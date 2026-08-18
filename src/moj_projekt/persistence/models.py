"""SQLAlchemy ORM models for the Ingestion, Event Extraction, and Evidence &
Trust bounded contexts.

Maps :class:`~moj_projekt.domain.source.Source`,
:class:`~moj_projekt.domain.document.Document`,
:class:`~moj_projekt.domain.event.Event`, and
:class:`~moj_projekt.domain.evidence_pack.EvidencePack` to PostgreSQL
tables. Schema changes for these tables live exclusively in ``migrations/``
(Alembic) - this module declares the mapping, it never calls
``Base.metadata.create_all()`` (root ``CLAUDE.md``, ADR-0013).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "DocumentModel", "EventModel", "EvidencePackModel", "SourceModel"]


class Base(DeclarativeBase):
    pass


class SourceModel(Base):
    """Row for a :class:`~moj_projekt.domain.source.Source`.

    ``key`` is the primary key: Source identity is the stable source key,
    not a surrogate id (DOMAIN_MODEL.md section 3).
    """

    __tablename__ = "sources"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    publisher: Mapped[str] = mapped_column(String(200), nullable=False)
    endpoint_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DocumentModel(Base):
    """Row for a :class:`~moj_projekt.domain.document.Document`.

    ``natural_key`` is ``source_native_id`` when present, else ``url`` -
    computed by the repository at write time, matching
    ``Document.natural_key``. Together with ``source_key`` and
    ``published_at`` it forms the deduplication natural key
    (DOMAIN_MODEL.md section 3); the unique constraint enforcing it and the
    immutability trigger both live in the migration, not here.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(
        String(100), ForeignKey("sources.key"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_native_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    natural_key: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    processing_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class EventModel(Base):
    """Row for an :class:`~moj_projekt.domain.event.Event`.

    ``extracted_facts`` and ``source_claims`` are separate JSONB columns -
    no code path merges them into one structure (ADR-0008). ``source_ids``
    is a JSONB array of Document ids rather than an association table
    (ADR-0005: "keep uncertain shapes in JSONB; do not add relationships no
    invariant requires") - the non-empty invariant is enforced at the
    domain layer and by a database CHECK constraint from the migration, not
    by a foreign key on each element.
    """

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    entities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    extracted_facts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_claims: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class EvidencePackModel(Base):
    """Row for one versioned :class:`~moj_projekt.domain.evidence_pack.EvidencePack`
    snapshot.

    Identity is ``(narrative_id, evidence_version)``; the row is never
    updated after insert - the immutability trigger from the migration
    rejects every UPDATE (ADR-0003: "never mutated in place; a rebuild
    produces a new evidence_version"). ``narrative_id`` has no foreign key
    yet - the ``narratives`` table lands in S001-T008; add the constraint
    then.
    """

    __tablename__ = "evidence_packs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    narrative_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    evidence_version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    independent_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_diversity: Mapped[int] = mapped_column(Integer, nullable=False)
    supporting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    contradicting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    top_supporting_events: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    key_facts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    strongest_sources: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    dissenting_sources: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    official_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    media_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    social_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    market_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    missing_evidence: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    evidence_gaps: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
