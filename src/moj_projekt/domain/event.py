"""``Event`` - a real-world development extracted from one or more Documents
(DOMAIN_MODEL.md section 3, "Event Extraction").

Pure domain representation: no persistence concern, no infrastructure
import. ``extracted_facts`` and ``source_claims`` are kept as two distinct
fields - the extractor never promotes a claim to a fact, and this type has
no method that would merge them (ADR-0008: "no standalone Claim/Fact
entity, table, or graph exists in MVP" - the epistemic separation lives in
having two separate fields, not in a third derived one).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

__all__ = ["Event"]


@dataclass(frozen=True, slots=True)
class Event:
    """A real-world development extracted from Documents.

    Identity is a system id, never the source Document - one Event may be
    supported by several Documents, and one Document may yield several
    Events (DOMAIN_MODEL.md section 3). ``source_ids`` references the
    supporting Documents and is never empty.

    ``extracted_facts`` and ``source_claims`` are structured, separate
    sequences (each item a small mapping) inside the extraction result -
    not full standalone Claim/Fact entities (ADR-0008). The structure of
    each item is not yet fixed by a schema version; that is explicit
    follow-up work in ADR-0008, not something this type should
    pre-decide.
    """

    type: str
    title: str
    occurred_at: datetime
    source_ids: tuple[UUID, ...]
    confidence: float
    entities: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[str, ...] = field(default_factory=tuple)
    extracted_facts: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    source_claims: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    id: UUID | None = None

    def __post_init__(self) -> None:
        for attr_name in ("type", "title"):
            value = getattr(self, attr_name)
            if not value.strip():
                raise ValueError(f"Event.{attr_name} must not be empty")
        if len(self.source_ids) == 0:
            raise ValueError("Event.source_ids must not be empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Event.confidence must be between 0.0 and 1.0")
