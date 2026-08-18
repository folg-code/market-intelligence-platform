"""Closed-set value objects (enums) from ``docs/vision/DOMAIN_MODEL.md`` section 4.

Every member name and value below mirrors the domain model document exactly.
These are plain :mod:`enum` types: illegal values are rejected at
construction because Python raises ``ValueError`` for an unknown enum value,
so callers never need to hand-roll that validation.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

__all__ = [
    "SourceTier",
    "ValidityStatus",
    "LifecycleStatus",
    "ImpactDirection",
    "ImpactHorizon",
    "OverrideState",
    "CandidateStatus",
    "EpistemicCategory",
    "RelationType",
    "Instrument",
    "EvidenceRefKind",
]


class SourceTier(IntEnum):
    """Trust tier of a :class:`Source` (DOMAIN_MODEL.md section 3, 4)."""

    PRIMARY = 1
    """Primary / official source (e.g. Fed/FOMC, BLS, SEC)."""
    PROFESSIONAL = 2
    """Professional reporting (established news outlets)."""
    SPECIALIST = 3
    """Specialist / research source."""
    SOCIAL = 4
    """Social source."""


class ValidityStatus(StrEnum):
    """Narrative validity (DOMAIN_MODEL.md section 4).

    ``confirmed`` is never set by an LLM (ADR-0002) - that rule is enforced
    by the validation layer, not by this type.
    """

    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    INVALID = "invalid"
    REJECTED = "rejected"


class LifecycleStatus(StrEnum):
    """Narrative lifecycle (DOMAIN_MODEL.md section 4).

    Deliberately excludes ``accelerating``, ``dominant``, ``recurring`` -
    those describe other dimensions (dynamics, not lifecycle).
    """

    EMERGING = "emerging"
    ACTIVE = "active"
    FADING = "fading"
    DORMANT = "dormant"
    RESOLVED = "resolved"


class ImpactDirection(StrEnum):
    """Direction of a Narrative's impact on an instrument (DOMAIN_MODEL.md section 4)."""

    STRONGLY_BEARISH = "strongly_bearish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    STRONGLY_BULLISH = "strongly_bullish"
    UNCERTAIN = "uncertain"


class ImpactHorizon(StrEnum):
    """Time horizon of an instrument impact assessment (DOMAIN_MODEL.md section 4)."""

    INTRADAY = "intraday"
    MULTI_DAY = "multi_day"
    UNKNOWN = "unknown"


class OverrideState(StrEnum):
    """Degree of human protection over a domain decision (DOMAIN_MODEL.md sections 4, 6)."""

    NONE = "none"
    USER_PREFERRED = "user_preferred"
    USER_LOCKED = "user_locked"


class CandidateStatus(StrEnum):
    """Output of the deterministic validation layer (DOMAIN_MODEL.md section 4, ADR-0002)."""

    ACCEPTED = "accepted"
    PROPOSED = "proposed"
    REJECTED = "rejected"


class EpistemicCategory(StrEnum):
    """Kind of evidence item (DOMAIN_MODEL.md section 4)."""

    OBSERVED_FACT = "observed_fact"
    SOURCE_CLAIM = "source_claim"
    MODEL_INFERENCE = "model_inference"
    SYSTEM_METRIC = "system_metric"
    MARKET_EVIDENCE = "market_evidence"


class RelationType(StrEnum):
    """Relation between two Narratives (DOMAIN_MODEL.md section 3, 4)."""

    RELATED_TO = "related_to"
    CAUSES = "causes"
    CONTRIBUTES_TO = "contributes_to"
    CONTRADICTS = "contradicts"
    PARENT_OF = "parent_of"
    MERGED_INTO = "merged_into"


class Instrument(StrEnum):
    """Tracked instrument set - closed in MVP (DOMAIN_MODEL.md section 4)."""

    NQ = "NQ"
    BTC = "BTC"
    GOLD = "GOLD"


class EvidenceRefKind(StrEnum):
    """What an :class:`~moj_projekt.domain.evidence.EvidenceRef` points at."""

    DOCUMENT = "document"
    EVENT = "event"
    FACT = "fact"
