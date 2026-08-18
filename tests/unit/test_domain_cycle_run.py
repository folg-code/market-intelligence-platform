"""Unit tests for CycleRun/CycleRunStatus/StageOutcome invariants
(S001-T011) - no database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus, StageOutcome

_STARTED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def test_stage_outcome_rejects_failure_reason_when_succeeded() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        StageOutcome(succeeded=True, failure_reason="boom")


def test_stage_outcome_requires_failure_reason_when_not_succeeded() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        StageOutcome(succeeded=False)


def test_new_cycle_run_starts_running_with_no_ended_at_or_failure_reason() -> None:
    cycle_run = CycleRun(started_at=_STARTED_AT)

    assert cycle_run.status is CycleRunStatus.RUNNING
    assert cycle_run.status.is_terminal is False
    assert cycle_run.ended_at is None
    assert cycle_run.failure_reason is None
    assert cycle_run.stage_outcomes == {}
    assert cycle_run.source_outcomes == {}


def test_running_cycle_run_rejects_an_ended_at() -> None:
    with pytest.raises(ValueError, match="ended_at"):
        CycleRun(started_at=_STARTED_AT, ended_at=_STARTED_AT)


def test_terminal_cycle_run_requires_an_ended_at() -> None:
    with pytest.raises(ValueError, match="ended_at"):
        CycleRun(started_at=_STARTED_AT, status=CycleRunStatus.SUCCEEDED)


def test_ended_at_before_started_at_is_rejected() -> None:
    with pytest.raises(ValueError, match="ended_at"):
        CycleRun(
            started_at=_STARTED_AT,
            status=CycleRunStatus.SUCCEEDED,
            ended_at=_STARTED_AT - timedelta(seconds=1),
        )


def test_failed_cycle_run_requires_a_failure_reason() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        CycleRun(
            started_at=_STARTED_AT,
            status=CycleRunStatus.FAILED,
            ended_at=_STARTED_AT + timedelta(minutes=1),
        )


def test_succeeded_cycle_run_rejects_a_failure_reason() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        CycleRun(
            started_at=_STARTED_AT,
            status=CycleRunStatus.SUCCEEDED,
            ended_at=_STARTED_AT + timedelta(minutes=1),
            failure_reason="should not be here",
        )


def test_with_stage_outcome_accumulates_without_mutating_the_original() -> None:
    cycle_run = CycleRun(started_at=_STARTED_AT)

    updated = cycle_run.with_stage_outcome("ingest", StageOutcome(succeeded=True))

    assert cycle_run.stage_outcomes == {}
    assert updated.stage_outcomes == {"ingest": StageOutcome(succeeded=True)}


def test_with_stage_outcome_rejects_a_terminal_cycle_run() -> None:
    cycle_run = CycleRun(started_at=_STARTED_AT).finish(
        status=CycleRunStatus.SUCCEEDED, ended_at=_STARTED_AT + timedelta(minutes=1)
    )

    with pytest.raises(ValueError, match="terminal"):
        cycle_run.with_stage_outcome("ingest", StageOutcome(succeeded=True))


def test_finish_requires_a_terminal_status() -> None:
    cycle_run = CycleRun(started_at=_STARTED_AT)

    with pytest.raises(ValueError, match="terminal"):
        cycle_run.finish(status=CycleRunStatus.RUNNING, ended_at=_STARTED_AT)


def test_finish_rejects_an_already_terminal_cycle_run() -> None:
    finished = CycleRun(started_at=_STARTED_AT).finish(
        status=CycleRunStatus.SUCCEEDED, ended_at=_STARTED_AT + timedelta(minutes=1)
    )

    with pytest.raises(ValueError, match="already terminal"):
        finished.finish(
            status=CycleRunStatus.FAILED,
            ended_at=_STARTED_AT + timedelta(minutes=2),
            failure_reason="x",
        )


def test_finish_succeeded_produces_a_terminal_cycle_run() -> None:
    ended_at = _STARTED_AT + timedelta(minutes=1)
    finished = CycleRun(started_at=_STARTED_AT).finish(
        status=CycleRunStatus.SUCCEEDED, ended_at=ended_at
    )

    assert finished.status is CycleRunStatus.SUCCEEDED
    assert finished.status.is_terminal is True
    assert finished.ended_at == ended_at
