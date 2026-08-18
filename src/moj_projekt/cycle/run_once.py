"""Direct entrypoint that runs exactly one processing cycle without the
scheduler (ADR-0011: "The cycle is invocable directly...so it is testable
and re-runnable without the scheduler.").

Usage::

    python -m moj_projekt.cycle.run_once

Builds a real ``Session``/``SystemClock``/repository from ``Settings``, the
same way :mod:`moj_projekt.persistence.seed_sources` builds its own
dependencies, and calls :func:`~moj_projekt.cycle.run_cycle.run_cycle` once.
This is also what an integration test calls twice in a row to exercise "two
consecutive cycles" against a real migrated database, without a live
scheduler running for real wall-clock time.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.domain.clock import SystemClock
from moj_projekt.domain.cycle_run import CycleRun
from moj_projekt.persistence.cycle_run_repository import SqlAlchemyCycleRunRepository

__all__ = ["run_once"]


def run_once(session: Session) -> CycleRun | None:
    """Run exactly one processing cycle against ``session``, using the real
    system clock. Returns ``None`` if a CycleRun is already ``RUNNING``.
    """
    repository = SqlAlchemyCycleRunRepository(session)
    return run_cycle(clock=SystemClock(), repository=repository)


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
