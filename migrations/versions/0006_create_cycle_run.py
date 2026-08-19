"""create cycle_runs table

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-18

Adds the ``cycle_runs`` table (S001-T011): the audit record of one 5-minute
processing cycle (ADR-0004, ADR-0011). ``status`` stores the
``CycleRunStatus`` IntEnum ordinal (1=RUNNING, 2=SUCCEEDED, 3=FAILED),
mirroring how the ``0002`` migration stored ``documents.processing_status``.

**Overlap prevention, belt and suspenders (ADR-0011):** "the cycle's
idempotency is not allowed to depend on the scheduler behaving correctly."
The application-level guard is
:meth:`~moj_projekt.domain.repositories.CycleRunRepository.get_running`,
checked by the orchestration function before starting a new run. This
migration adds the independent database-level backstop: a partial unique
index on a constant expression, restricted to rows where
``status = 1`` (RUNNING) - the standard Postgres idiom for "at most one row
may satisfy this predicate," used here the same way ``narrative_episodes``'
``EXCLUDE USING gist`` (migration ``0004``) backs the "no overlapping
episodes" domain invariant with a database constraint rather than relying
solely on application logic.

Three CHECK constraints mirror the ``CycleRun.__post_init__`` invariants so
a raw INSERT/UPDATE that bypasses the domain constructor cannot violate
them either (same defense-in-depth pattern as ``ck_llm_runs_no_latest_alias``
in migration ``0005``):

- ``status`` is one of the three known ``CycleRunStatus`` ordinals;
- ``ended_at`` is set if and only if ``status`` is terminal (not RUNNING),
  and when set, ``ended_at >= started_at``;
- ``failure_reason`` is set if and only if ``status`` is FAILED.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# CycleRunStatus ordinals (moj_projekt.domain.cycle_run.CycleRunStatus) -
# kept in sync with the domain enum by convention, the same way this
# project already relies on ProcessingStatus's ordinals elsewhere.
_STATUS_RUNNING = 1
_STATUS_SUCCEEDED = 2
_STATUS_FAILED = 3

_SINGLE_RUNNING_INDEX = "uq_cycle_runs_single_running"


def upgrade() -> None:
    op.create_table(
        "cycle_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False),
        sa.Column(
            "stage_outcomes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "source_outcomes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_STATUS_RUNNING}, {_STATUS_SUCCEEDED}, {_STATUS_FAILED})",
            name="ck_cycle_runs_status_valid",
        ),
        sa.CheckConstraint(
            f"(status = {_STATUS_RUNNING} AND ended_at IS NULL) OR "
            f"(status != {_STATUS_RUNNING} AND ended_at IS NOT NULL)",
            name="ck_cycle_runs_ended_at_matches_status",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_cycle_runs_ended_after_started",
        ),
        sa.CheckConstraint(
            f"(status = {_STATUS_FAILED} AND failure_reason IS NOT NULL "
            "AND trim(failure_reason) <> '') OR "
            f"(status != {_STATUS_FAILED} AND failure_reason IS NULL)",
            name="ck_cycle_runs_failure_reason_matches_status",
        ),
    )

    # At most one RUNNING row at a time (see module docstring). All rows
    # matching the partial predicate index the same constant `TRUE`, so a
    # second one violates the unique index.
    op.execute(
        f"""
        CREATE UNIQUE INDEX {_SINGLE_RUNNING_INDEX}
        ON cycle_runs ((true))
        WHERE status = {_STATUS_RUNNING}
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_SINGLE_RUNNING_INDEX}")
    op.drop_table("cycle_runs")
