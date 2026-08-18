"""``NarrativeInstrumentImpact`` - an explicit, auditable Narrative-to-
Instrument impact assessment (DOMAIN_MODEL.md section 3, "Instrument
Impact"; ADR-0006).

Pure domain representation: no persistence concern, no infrastructure
import. Identity is ``(narrative_id, instrument)`` - **one current**
assessment per pair, not a history of assessments (DOMAIN_MODEL.md). This
mirrors a "current state" row, not a versioned snapshot like
:class:`~moj_projekt.domain.evidence_pack.EvidencePack` - the domain model
gives instrument impact no versioning/history language the way it does for
EvidencePack, and no requirement to keep old assessments exists yet. A
re-assessment therefore **replaces** the current row for that pair
(persistence layer: an upsert keyed on the unique ``(narrative_id,
instrument)`` constraint) rather than creating a new one - a documented
judgment call, analogous to the embedding-dimension placeholder in
S001-T008; revisit if a future need for impact-assessment history emerges.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from moj_projekt.domain.enums import CandidateStatus, ImpactDirection, ImpactHorizon, Instrument
from moj_projekt.domain.evidence import EvidenceRef

__all__ = ["NarrativeInstrumentImpact"]


@dataclass(frozen=True, slots=True)
class NarrativeInstrumentImpact:
    """One current impact assessment of a Narrative on a tracked Instrument.

    ``relevance`` states whether the narrative matters to this instrument at
    all - it is never inferred solely from entity/keyword presence
    (ADR-0006). A non-neutral ``direction`` requires non-empty ``rationale``
    and non-empty ``evidence_refs`` (ADR-0006 rule: "A non-neutral direction
    requires non-empty rationale and evidence_refs").
    """

    narrative_id: UUID
    instrument: Instrument
    relevance: bool
    direction: ImpactDirection
    confidence: float
    horizon: ImpactHorizon
    rationale: str = ""
    impact_channels: Sequence[str] = field(default_factory=tuple)
    evidence_refs: Sequence[EvidenceRef] = field(default_factory=tuple)
    status: CandidateStatus = CandidateStatus.PROPOSED
    llm_run_id: UUID | None = None
    id: UUID | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                "NarrativeInstrumentImpact.confidence must be between 0.0 and 1.0"
            )
        if self.direction is not ImpactDirection.NEUTRAL:
            if not self.rationale.strip():
                raise ValueError(
                    "NarrativeInstrumentImpact.rationale is required for a "
                    "non-neutral direction (ADR-0006)"
                )
            if len(self.evidence_refs) == 0:
                raise ValueError(
                    "NarrativeInstrumentImpact.evidence_refs must not be empty "
                    "for a non-neutral direction (ADR-0006)"
                )
