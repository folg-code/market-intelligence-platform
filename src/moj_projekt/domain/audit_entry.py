"""``AuditEntry`` - the append-only human-side audit trail
(DOMAIN_MODEL.md section 3, "Governance & Audit"; DOMAIN_MODEL.md section
6; ADR-0009).

Pure domain representation: no persistence concern, no infrastructure
import. Every human correction writes exactly one ``AuditEntry`` -
``previous_value`` is the state actually replaced, not a reconstruction
(ADR-0009). Nothing in this sprint's scope writes a real AuditEntry (no
override UI exists yet) - this type exists so the append-only record has a
stable shape to write into once overrides are built.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

__all__ = ["AuditEntry"]


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One append-only record of a human correction.

    ``previous_value``/``new_value`` are free-form snapshots of the state
    actually replaced/written - their shape depends on ``target_id``'s kind
    (Narrative, NarrativeEvent assignment, ...), which is not fixed here.
    """

    actor: str
    action: str
    target_id: str
    timestamp: datetime
    reason: str
    previous_value: Mapping[str, Any] = field(default_factory=dict)
    new_value: Mapping[str, Any] = field(default_factory=dict)
    id: UUID | None = None

    def __post_init__(self) -> None:
        for attr_name in ("actor", "action", "target_id", "reason"):
            value = getattr(self, attr_name)
            if not value.strip():
                raise ValueError(f"AuditEntry.{attr_name} must not be empty")
