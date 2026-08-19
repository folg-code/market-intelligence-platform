"""``NarrativeEpisode`` - a distinct period of activity of a recurring
Narrative (DOMAIN_MODEL.md section 3, "Narrative Intelligence").

Pure domain representation: no persistence concern, no infrastructure
import. MVP: episodes exist in the model but are not automatically
managed - manual or trivial-case creation only, no automated peak/end/
reactivation detection (DOMAIN_MODEL.md section 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

__all__ = ["NarrativeEpisode"]


@dataclass(frozen=True, slots=True)
class NarrativeEpisode:
    """One activity period of a Narrative, scoped to that Narrative.

    "Episodes of one Narrative do not overlap in time" is a cross-row
    invariant (it needs to see a Narrative's other episodes), so it cannot
    be checked in this constructor - it is enforced at the database level
    by an ``EXCLUDE`` constraint from the migration, not here.
    """

    narrative_id: UUID
    started_at: datetime
    ended_at: datetime | None = None
    notes: str = ""
    id: UUID | None = None

    def __post_init__(self) -> None:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("NarrativeEpisode.ended_at must be >= started_at")
