"""Unit tests for NarrativeRelation invariants (S001-T008) - no database."""

from __future__ import annotations

from uuid import uuid4

import pytest

from moj_projekt.domain.enums import RelationType
from moj_projekt.domain.narrative_relation import NarrativeRelation


def test_narrative_relation_rejects_self_relation() -> None:
    narrative_id = uuid4()

    with pytest.raises(ValueError, match="itself"):
        NarrativeRelation(
            source_narrative_id=narrative_id,
            target_narrative_id=narrative_id,
            relation_type=RelationType.RELATED_TO,
        )


def test_narrative_relation_accepts_distinct_narratives() -> None:
    relation = NarrativeRelation(
        source_narrative_id=uuid4(),
        target_narrative_id=uuid4(),
        relation_type=RelationType.CONTRADICTS,
    )

    assert relation.relation_type is RelationType.CONTRADICTS
