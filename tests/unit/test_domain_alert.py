"""Unit tests for Alert invariants (S001-T009) - no database."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from moj_projekt.domain.alert import Alert
from moj_projekt.domain.enums import AlertType

_CREATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def test_alert_rejects_empty_trigger_key() -> None:
    with pytest.raises(ValueError, match="trigger_key"):
        Alert(
            narrative_id=uuid4(),
            alert_type=AlertType.EMERGING_NARRATIVE,
            trigger_key="  ",
            created_at=_CREATED_AT,
        )


def test_alert_accepts_a_valid_trigger_key() -> None:
    alert = Alert(
        narrative_id=uuid4(),
        alert_type=AlertType.CONFIRMED_NARRATIVE,
        trigger_key="event:1234",
        created_at=_CREATED_AT,
    )

    assert alert.alert_type is AlertType.CONFIRMED_NARRATIVE
    assert alert.details == {}
