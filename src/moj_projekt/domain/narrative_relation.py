"""``NarrativeRelation`` - a typed relation between two Narratives
(DOMAIN_MODEL.md section 3, "Narrative Intelligence").

Pure domain representation: no persistence concern, no infrastructure
import. Relations exist so Narratives are not prematurely merged - automatic
merge/split is out of scope for MVP.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from moj_projekt.domain.enums import RelationType

__all__ = ["NarrativeRelation"]


@dataclass(frozen=True, slots=True)
class NarrativeRelation:
    """A directed or symmetric relation between two Narratives.

    Identity is ``(source_narrative_id, target_narrative_id, relation_type)``.
    ``causes``, ``contributes_to``, ``parent_of``, ``merged_into`` are
    directional; ``related_to`` and ``contradicts`` are symmetric in
    meaning, but this type stores one directed row either way - symmetry is
    a meaning, not a storage requirement.
    """

    source_narrative_id: UUID
    target_narrative_id: UUID
    relation_type: RelationType
    id: UUID | None = None

    def __post_init__(self) -> None:
        if self.source_narrative_id == self.target_narrative_id:
            raise ValueError("NarrativeRelation must not relate a narrative to itself")
