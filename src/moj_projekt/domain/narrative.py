"""``Narrative`` - the product's central object: a market interpretation with
a durable identity (DOMAIN_MODEL.md section 3, "Narrative Intelligence";
ADR-0001, ADR-0014).

Pure domain representation: no persistence concern, no infrastructure
import. Identity is ``canonical_key`` - a semantic, human-readable, stable
identifier, never a cluster hash and never the embedding (ADR-0001).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from moj_projekt.domain.embedding import IdentityEmbedding
from moj_projekt.domain.enums import LifecycleStatus, OverrideState, ValidityStatus

__all__ = ["Narrative"]


@dataclass(frozen=True, slots=True)
class Narrative:
    """A market interpretation with an economic mechanism, exposures,
    lifecycle, validity, and durable identity.

    ``identity_embedding`` is derived, recomputable, and never authoritative
    (ADR-0014): a Narrative with no embedding is still fully valid - only
    retrieval degrades. Uniqueness of ``canonical_key`` and the "material
    narrative needs a current EvidencePack" rule are enforced outside this
    constructor (the database unique constraint and the end-of-cycle check,
    respectively) - a single Narrative instance cannot know about its
    siblings or about EvidencePack existence.
    """

    canonical_key: str
    display_title: str
    economic_mechanism: str
    market_interpretation: str
    category: str
    first_seen: datetime
    last_seen: datetime
    updated_at: datetime
    validity_status: ValidityStatus = ValidityStatus.CANDIDATE
    lifecycle_status: LifecycleStatus = LifecycleStatus.EMERGING
    entities: Sequence[str] = field(default_factory=tuple)
    topics: Sequence[str] = field(default_factory=tuple)
    attention_score: float = 0.0
    strength: float = 0.0
    velocity: float = 0.0
    momentum: float = 0.0
    confidence: float = 0.0
    uncertainty_reasons: Sequence[str] = field(default_factory=tuple)
    contradiction_signals: Sequence[str] = field(default_factory=tuple)
    override_state: OverrideState = OverrideState.NONE
    identity_embedding: IdentityEmbedding | None = None
    id: UUID | None = None

    def __post_init__(self) -> None:
        for attr_name in (
            "canonical_key",
            "display_title",
            "economic_mechanism",
            "market_interpretation",
            "category",
        ):
            value = getattr(self, attr_name)
            if not value.strip():
                raise ValueError(f"Narrative.{attr_name} must not be empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Narrative.confidence must be between 0.0 and 1.0")
        if self.first_seen > self.last_seen:
            raise ValueError("Narrative.first_seen must be <= last_seen")
