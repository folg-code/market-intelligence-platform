"""create event and evidence_pack tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-18

Adds the Event Extraction and Evidence & Trust bounded contexts' tables
(DOMAIN_MODEL.md section 3, S001-T007):

- ``events`` - ``extracted_facts`` and ``source_claims`` are separate JSONB
  columns, never merged (ADR-0008); ``source_ids`` is a non-empty JSONB
  array of Document ids, enforced by a CHECK constraint.
- ``evidence_packs`` - a versioned, immutable snapshot keyed by
  ``(narrative_id, evidence_version)`` (ADR-0003). ``narrative_id`` has no
  foreign key yet - the ``narratives`` table lands in S001-T008; add the
  constraint in that migration. ``independent_source_count <= source_count``
  is enforced by a CHECK constraint. A database-level trigger rejects every
  UPDATE - unlike Document, no column on an EvidencePack may ever change
  after insert; a rebuild is always a new row.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_IMMUTABILITY_TRIGGER_FUNCTION = "evidence_packs_enforce_immutability"
_IMMUTABILITY_TRIGGER = "evidence_packs_enforce_immutability_trigger"


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            "extracted_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_claims",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "jsonb_array_length(source_ids) > 0",
            name="ck_events_source_ids_not_empty",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_events_confidence_range",
        ),
    )

    op.create_table(
        "evidence_packs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("narrative_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_version", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("independent_source_count", sa.Integer(), nullable=False),
        sa.Column("source_diversity", sa.Integer(), nullable=False),
        sa.Column(
            "supporting_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "contradicting_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "top_supporting_events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "key_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "strongest_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "dissenting_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "official_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "media_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "social_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "market_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "missing_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence_gaps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.UniqueConstraint(
            "narrative_id",
            "evidence_version",
            name="uq_evidence_packs_narrative_version",
        ),
        sa.CheckConstraint(
            "independent_source_count <= source_count",
            name="ck_evidence_packs_independent_le_source_count",
        ),
        sa.CheckConstraint(
            "evidence_version >= 1",
            name="ck_evidence_packs_version_positive",
        ),
    )
    op.create_index(
        "ix_evidence_packs_narrative_id", "evidence_packs", ["narrative_id"]
    )

    # Immutable snapshot: no column may change after insert. A rebuild is
    # always a new row with a higher evidence_version (ADR-0003).
    op.execute(
        f"""
        CREATE FUNCTION {_IMMUTABILITY_TRIGGER_FUNCTION}()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'evidence_packs: rows are immutable, rebuild as a new '
                'evidence_version instead (id=%)', OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_IMMUTABILITY_TRIGGER}
        BEFORE UPDATE ON evidence_packs
        FOR EACH ROW
        EXECUTE FUNCTION {_IMMUTABILITY_TRIGGER_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_IMMUTABILITY_TRIGGER} ON evidence_packs")
    op.execute(f"DROP FUNCTION IF EXISTS {_IMMUTABILITY_TRIGGER_FUNCTION}()")
    op.drop_index("ix_evidence_packs_narrative_id", table_name="evidence_packs")
    op.drop_table("evidence_packs")
    op.drop_table("events")
