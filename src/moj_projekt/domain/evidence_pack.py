"""``EvidencePack`` - a standardized, versioned snapshot of evidence
supporting/contradicting a Narrative (DOMAIN_MODEL.md section 3, "Evidence &
Trust"; ADR-0003).

Pure domain representation: no persistence concern, no infrastructure
import. Identity is ``(narrative_id, evidence_version)`` - a rebuild
produces a new version rather than mutating an existing pack, so this type
takes ``generated_at`` as a constructor argument rather than reading a
clock itself (root ``CLAUDE.md``: "the clock is injected").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from moj_projekt.domain.evidence import EvidenceRef

__all__ = ["EvidencePack"]


@dataclass(frozen=True, slots=True)
class EvidencePack:
    """One versioned snapshot of evidence for a Narrative.

    ``independent_source_count`` is computed and stored separately from
    ``source_count``, and is always less than or equal to it - documents
    deriving from one originating report count once (ADR-0003).

    ``market_evidence`` must be empty in MVP - there is no market data feed
    yet, and an empty ``market_evidence`` is what downstream validation
    relies on to forbid market-pricing language (ADR-0003 rule 5). This is
    a domain-level guard so it can be lifted in one place once a market
    data feed exists; it is deliberately not also a database constraint,
    which would need a migration to drop at that point.
    """

    narrative_id: UUID
    evidence_version: int
    generated_at: datetime
    source_count: int
    independent_source_count: int
    source_diversity: int
    supporting_evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    contradicting_evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    top_supporting_events: tuple[UUID, ...] = field(default_factory=tuple)
    key_facts: tuple[str, ...] = field(default_factory=tuple)
    strongest_sources: tuple[str, ...] = field(default_factory=tuple)
    dissenting_sources: tuple[str, ...] = field(default_factory=tuple)
    official_evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    media_evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    social_evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    market_evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    evidence_gaps: tuple[str, ...] = field(default_factory=tuple)
    id: UUID | None = None

    def __post_init__(self) -> None:
        if self.evidence_version < 1:
            raise ValueError("EvidencePack.evidence_version must be >= 1")
        if self.source_count < 0:
            raise ValueError("EvidencePack.source_count must not be negative")
        if self.independent_source_count < 0:
            raise ValueError(
                "EvidencePack.independent_source_count must not be negative"
            )
        if self.independent_source_count > self.source_count:
            raise ValueError(
                "EvidencePack.independent_source_count must be <= source_count "
                f"({self.independent_source_count} > {self.source_count})"
            )
        if self.source_diversity < 0:
            raise ValueError("EvidencePack.source_diversity must not be negative")
        if len(self.market_evidence) > 0:
            raise ValueError(
                "EvidencePack.market_evidence must be empty in MVP - "
                "no market data feed exists yet (ADR-0003)"
            )
