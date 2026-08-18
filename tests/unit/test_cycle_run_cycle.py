"""Unit tests for the cycle orchestration function (S001-T011) - no
database. Uses a fake :class:`~moj_projekt.domain.clock.Clock` (fixed,
incrementing timestamps) and a fake in-memory
:class:`~moj_projekt.domain.repositories.CycleRunRepository`, exactly the
injected-dependency seams ``run_cycle`` exists to provide (root
``CLAUDE.md``: "The clock is injected... the pipeline is time-sensitive and
must be testable.").
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus, StageOutcome

_T0 = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)


class _FakeClock:
    """Returns each of ``times`` in order, one per call to ``now()``."""

    def __init__(self, times: Sequence[datetime]) -> None:
        self._times: Iterator[datetime] = iter(times)

    def now(self) -> datetime:
        return next(self._times)


class _FakeCycleRunRepository:
    """In-memory stand-in for :class:`SqlAlchemyCycleRunRepository`."""

    def __init__(self, *, seeded: CycleRun | None = None) -> None:
        self._rows: dict[UUID, CycleRun] = {}
        if seeded is not None:
            row = seeded if seeded.id is not None else replace(seeded, id=uuid4())
            self._rows[row.id] = row  # type: ignore[index]

    def add(self, cycle_run: CycleRun) -> CycleRun:
        stored = replace(cycle_run, id=uuid4())
        self._rows[stored.id] = stored  # type: ignore[index]
        return stored

    def update(self, cycle_run: CycleRun) -> CycleRun:
        if cycle_run.id not in self._rows:
            raise ValueError(f"CycleRun {cycle_run.id} does not exist")
        self._rows[cycle_run.id] = cycle_run  # type: ignore[index]
        return cycle_run

    def get(self, cycle_run_id: UUID) -> CycleRun | None:
        return self._rows.get(cycle_run_id)

    def get_running(self) -> CycleRun | None:
        for row in self._rows.values():
            if row.status is CycleRunStatus.RUNNING:
                return row
        return None

    def all_rows(self) -> list[CycleRun]:
        return list(self._rows.values())


def test_run_cycle_reaches_succeeded_with_clock_supplied_timestamps() -> None:
    ended_at = _T0 + timedelta(seconds=3)
    clock = _FakeClock([_T0, ended_at])
    repository = _FakeCycleRunRepository()
    stages = [Stage("ingest", lambda: None), Stage("extract", lambda: None)]

    result = run_cycle(clock=clock, repository=repository, stages=stages)

    assert result is not None
    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.started_at == _T0
    assert result.ended_at == ended_at
    assert result.failure_reason is None
    assert result.stage_outcomes == {
        "ingest": StageOutcome(succeeded=True),
        "extract": StageOutcome(succeeded=True),
    }


def test_run_cycle_catches_a_raising_stage_and_still_reaches_a_terminal_state() -> None:
    ended_at = _T0 + timedelta(seconds=1)
    clock = _FakeClock([_T0, ended_at])
    repository = _FakeCycleRunRepository()

    def _boom() -> None:
        raise RuntimeError("source unavailable")

    stages = [Stage("ingest", _boom), Stage("extract", lambda: None)]

    result = run_cycle(clock=clock, repository=repository, stages=stages)

    assert result is not None
    assert result.status is CycleRunStatus.FAILED
    assert result.status.is_terminal is True
    assert result.ended_at == ended_at
    assert result.failure_reason is not None
    assert "ingest" in result.failure_reason
    assert "source unavailable" in result.failure_reason
    ingest_outcome = result.stage_outcomes["ingest"]
    assert ingest_outcome.succeeded is False
    assert ingest_outcome.failure_reason is not None
    assert "source unavailable" in ingest_outcome.failure_reason
    # The pipeline stops at the first failing stage: later stages that would
    # consume its output are not attempted.
    assert "extract" not in result.stage_outcomes


def test_run_cycle_records_exactly_one_cycle_run_even_when_a_stage_raises() -> None:
    clock = _FakeClock([_T0, _T0 + timedelta(seconds=1)])
    repository = _FakeCycleRunRepository()

    def _boom() -> None:
        raise ValueError("boom")

    run_cycle(clock=clock, repository=repository, stages=[Stage("ingest", _boom)])

    assert len(repository.all_rows()) == 1
    assert repository.all_rows()[0].status.is_terminal


def test_run_cycle_no_ops_when_a_run_is_already_in_progress() -> None:
    already_running = CycleRun(started_at=_T0 - timedelta(minutes=5))
    repository = _FakeCycleRunRepository(seeded=already_running)
    clock = _FakeClock([_T0])  # would raise StopIteration if now() were called

    result = run_cycle(
        clock=clock, repository=repository, stages=[Stage("ingest", lambda: None)]
    )

    assert result is None
    assert len(repository.all_rows()) == 1
    assert repository.all_rows()[0].status is CycleRunStatus.RUNNING


def test_run_cycle_no_op_does_not_call_the_clock() -> None:
    already_running = CycleRun(started_at=_T0 - timedelta(minutes=5))
    repository = _FakeCycleRunRepository(seeded=already_running)
    clock = _FakeClock([])  # calling now() would raise StopIteration

    result = run_cycle(
        clock=clock, repository=repository, stages=[Stage("ingest", lambda: None)]
    )

    assert result is None


def test_run_cycle_defaults_to_the_six_ordered_stages_and_they_all_succeed() -> None:
    ended_at = _T0 + timedelta(seconds=2)
    clock = _FakeClock([_T0, ended_at])
    repository = _FakeCycleRunRepository()

    result = run_cycle(clock=clock, repository=repository)

    assert result is not None
    assert result.status is CycleRunStatus.SUCCEEDED
    assert set(result.stage_outcomes) == {
        "ingest",
        "extract",
        "narratives",
        "evidence",
        "state",
        "alerts",
    }


@pytest.mark.parametrize("stage_index", range(6))
def test_run_cycle_reports_failure_from_any_stage_position(stage_index: int) -> None:
    from moj_projekt.cycle.stages import DEFAULT_STAGES

    clock = _FakeClock([_T0, _T0 + timedelta(seconds=1)])
    repository = _FakeCycleRunRepository()

    def _boom() -> None:
        raise RuntimeError("failed here")

    stages = list(DEFAULT_STAGES)
    failing_name = stages[stage_index].name
    stages[stage_index] = Stage(failing_name, _boom)

    result = run_cycle(clock=clock, repository=repository, stages=stages)

    assert result is not None
    assert result.status is CycleRunStatus.FAILED
    assert result.failure_reason is not None
    assert failing_name in result.failure_reason
