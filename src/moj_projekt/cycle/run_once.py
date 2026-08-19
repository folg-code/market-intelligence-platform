"""Direct entrypoint that runs exactly one processing cycle without the
scheduler (ADR-0011: "The cycle is invocable directly...so it is testable
and re-runnable without the scheduler.").

Usage::

    python -m moj_projekt.cycle.run_once

Builds a real ``Session``/``Clock``/repositories/RSS adapter from
``Settings`` and calls :func:`~moj_projekt.cycle.run_cycle.run_cycle` once.
This is also what an integration test calls twice in a row to exercise
"two consecutive cycles" against a real migrated database, without a live
scheduler running for real wall-clock time.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.cycle.ingest import build_production_stages
from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.domain.clock import Clock, SystemClock
from moj_projekt.domain.cycle_run import CycleRun
from moj_projekt.ingestion.adapter import SourceAdapter
from moj_projekt.ingestion.rss import RSS_SOURCE_TYPE, RssFeedAdapter
from moj_projekt.persistence.cycle_run_repository import SqlAlchemyCycleRunRepository
from moj_projekt.persistence.document_repository import SqlAlchemyDocumentRepository
from moj_projekt.persistence.source_repository import SqlAlchemySourceRepository

__all__ = ["run_once"]


def run_once(
    session: Session,
    *,
    clock: Clock | None = None,
    adapters: Mapping[str, SourceAdapter] | None = None,
) -> CycleRun | None:
    """Run exactly one processing cycle against ``session``.

    Uses :class:`~moj_projekt.domain.clock.SystemClock` and the RSS adapter
    unless the caller injects them (tests). Returns ``None`` if a CycleRun
    is already ``RUNNING``.
    """
    used_clock: Clock = SystemClock() if clock is None else clock
    owned_adapter: RssFeedAdapter | None = None
    if adapters is None:
        owned_adapter = RssFeedAdapter(clock=used_clock)
        adapters = {RSS_SOURCE_TYPE: owned_adapter}
    try:
        stages = build_production_stages(
            source_repository=SqlAlchemySourceRepository(session),
            document_repository=SqlAlchemyDocumentRepository(session),
            adapters=adapters,
        )
        repository = SqlAlchemyCycleRunRepository(session)
        return run_cycle(clock=used_clock, repository=repository, stages=stages)
    finally:
        if owned_adapter is not None:
            owned_adapter.close()


def main() -> int:
    """Run one cycle against the database configured by ``Settings``."""
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as session:
            result = run_once(session)
    finally:
        engine.dispose()

    if result is None:
        print("cycle skipped: another CycleRun is already RUNNING")
        return 0

    print(
        f"cycle {result.id}: {result.status.name} "
        f"({result.started_at} -> {result.ended_at})"
    )
    if result.failure_reason is not None:
        print(f"failure_reason: {result.failure_reason}")
    if result.source_outcomes:
        for source_key, outcome in result.source_outcomes.items():
            status = "ok" if outcome.succeeded else f"failed ({outcome.failure_reason})"
            print(f"  source {source_key}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
