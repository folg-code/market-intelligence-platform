"""``CycleRun`` - the audit record of one 5-minute processing cycle
(ADR-0004, ADR-0011; ``ARCHITECTURE_FOUNDATIONS.md`` section 4).

Pure domain representation: no persistence concern, no infrastructure
import. ADR-0011 states the run record, not scheduler logs, is the audit
surface, and that overlap prevention must not depend solely on the
scheduler behaving correctly - the "at most one RUNNING row" invariant is a
cross-row invariant this type cannot check on its own (mirroring
:class:`~moj_projekt.domain.narrative_episode.NarrativeEpisode`'s overlap
rule); it is enforced by the orchestration function reading
:meth:`~moj_projekt.domain.repositories.CycleRunRepository.get_running`
before starting a new run, and independently by a database constraint (see
migration ``0006``). Once the row is terminal, a further UPDATE is rejected
at the database (migration ``0007``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import IntEnum
from uuid import UUID

__all__ = ["CycleRun", "CycleRunStatus", "StageOutcome"]


class CycleRunStatus(IntEnum):
    """Lifecycle of one CycleRun.

    Mirrors :class:`~moj_projekt.domain.document.ProcessingStatus`'s
    IntEnum style. Every CycleRun starts ``RUNNING`` and moves to exactly
    one terminal value; the acceptance criterion this exists to satisfy is
    "a cycle produces exactly one CycleRun record with a terminal state,
    including when a stage raises" - so a run that fails is still a
    terminal ``FAILED`` record, never left ``RUNNING`` or discarded.
    """

    RUNNING = 1
    SUCCEEDED = 2
    FAILED = 3

    @property
    def is_terminal(self) -> bool:
        return self is not CycleRunStatus.RUNNING


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """Whether one unit of cycle work succeeded, and why not when it did not.

    Reused for both ``CycleRun.stage_outcomes`` (one of the six pipeline
    stages) and ``CycleRun.source_outcomes`` (one ingestion source, per root
    ``CLAUDE.md``: "A failing source must not fail the cycle. Ingestion
    errors are isolated per source and recorded in the CycleRun record.") -
    both are "did this named unit of work succeed" records with the same
    shape, so one typed type serves both rather than two near-identical
    ones.
    """

    succeeded: bool
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.succeeded and self.failure_reason is not None:
            raise ValueError(
                "StageOutcome.failure_reason is only meaningful when succeeded is False"
            )
        if not self.succeeded and (
            self.failure_reason is None or not self.failure_reason.strip()
        ):
            raise ValueError(
                "StageOutcome.failure_reason is required when succeeded is False"
            )


@dataclass(frozen=True, slots=True)
class CycleRun:
    """One run of the 5-minute processing cycle (ADR-0004, ADR-0011).

    ``stage_outcomes`` records, keyed by stage name, whether each of the
    ordered pipeline stages
    (:data:`moj_projekt.cycle.stages.DEFAULT_STAGES`) succeeded.
    ``source_outcomes`` is the per-unit map for isolated work that must
    not fail the cycle: ingest keys it by source key (S001-T012); extract
    keys per-document transport failures by document id (S002-T009).
    ``failure_reason`` is the top-level reason the cycle as a whole is
    ``FAILED`` (e.g. naming which stage raised); it is distinct from any
    individual stage's own ``failure_reason`` in ``stage_outcomes``.
    """

    started_at: datetime
    status: CycleRunStatus = CycleRunStatus.RUNNING
    ended_at: datetime | None = None
    stage_outcomes: Mapping[str, StageOutcome] = field(default_factory=dict)
    source_outcomes: Mapping[str, StageOutcome] = field(default_factory=dict)
    failure_reason: str | None = None
    id: UUID | None = None

    def __post_init__(self) -> None:
        if self.status.is_terminal:
            if self.ended_at is None:
                raise ValueError("CycleRun.ended_at is required once status is terminal")
        elif self.ended_at is not None:
            raise ValueError("CycleRun.ended_at must be unset while status is RUNNING")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("CycleRun.ended_at must be >= started_at")
        if self.status is CycleRunStatus.FAILED:
            if self.failure_reason is None or not self.failure_reason.strip():
                raise ValueError(
                    "CycleRun.failure_reason is required when status is FAILED"
                )
        elif self.failure_reason is not None:
            raise ValueError(
                "CycleRun.failure_reason is only meaningful when status is FAILED"
            )

    def with_stage_outcome(self, stage: str, outcome: StageOutcome) -> CycleRun:
        """Return a copy with ``stage`` recorded in ``stage_outcomes``.

        Rejects being called once the run has already reached a terminal
        state: a stage outcome can only be recorded while the cycle this
        run represents is still in progress.
        """
        if self.status.is_terminal:
            raise ValueError("cannot record a stage outcome on a terminal CycleRun")
        return replace(self, stage_outcomes={**self.stage_outcomes, stage: outcome})

    def with_source_outcome(self, source_key: str, outcome: StageOutcome) -> CycleRun:
        """Return a copy with ``source_key`` recorded in ``source_outcomes``.

        Same terminal-state guard as :meth:`with_stage_outcome`: per-source
        ingest results are only meaningful while the cycle is still running.
        """
        if self.status.is_terminal:
            raise ValueError("cannot record a source outcome on a terminal CycleRun")
        return replace(
            self, source_outcomes={**self.source_outcomes, source_key: outcome}
        )

    def with_document_outcome(self, document_id: UUID, outcome: StageOutcome) -> CycleRun:
        """Record a per-document extract outcome on ``source_outcomes``.

        Reuses the existing per-unit JSONB map (extraction adds no table
        and no CycleRun column - D-S002-02 P8). Document ids do not
        collide with ingest source keys.
        """
        return self.with_source_outcome(str(document_id), outcome)

    def finish(
        self,
        *,
        status: CycleRunStatus,
        ended_at: datetime,
        failure_reason: str | None = None,
    ) -> CycleRun:
        """Return a terminal copy of this CycleRun.

        Rejects a non-terminal ``status`` (``finish`` exists precisely to
        move a run to its terminal state) and rejects being called on a
        CycleRun that is already terminal - a CycleRun reaches its terminal
        state exactly once.
        """
        if not status.is_terminal:
            raise ValueError("CycleRun.finish requires a terminal status")
        if self.status.is_terminal:
            raise ValueError("CycleRun is already terminal")
        return replace(
            self, status=status, ended_at=ended_at, failure_reason=failure_reason
        )
