"""create source and document tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-18

Adds the Ingestion bounded context's two tables (DOMAIN_MODEL.md section 3):

- ``sources`` - keyed by the stable source key, one tier per source.
- ``documents`` - deduplicated by (source_key, natural_key, published_at),
  where ``natural_key`` is the source-native id when present, else the URL
  (S001-T006).

A database-level trigger enforces Document immutability after collection:
any UPDATE that changes ``id`` or any column other than
``processing_status``, or that moves ``processing_status`` backwards, is
rejected. This is defense in depth underneath the repository, which exposes
no "update content" method at all.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_IMMUTABILITY_TRIGGER_FUNCTION = "documents_enforce_immutability"
_IMMUTABILITY_TRIGGER = "documents_enforce_immutability_trigger"


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=False),
        sa.Column(
            "endpoint_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_key",
            sa.String(length=100),
            sa.ForeignKey("sources.key"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_native_id", sa.Text(), nullable=True),
        sa.Column("natural_key", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("processing_status", sa.SmallInteger(), nullable=False),
        sa.UniqueConstraint(
            "source_key",
            "natural_key",
            "published_at",
            name="uq_documents_dedupe_key",
        ),
    )
    op.create_index("ix_documents_source_key", "documents", ["source_key"])

    # Immutability: only `processing_status` may change after collection,
    # and only forward. Every other column, including the `id` primary key,
    # and any regression of `processing_status`, raises.
    op.execute(
        f"""
        CREATE FUNCTION {_IMMUTABILITY_TRIGGER_FUNCTION}()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.source_key IS DISTINCT FROM OLD.source_key
                OR NEW.source_type IS DISTINCT FROM OLD.source_type
                OR NEW.url IS DISTINCT FROM OLD.url
                OR NEW.source_native_id IS DISTINCT FROM OLD.source_native_id
                OR NEW.natural_key IS DISTINCT FROM OLD.natural_key
                OR NEW.published_at IS DISTINCT FROM OLD.published_at
                OR NEW.collected_at IS DISTINCT FROM OLD.collected_at
                OR NEW.title IS DISTINCT FROM OLD.title
                OR NEW.content IS DISTINCT FROM OLD.content
                OR NEW.language IS DISTINCT FROM OLD.language
                OR NEW.raw_metadata IS DISTINCT FROM OLD.raw_metadata
            THEN
                RAISE EXCEPTION
                    'documents: collected content is immutable (id=%)', OLD.id;
            END IF;

            IF NEW.processing_status < OLD.processing_status THEN
                RAISE EXCEPTION
                    'documents: processing_status cannot regress (id=%, % -> %)',
                    OLD.id, OLD.processing_status, NEW.processing_status;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_IMMUTABILITY_TRIGGER}
        BEFORE UPDATE ON documents
        FOR EACH ROW
        EXECUTE FUNCTION {_IMMUTABILITY_TRIGGER_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_IMMUTABILITY_TRIGGER} ON documents")
    op.execute(f"DROP FUNCTION IF EXISTS {_IMMUTABILITY_TRIGGER_FUNCTION}()")
    op.drop_index("ix_documents_source_key", table_name="documents")
    op.drop_table("documents")
    op.drop_table("sources")
