"""enable pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-08-18

This is the Alembic baseline: an otherwise empty schema whose only job is to
make the `vector` type available before any migration needs it
(ADR-0014). Entity tables land in later migrations (S001-T006 onward).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
