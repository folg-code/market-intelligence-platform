"""The processing cycle orchestration function (ADR-0004, ADR-0011).

:func:`run_cycle` is the one place the six ordered stages
(:data:`moj_projekt.cycle.stages.DEFAULT_STAGES`) actually run, in order,
inside one :class:`~moj_projekt.domain.cycle_run.CycleRun` record. It takes
no FastAPI or APScheduler dependency - only an injected
:class:`~moj_projekt.domain.clock.Clock` and a
:class:`~moj_projekt.domain.repositories.CycleRunRepository` (backed by a
plain SQLAlchemy ``Session`` in production, via
:class:`~moj_projekt.persistence.cycle_run_repository.SqlAlchemyCycleRunRepository`) -
so it is directly callable from a unit test with fakes for both, from
:mod:`moj_projekt.cycle.run_once` without a scheduler, and from the
APScheduler job registered in :mod:`moj_projekt.api.app`.
"""

from __future__ import annotations

from collections.abc import Sequence

from moj_projekt.cycle.stages import DEFAULT_STAGES, Stage
from moj_projekt.domain.clock import Clock
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus, StageOutcome
from moj_projekt.domain.repositories import CycleRunRepository

__all__ = ["run_cycle"]


def run_cycle(
    *,
    clock: Clock,
    repository: CycleRunRepository,
    stages: Sequence[Stage] = DEFAULT_STAGES,
) -> CycleRun | None:
    """Run one processing cycle and return its terminal CycleRun.

    Returns ``None`` without doing anything when a CycleRun is already
    ``RUNNING`` - the data-level overlap guard (ADR-0011: "the cycle's
    idempotency is not allowed to depend on the scheduler behaving
    correctly"), which is what makes "two overlapping triggers result in
    one execution" true independently of the scheduler's own
    ``max_instances=1``.

    Stages run in order and stop at the first one that raises: later
    stages consume earlier stages' output (ingest -> extract -> narratives
    -> evidence -> state -> alerts), so continuing past a failure would
    mean operating on incomplete input. The raising stage's exception is
    caught and recorded as its own
    :class:`~moj_projekt.domain.cycle_run.StageOutcome` - it does not
    propagate out of this function - and the cycle still reaches exactly
    one terminal state: ``SUCCEEDED`` if every stage ran and succeeded,
    ``FAILED`` otherwise, with ``failure_reason`` naming which stage failed
    and why.
    """
    if repository.get_running() is not None:
        return None

    cycle_run = repository.add(CycleRun(started_at=clock.now()))

    failed_stage: str | None = None
    failure_detail: str | None = None
    for stage in stages:
        try:
            stage.run()
        except Exception as exc:  # a stage's own error must not crash the cycle
            failure_detail = f"{type(exc).__name__}: {exc}"
            cycle_run = cycle_run.with_stage_outcome(
                stage.name, StageOutcome(succeeded=False, failure_reason=failure_detail)
            )
            failed_stage = stage.name
            break
        else:
            cycle_run = cycle_run.with_stage_outcome(stage.name, StageOutcome(succeeded=True))

    if failed_stage is None:
        cycle_run = cycle_run.finish(status=CycleRunStatus.SUCCEEDED, ended_at=clock.now())
    else:
        cycle_run = cycle_run.finish(
            status=CycleRunStatus.FAILED,
            ended_at=clock.now(),
            failure_reason=f"stage '{failed_stage}' failed: {failure_detail}",
        )

    return repository.update(cycle_run)
