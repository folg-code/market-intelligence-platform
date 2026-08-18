"""The model of docs/vision/DOMAIN_MODEL.md.

Value objects, invariants, and repository interfaces. Must not import
SQLAlchemy, httpx, or the Anthropic SDK - enforced by a test
(root CLAUDE.md, docs/reference/MODULE_MAP.md).
"""

from __future__ import annotations

from moj_projekt.domain.document import Document, DocumentDedupeKey, ProcessingStatus
from moj_projekt.domain.embedding import IdentityEmbedding
from moj_projekt.domain.enums import (
    CandidateStatus,
    EpistemicCategory,
    EvidenceRefKind,
    ImpactDirection,
    ImpactHorizon,
    Instrument,
    LifecycleStatus,
    OverrideState,
    RelationType,
    SourceTier,
    ValidityStatus,
)
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.repositories import DocumentRepository, SourceRepository
from moj_projekt.domain.source import Source

__all__ = [
    "CandidateStatus",
    "Document",
    "DocumentDedupeKey",
    "DocumentRepository",
    "EpistemicCategory",
    "EvidenceRef",
    "EvidenceRefKind",
    "IdentityEmbedding",
    "ImpactDirection",
    "ImpactHorizon",
    "Instrument",
    "LifecycleStatus",
    "OverrideState",
    "ProcessingStatus",
    "RelationType",
    "Source",
    "SourceRepository",
    "SourceTier",
    "ValidityStatus",
]
