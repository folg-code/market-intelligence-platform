"""``Alert`` - an in-app notification of a material change
(DOMAIN_MODEL.md section 3, "Delivery"; ADR-0004, ADR-0005).

Pure domain representation: no persistence concern, no infrastructure
import. Identity is a system id, deduplicated per ``(narrative_id,
alert_type, trigger_key)`` so a repeated cycle does not re-fire the same
alert (DOMAIN_MODEL.md). ``trigger_key`` identifies "the change that
triggered" the alert (e.g. an event id, or a stable description of a
narrative-state transition) - its exact shape is decided by whichever
future task generates alerts; this type only requires it to be present and
non-empty, matching the dedup key the domain model specifies. ``details``
carries whatever free-form context about the trigger that generation logic
wants to show later - an uncertain shape kept in JSONB rather than
pre-decided here (ADR-0005 risk mitigation: "keep uncertain shapes in
JSONB; do not add relationships no invariant requires").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from moj_projekt.domain.enums import AlertType

__all__ = ["Alert"]


@dataclass(frozen=True, slots=True)
class Alert:
    """One in-app alert, generated inside the 5-minute cycle (ADR-0004)."""

    narrative_id: UUID
    alert_type: AlertType
    trigger_key: str
    created_at: datetime
    details: Mapping[str, Any] = field(default_factory=dict)
    id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.trigger_key.strip():
            raise ValueError("Alert.trigger_key must not be empty")
