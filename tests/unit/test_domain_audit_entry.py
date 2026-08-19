"""Unit tests for AuditEntry invariants (S001-T009) - no database."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from moj_projekt.domain.audit_entry import AuditEntry

_TIMESTAMP = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _make_entry(**overrides: object) -> AuditEntry:
    defaults: dict[str, object] = dict(
        actor="trader",
        action="reject_event_assignment",
        target_id="narrative_event:1234",
        timestamp=_TIMESTAMP,
        reason="Not the same economic mechanism.",
    )
    defaults.update(overrides)
    return AuditEntry(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize("attr_name", ["actor", "action", "target_id", "reason"])
def test_audit_entry_rejects_empty_required_string_fields(attr_name: str) -> None:
    with pytest.raises(ValueError, match=attr_name):
        _make_entry(**{attr_name: "  "})


def test_audit_entry_accepts_a_valid_entry() -> None:
    entry = _make_entry(previous_value={"status": "proposed"}, new_value={"status": "rejected"})

    assert entry.previous_value == {"status": "proposed"}
    assert entry.new_value == {"status": "rejected"}
