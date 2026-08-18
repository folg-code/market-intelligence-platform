"""create narrative tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-18

Adds the Narrative Intelligence bounded context's tables (DOMAIN_MODEL.md
section 3, S001-T008):

- ``narratives`` - the product's central object, identified by the unique
  ``canonical_key`` (ADR-0001), including the ``identity_embedding`` vector
  column plus ``embedding_model``/``embedding_version`` (ADR-0014). A CHECK
  constraint keeps those three columns all-null or all-set together.
- ``narrative_episodes`` - scoped to one Narrative; an ``EXCLUDE`` constraint
  (requires the ``btree_gist`` extension) rejects any two episodes of the
  same Narrative whose active periods overlap.
- ``narrative_events`` - the (narrative, event) assignment, composite
  primary key; ``llm_run_id`` has no foreign key yet (``llm_runs`` lands in
  S001-T009).
- ``narrative_relations`` - typed relation between two Narratives; a CHECK
  constraint rejects self-relations, a unique constraint rejects duplicate
  ``(source, target, type)`` triples.

Also adds the foreign key from ``evidence_packs.narrative_id`` to
``narratives.id``: the S001-T007 migration created that column and its
``uq_evidence_packs_narrative_version`` unique constraint before this table
existed, so the FK could not be added then (reviewer note on S001-T007,
carried forward here).

**Embedding dimension placeholder:** ``NARRATIVE_EMBEDDING_DIMENSION`` below
is a documented placeholder, not a decision - the embedding model source is
still open (ADR-0014 Follow-up; docs/planning/CURRENT_STATUS.md "Open
decisions"). 384 matches common small local open-weight sentence-embedding
models (e.g. sentence-transformers/all-MiniLM-L6-v2,
BAAI/bge-small-en-v1.5), the direction ADR-0014 leans toward ("no vendor, no
per-token cost"). Changing the embedding model later means a new migration
that alters this column's dimension, plus a full re-embedding pass -
`identity_embedding` is derived data, never identity (ADR-0001, ADR-0014),
so this is acceptable and not a data-loss event.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# See the module docstring "Embedding dimension placeholder" note above.
NARRATIVE_EMBEDDING_DIMENSION = 384

_EPISODE_NO_OVERLAP_CONSTRAINT = "ex_narrative_episodes_no_overlap"


def upgrade() -> None:
    # Required for the UUID equality operator class used by the
    # narrative_episodes EXCLUDE constraint below.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "narratives",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("canonical_key", sa.String(length=200), nullable=False),
        sa.Column("display_title", sa.Text(), nullable=False),
        sa.Column("validity_status", sa.String(length=20), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), nullable=False),
        sa.Column("economic_mechanism", sa.Text(), nullable=False),
        sa.Column("market_interpretation", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "topics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "attention_score", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column("strength", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("velocity", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("momentum", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column(
            "confidence", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "uncertainty_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "contradiction_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "override_state",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "identity_embedding",
            Vector(NARRATIVE_EMBEDDING_DIMENSION),
            nullable=True,
        ),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("embedding_version", sa.String(length=50), nullable=True),
        sa.UniqueConstraint("canonical_key", name="uq_narratives_canonical_key"),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_narratives_confidence_range",
        ),
        sa.CheckConstraint(
            "first_seen <= last_seen",
            name="ck_narratives_first_seen_before_last_seen",
        ),
        sa.CheckConstraint(
            "(identity_embedding IS NULL AND embedding_model IS NULL "
            "AND embedding_version IS NULL) "
            "OR (identity_embedding IS NOT NULL AND embedding_model IS NOT NULL "
            "AND embedding_version IS NOT NULL)",
            name="ck_narratives_embedding_all_or_nothing",
        ),
    )

    op.create_table(
        "narrative_episodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "narrative_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("narratives.id"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_narrative_episodes_ended_after_started",
        ),
    )
    op.create_index(
        "ix_narrative_episodes_narrative_id",
        "narrative_episodes",
        ["narrative_id"],
    )
    # No two episodes of the same Narrative may have overlapping active
    # periods (DOMAIN_MODEL.md "Episodes of one Narrative do not overlap in
    # time"). An open episode (ended_at IS NULL) is treated as ongoing
    # ("infinity") for overlap purposes.
    op.execute(
        f"""
        ALTER TABLE narrative_episodes
        ADD CONSTRAINT {_EPISODE_NO_OVERLAP_CONSTRAINT}
        EXCLUDE USING gist (
            narrative_id WITH =,
            tstzrange(started_at, COALESCE(ended_at, 'infinity'::timestamptz), '[]')
                WITH &&
        )
        """
    )

    op.create_table(
        "narrative_events",
        sa.Column(
            "narrative_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("narratives.id"),
            primary_key=True,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id"),
            primary_key=True,
        ),
        sa.Column("assignment_rationale", sa.Text(), nullable=False),
        sa.Column("assignment_confidence", sa.Float(), nullable=False),
        sa.Column(
            "assignment_status",
            sa.String(length=20),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("llm_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "candidate_shortlist",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "override_state",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
        sa.CheckConstraint(
            "assignment_confidence >= 0.0 AND assignment_confidence <= 1.0",
            name="ck_narrative_events_confidence_range",
        ),
    )

    op.create_table(
        "narrative_relations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_narrative_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("narratives.id"),
            nullable=False,
        ),
        sa.Column(
            "target_narrative_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("narratives.id"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=20), nullable=False),
        sa.UniqueConstraint(
            "source_narrative_id",
            "target_narrative_id",
            "relation_type",
            name="uq_narrative_relations_source_target_type",
        ),
        sa.CheckConstraint(
            "source_narrative_id != target_narrative_id",
            name="ck_narrative_relations_no_self_relation",
        ),
    )

    # S001-T007 could not add this FK when evidence_packs was created,
    # because narratives did not exist yet - add it now (carried-forward
    # reviewer note on S001-T007).
    op.create_foreign_key(
        "fk_evidence_packs_narrative_id_narratives",
        "evidence_packs",
        "narratives",
        ["narrative_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evidence_packs_narrative_id_narratives",
        "evidence_packs",
        type_="foreignkey",
    )
    op.drop_table("narrative_relations")
    op.drop_table("narrative_events")
    op.execute(
        f"ALTER TABLE narrative_episodes DROP CONSTRAINT "
        f"{_EPISODE_NO_OVERLAP_CONSTRAINT}"
    )
    op.drop_index(
        "ix_narrative_episodes_narrative_id", table_name="narrative_episodes"
    )
    op.drop_table("narrative_episodes")
    op.drop_table("narratives")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
