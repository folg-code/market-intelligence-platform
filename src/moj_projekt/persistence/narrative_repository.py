"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.NarrativeRepository`.

``canonical_key`` uniqueness (ADR-0001) is enforced by the
``uq_narratives_canonical_key`` constraint from the migration: inserting a
duplicate raises ``IntegrityError`` rather than being silently
special-cased here. ``identity_embedding`` round-trips through the
``pgvector`` column type as a plain sequence of floats.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from moj_projekt.domain.embedding import IdentityEmbedding
from moj_projekt.domain.enums import LifecycleStatus, OverrideState, ValidityStatus
from moj_projekt.domain.narrative import Narrative
from moj_projekt.persistence.models import NarrativeModel

__all__ = ["SqlAlchemyNarrativeRepository"]


def _to_domain(row: NarrativeModel) -> Narrative:
    identity_embedding: IdentityEmbedding | None = None
    if row.identity_embedding is not None:
        assert row.embedding_model is not None
        assert row.embedding_version is not None
        identity_embedding = IdentityEmbedding(
            embedding_model=row.embedding_model,
            embedding_version=row.embedding_version,
            vector=tuple(float(component) for component in row.identity_embedding),
        )
    return Narrative(
        id=row.id,
        canonical_key=row.canonical_key,
        display_title=row.display_title,
        validity_status=ValidityStatus(row.validity_status),
        lifecycle_status=LifecycleStatus(row.lifecycle_status),
        economic_mechanism=row.economic_mechanism,
        market_interpretation=row.market_interpretation,
        category=row.category,
        entities=tuple(row.entities),
        topics=tuple(row.topics),
        attention_score=row.attention_score,
        strength=row.strength,
        velocity=row.velocity,
        momentum=row.momentum,
        confidence=row.confidence,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
        updated_at=row.updated_at,
        uncertainty_reasons=tuple(row.uncertainty_reasons),
        contradiction_signals=tuple(row.contradiction_signals),
        override_state=OverrideState(row.override_state),
        identity_embedding=identity_embedding,
    )


class SqlAlchemyNarrativeRepository:
    """Persists Narratives. No update path in this sprint's scope."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, narrative: Narrative) -> Narrative:
        embedding = narrative.identity_embedding
        row = NarrativeModel(
            canonical_key=narrative.canonical_key,
            display_title=narrative.display_title,
            validity_status=narrative.validity_status.value,
            lifecycle_status=narrative.lifecycle_status.value,
            economic_mechanism=narrative.economic_mechanism,
            market_interpretation=narrative.market_interpretation,
            category=narrative.category,
            entities=list(narrative.entities),
            topics=list(narrative.topics),
            attention_score=narrative.attention_score,
            strength=narrative.strength,
            velocity=narrative.velocity,
            momentum=narrative.momentum,
            confidence=narrative.confidence,
            first_seen=narrative.first_seen,
            last_seen=narrative.last_seen,
            updated_at=narrative.updated_at,
            uncertainty_reasons=list(narrative.uncertainty_reasons),
            contradiction_signals=list(narrative.contradiction_signals),
            override_state=narrative.override_state.value,
            identity_embedding=list(embedding.vector) if embedding is not None else None,
            embedding_model=embedding.embedding_model if embedding is not None else None,
            embedding_version=(
                embedding.embedding_version if embedding is not None else None
            ),
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, narrative_id: UUID) -> Narrative | None:
        row = self._session.get(NarrativeModel, narrative_id)
        return _to_domain(row) if row is not None else None

    def get_by_canonical_key(self, canonical_key: str) -> Narrative | None:
        row = self._session.execute(
            select(NarrativeModel).where(
                NarrativeModel.canonical_key == canonical_key
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row is not None else None
