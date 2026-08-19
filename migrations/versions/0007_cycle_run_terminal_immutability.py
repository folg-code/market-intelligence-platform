"""reject updates to already-terminal cycle_runs

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-19

Adds a ``BEFORE UPDATE`` trigger on ``cycle_runs`` so a row that has already
reached a terminal status (``SUCCEEDED`` or ``FAILED``) cannot be written
again (PRB-004, S002-T004). The legitimate ``RUNNING`` -> terminal
transition is still permitted: the trigger only inspects ``OLD.status``.

This is the same defense-in-depth pattern as the immutability /
append-only triggers on ``documents`` (migration ``0002``),
``evidence_packs`` (``0003``), and ``llm_runs`` / ``audit_entries``
(``0005``), underneath the domain constructor which already rejects
:meth:`~moj_projekt.domain.cycle_run.CycleRun.finish` on an already-terminal
run. Retry/resume semantics are out of scope; this migration only freezes
the row once it has left ``RUNNING``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# CycleRunStatus.RUNNING ordinal - kept in sync with the domain enum by
# convention, matching migration ``0006``.
_STATUS_RUNNING = 1

_TERMINAL_IMMUTABILITY_FUNCTION = "cycle_runs_reject_terminal_update"
_TERMINAL_IMMUTABILITY_TRIGGER = "cycle_runs_reject_terminal_update_trigger"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {_TERMINAL_IMMUTABILITY_FUNCTION}()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status != {_STATUS_RUNNING} THEN
                RAISE EXCEPTION
                    'cycle_runs: terminal rows cannot be updated '
                    '(id=%, status=%)',
                    OLD.id, OLD.status;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_TERMINAL_IMMUTABILITY_TRIGGER}
        BEFORE UPDATE ON cycle_runs
        FOR EACH ROW
        EXECUTE FUNCTION {_TERMINAL_IMMUTABILITY_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_TERMINAL_IMMUTABILITY_TRIGGER} ON cycle_runs")
    op.execute(f"DROP FUNCTION IF EXISTS {_TERMINAL_IMMUTABILITY_FUNCTION}()")
