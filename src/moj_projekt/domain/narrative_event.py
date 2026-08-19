"""``NarrativeEvent`` - the assignment of an Event to a Narrative
(DOMAIN_MODEL.md section 3, "Narrative Intelligence"; section 5 assignment
rule; ADR-0014).

Pure domain representation: no persistence concern, no infrastructure
import. Identity is the ``(narrative_id, event_id)`` pair. The
three-condition assignment rule itself (same economic mechanism; similar
affected instruments/exposures; strengthens/weakens/updates the same market
interpretation) is judged upstream by an LLM plus the deterministic
validation layer (ADR-0002, ADR-0014) - this type only stores the *result*
of that judgement, it cannot re-derive or re-check the rule from a single
row.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from moj_projekt.domain.enums import CandidateStatus, OverrideState

__all__ = ["NarrativeEvent"]


@dataclass(frozen=True, slots=True)
class NarrativeEvent:
    """One (narrative, event) assignment, with its rationale, confidence,
    validation outcome, and the retrieval context that produced it.

    ``candidate_shortlist`` records the retrieved candidates and their
    similarity scores that were considered for this assignment (ADR-0014) -
    similarity narrows or blocks the shortlist, it never itself decides the
    assignment.
    """

    narrative_id: UUID
    event_id: UUID
    assignment_rationale: str
    assignment_confidence: float
    assignment_status: CandidateStatus = CandidateStatus.PROPOSED
    llm_run_id: UUID | None = None
    candidate_shortlist: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    override_state: OverrideState = OverrideState.NONE
    id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.assignment_rationale.strip():
            raise ValueError("NarrativeEvent.assignment_rationale must not be empty")
        if not (0.0 <= self.assignment_confidence <= 1.0):
            raise ValueError(
                "NarrativeEvent.assignment_confidence must be between 0.0 and 1.0"
            )
