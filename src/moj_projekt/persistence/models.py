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

from pgvector.sqlalchemy import Vector
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

__all__ = [
    "AlertModel",
    "AuditEntryModel",
    "Base",
    "CycleRunModel",
    "DocumentModel",
    "EventModel",
    "EvidencePackModel",
    "LLMRunModel",
    "NarrativeEpisodeModel",
    "NarrativeEventModel",
    "NarrativeInstrumentImpactModel",
    "NarrativeModel",
    "NarrativeRelationModel",
    "SourceModel",
]

# Placeholder embedding dimension (S001-T008). The embedding model source is
# still an open decision (ADR-0014 Follow-up, docs/planning/CURRENT_STATUS.md
# "Open decisions"); this value matches common small local open-weight
# sentence-embedding models (e.g. sentence-transformers/all-MiniLM-L6-v2,
# BAAI/bge-small-en-v1.5 - both 384 dimensions), which is the direction
# ADR-0014 leans ("no vendor, no per-token cost"). Changing the embedding
# model later means a migration that alters this column's dimension plus a
# full re-embedding pass, not a data-loss event - `identity_embedding` is
# derived data, never identity (ADR-0001, ADR-0014).
NARRATIVE_EMBEDDING_DIMENSION = 384


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
    produces a new evidence_version"). ``narrative_id`` references
    ``narratives.id`` - the foreign key was added in the S001-T008
    migration once that table existed (it could not be added when this
    table was first created in S001-T007).
    """

    __tablename__ = "evidence_packs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), nullable=False
    )
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


class NarrativeModel(Base):
    """Row for a :class:`~moj_projekt.domain.narrative.Narrative`.

    ``canonical_key`` carries the unique constraint - identity is semantic,
    not the surrogate ``id`` (ADR-0001). ``identity_embedding`` is a
    ``vector(NARRATIVE_EMBEDDING_DIMENSION)`` column - see the module-level
    comment on that constant for the placeholder dimension rationale. It is
    nullable together with ``embedding_model``/``embedding_version`` (a
    CHECK constraint from the migration enforces all-or-nothing) - a
    Narrative with no embedding yet is fully valid (ADR-0014).
    """

    __tablename__ = "narratives"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_key: Mapped[str] = mapped_column(String(200), nullable=False)
    display_title: Mapped[str] = mapped_column(Text, nullable=False)
    validity_status: Mapped[str] = mapped_column(String(20), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False)
    economic_mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    market_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    entities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    attention_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    velocity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    momentum: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    uncertainty_reasons: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    contradiction_signals: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    override_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )
    identity_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(NARRATIVE_EMBEDDING_DIMENSION), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(50), nullable=True)


class NarrativeEpisodeModel(Base):
    """Row for a :class:`~moj_projekt.domain.narrative_episode.NarrativeEpisode`.

    "Episodes of one Narrative do not overlap in time" is enforced by an
    ``EXCLUDE`` constraint from the migration, not here - it is a cross-row
    invariant.
    """

    __tablename__ = "narrative_episodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class NarrativeEventModel(Base):
    """Row for a :class:`~moj_projekt.domain.narrative_event.NarrativeEvent`
    assignment.

    Identity is the composite primary key ``(narrative_id, event_id)``.
    ``llm_run_id`` references ``llm_runs.id`` - the foreign key was added
    in the S001-T009 migration once that table existed (it could not be
    added when this table was first created in S001-T008).
    """

    __tablename__ = "narrative_events"

    narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), primary_key=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id"), primary_key=True
    )
    assignment_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    assignment_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    assignment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="proposed"
    )
    llm_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("llm_runs.id"), nullable=True
    )
    candidate_shortlist: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    override_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )


class NarrativeRelationModel(Base):
    """Row for a :class:`~moj_projekt.domain.narrative_relation.NarrativeRelation`.

    Identity is ``(source_narrative_id, target_narrative_id, relation_type)``
    - enforced by a unique constraint from the migration. Self-relations are
    rejected structurally in the domain type and by a CHECK constraint here.
    """

    __tablename__ = "narrative_relations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), nullable=False
    )
    target_narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False)


class LLMRunModel(Base):
    """Row for an :class:`~moj_projekt.domain.llm_run.LLMRun` (S001-T009).

    Append-only: the ``llm_runs_append_only_trigger`` from the migration
    rejects every UPDATE and DELETE (ADR-0007).
    """

    __tablename__ = "llm_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    input_reference_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_errors: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    inference_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    token_usage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    latency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuditEntryModel(Base):
    """Row for an :class:`~moj_projekt.domain.audit_entry.AuditEntry`
    (S001-T009).

    Append-only: the ``audit_entries_append_only_trigger`` from the
    migration rejects every UPDATE and DELETE (ADR-0009).
    """

    __tablename__ = "audit_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    new_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class CycleRunModel(Base):
    """Row for a :class:`~moj_projekt.domain.cycle_run.CycleRun` (S001-T011).

    ``status`` is stored as the underlying ``CycleRunStatus`` ordinal
    (``SmallInteger``), mirroring how ``Document.processing_status`` stores
    its IntEnum. ``stage_outcomes``/``source_outcomes`` are separate JSONB
    columns, each keyed by stage/source name, consistent with how other
    JSONB map/list columns are modelled elsewhere in this file. A partial
    unique index from the migration (not expressible here) enforces "at
    most one RUNNING row" at the database level too, mirroring
    ``narrative_episodes``'s EXCLUDE-constraint pattern of backing a
    cross-row domain invariant with a DB constraint. A ``BEFORE UPDATE``
    trigger from migration ``0007`` rejects any write to a row that is
    already terminal (PRB-004).
    """

    __tablename__ = "cycle_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stage_outcomes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    source_outcomes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class NarrativeInstrumentImpactModel(Base):
    """Row for a
    :class:`~moj_projekt.domain.instrument_impact.NarrativeInstrumentImpact`
    (S001-T009).

    Identity is ``(narrative_id, instrument)`` - the unique constraint from
    the migration backs the "one current assessment per pair" invariant and
    the repository's upsert semantics (see the domain type's module
    docstring for the versioning judgment call).
    """

    __tablename__ = "narrative_instrument_impacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), nullable=False
    )
    instrument: Mapped[str] = mapped_column(String(10), nullable=False)
    relevance: Mapped[bool] = mapped_column(Boolean, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    horizon: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    impact_channels: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="proposed"
    )
    llm_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("llm_runs.id"), nullable=True
    )


class AlertModel(Base):
    """Row for an :class:`~moj_projekt.domain.alert.Alert` (S001-T009).

    Deduplicated per ``(narrative_id, alert_type, trigger_key)`` by the
    unique constraint from the migration - a repeated cycle does not
    re-fire the same alert (DOMAIN_MODEL.md).
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_key: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
