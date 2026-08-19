"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.CycleRunRepository`.

Two writes per cycle, not one: :meth:`add` inserts the ``RUNNING`` row when
a cycle starts, :meth:`update` overwrites it in place with its terminal
state - there is no immutability/append-only rule for this table (unlike
``llm_runs``/``audit_entries``), because the whole point of the record is
to observe a run *while* it is still in progress
(:meth:`get_running`, the data-level overlap guard from ADR-0011).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus, StageOutcome
from moj_projekt.persistence.models import CycleRunModel

__all__ = ["SqlAlchemyCycleRunRepository"]


def _outcomes_to_json(outcomes: dict[str, StageOutcome]) -> dict[str, Any]:
    return {
        name: {"succeeded": outcome.succeeded, "failure_reason": outcome.failure_reason}
        for name, outcome in outcomes.items()
    }


def _outcomes_from_json(raw: dict[str, Any]) -> dict[str, StageOutcome]:
    return {
        name: StageOutcome(
            succeeded=value["succeeded"], failure_reason=value["failure_reason"]
        )
        for name, value in raw.items()
    }


def _to_domain(row: CycleRunModel) -> CycleRun:
    return CycleRun(
        id=row.id,
        started_at=row.started_at,
        status=CycleRunStatus(row.status),
        ended_at=row.ended_at,
        stage_outcomes=_outcomes_from_json(row.stage_outcomes),
        source_outcomes=_outcomes_from_json(row.source_outcomes),
        failure_reason=row.failure_reason,
    )


class SqlAlchemyCycleRunRepository:
    """Persists CycleRuns and answers "is one currently running?"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, cycle_run: CycleRun) -> CycleRun:
        row = CycleRunModel(
            started_at=cycle_run.started_at,
            ended_at=cycle_run.ended_at,
            status=int(cycle_run.status),
            stage_outcomes=_outcomes_to_json(dict(cycle_run.stage_outcomes)),
            source_outcomes=_outcomes_to_json(dict(cycle_run.source_outcomes)),
            failure_reason=cycle_run.failure_reason,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return _to_domain(row)

    def update(self, cycle_run: CycleRun) -> CycleRun:
        if cycle_run.id is None:
            raise ValueError("CycleRun.id is required to update an existing row")

        result = self._session.execute(
            update(CycleRunModel)
            .where(CycleRunModel.id == cycle_run.id)
            .values(
                ended_at=cycle_run.ended_at,
                status=int(cycle_run.status),
                stage_outcomes=_outcomes_to_json(dict(cycle_run.stage_outcomes)),
                source_outcomes=_outcomes_to_json(dict(cycle_run.source_outcomes)),
                failure_reason=cycle_run.failure_reason,
            )
        )
        self._session.flush()

        # `execute()` on an UPDATE returns a CursorResult at runtime, which
        # does have `rowcount` - the generic `Result[Any]` return type just
        # doesn't expose it statically (matches
        # SqlAlchemyDocumentRepository.advance_processing_status).
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise ValueError(f"CycleRun {cycle_run.id} does not exist")

        row = self._session.get(CycleRunModel, cycle_run.id)
        assert row is not None
        return _to_domain(row)

    def get(self, cycle_run_id: UUID) -> CycleRun | None:
        row = self._session.get(CycleRunModel, cycle_run_id)
        return _to_domain(row) if row is not None else None

    def get_running(self) -> CycleRun | None:
        row = self._session.execute(
            select(CycleRunModel).where(
                CycleRunModel.status == int(CycleRunStatus.RUNNING)
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row is not None else None
