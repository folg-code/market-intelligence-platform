"""create narrative_instrument_impacts, alerts, llm_runs, audit_entries tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-18

Adds the last MVP entities from DOMAIN_MODEL.md section 3 (S001-T009):

- ``llm_runs`` - the append-only LLM reproducibility record (ADR-0007).
  Created first in this migration so ``narrative_events.llm_run_id`` and
  ``narrative_instrument_impacts.llm_run_id`` can reference it.
- ``audit_entries`` - the append-only human-side audit trail (ADR-0009).
- ``narrative_instrument_impacts`` - one **current** assessment per
  ``(narrative_id, instrument)`` pair (unique constraint), not a versioned
  history - see the domain type's module docstring for the judgment call.
  A CHECK constraint mirrors the domain-level rule that a non-neutral
  ``direction`` requires a non-empty ``rationale`` and non-empty
  ``evidence_refs`` (ADR-0006).
- ``alerts`` - deduplicated per ``(narrative_id, alert_type, trigger_key)``
  so a repeated cycle does not re-fire the same alert.

Also adds the foreign key from ``narrative_events.llm_run_id`` to
``llm_runs.id``: the S001-T008 migration created that column without a
foreign key because ``llm_runs`` did not exist yet (reviewer note on
S001-T008, carried forward here so it is not dropped).

**Append-only enforcement:** ``llm_runs`` and ``audit_entries`` each get a
database-level trigger that rejects every UPDATE and DELETE (ADR-0007,
ADR-0009) - this is defense in depth underneath the repository layer, which
exposes no update/delete method at all, matching the immutability pattern
already established for ``documents`` (S001-T006, update-limited) and
``evidence_packs`` (S001-T007, update-rejected). Unlike ``evidence_packs``,
these two tables also reject DELETE, because "append-only" here is stated
as a stronger, explicit invariant in both ADR-0007 and ADR-0009 (and in the
S001-T009 acceptance criteria) than the "never mutated in place" language
used for EvidencePack.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_LLM_RUNS_APPEND_ONLY_FUNCTION = "llm_runs_reject_update_delete"
_LLM_RUNS_APPEND_ONLY_TRIGGER = "llm_runs_append_only_trigger"
_AUDIT_ENTRIES_APPEND_ONLY_FUNCTION = "audit_entries_reject_update_delete"
_AUDIT_ENTRIES_APPEND_ONLY_TRIGGER = "audit_entries_append_only_trigger"


def upgrade() -> None:
    op.create_table(
        "llm_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("system_prompt_version", sa.String(length=50), nullable=False),
        sa.Column("input_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "input_reference_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("output_schema_version", sa.String(length=50), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=False),
        sa.Column(
            "parsed_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("validation_status", sa.String(length=20), nullable=False),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "temperature", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column(
            "inference_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "token_usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "latency", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_array_length(input_reference_ids) > 0",
            name="ck_llm_runs_input_reference_ids_not_empty",
        ),
        sa.CheckConstraint(
            "temperature >= 0.0", name="ck_llm_runs_temperature_non_negative"
        ),
        sa.CheckConstraint(
            "latency >= 0.0", name="ck_llm_runs_latency_non_negative"
        ),
    )

    op.create_table(
        "audit_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=200), nullable=False),
        sa.Column(
            "previous_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "new_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_audit_entries_target_id", "audit_entries", ["target_id"]
    )

    op.create_table(
        "narrative_instrument_impacts",
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
        sa.Column("instrument", sa.String(length=10), nullable=False),
        sa.Column("relevance", sa.Boolean(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("horizon", sa.String(length=20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "impact_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="proposed"
        ),
        sa.Column(
            "llm_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("llm_runs.id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "narrative_id",
            "instrument",
            name="uq_narrative_instrument_impacts_narrative_instrument",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_narrative_instrument_impacts_confidence_range",
        ),
        sa.CheckConstraint(
            "direction = 'neutral' OR "
            "(rationale <> '' AND jsonb_array_length(evidence_refs) > 0)",
            name="ck_narrative_instrument_impacts_non_neutral_requires_evidence",
        ),
    )

    op.create_table(
        "alerts",
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
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("trigger_key", sa.String(length=200), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "narrative_id",
            "alert_type",
            "trigger_key",
            name="uq_alerts_narrative_type_trigger",
        ),
    )

    # S001-T008 could not add this FK when narrative_events was created,
    # because llm_runs did not exist yet - add it now (carried-forward
    # reviewer note on S001-T008).
    op.create_foreign_key(
        "fk_narrative_events_llm_run_id_llm_runs",
        "narrative_events",
        "llm_runs",
        ["llm_run_id"],
        ["id"],
    )

    # Append-only enforcement: reject every UPDATE and DELETE (ADR-0007).
    op.execute(
        f"""
        CREATE FUNCTION {_LLM_RUNS_APPEND_ONLY_FUNCTION}()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'llm_runs: rows are append-only, % is not permitted (id=%)',
                TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_LLM_RUNS_APPEND_ONLY_TRIGGER}
        BEFORE UPDATE OR DELETE ON llm_runs
        FOR EACH ROW
        EXECUTE FUNCTION {_LLM_RUNS_APPEND_ONLY_FUNCTION}();
        """
    )

    # Append-only enforcement: reject every UPDATE and DELETE (ADR-0009).
    op.execute(
        f"""
        CREATE FUNCTION {_AUDIT_ENTRIES_APPEND_ONLY_FUNCTION}()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_entries: rows are append-only, % is not permitted (id=%)',
                TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_AUDIT_ENTRIES_APPEND_ONLY_TRIGGER}
        BEFORE UPDATE OR DELETE ON audit_entries
        FOR EACH ROW
        EXECUTE FUNCTION {_AUDIT_ENTRIES_APPEND_ONLY_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(
        f"DROP TRIGGER IF EXISTS {_AUDIT_ENTRIES_APPEND_ONLY_TRIGGER} ON audit_entries"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {_AUDIT_ENTRIES_APPEND_ONLY_FUNCTION}()")
    op.execute(
        f"DROP TRIGGER IF EXISTS {_LLM_RUNS_APPEND_ONLY_TRIGGER} ON llm_runs"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {_LLM_RUNS_APPEND_ONLY_FUNCTION}()")

    op.drop_constraint(
        "fk_narrative_events_llm_run_id_llm_runs",
        "narrative_events",
        type_="foreignkey",
    )
    op.drop_table("alerts")
    op.drop_table("narrative_instrument_impacts")
    op.drop_index("ix_audit_entries_target_id", table_name="audit_entries")
    op.drop_table("audit_entries")
    op.drop_table("llm_runs")
