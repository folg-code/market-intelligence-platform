"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.NarrativeRelationRepository`.

Self-relations are rejected twice: structurally, by
:meth:`NarrativeRelation.__post_init__
<moj_projekt.domain.narrative_relation.NarrativeRelation.__post_init__>`,
and at the database level by the ``ck_narrative_relations_no_self_relation``
CHECK constraint from the migration. Duplicate ``(source, target, type)``
triples raise ``IntegrityError`` via the
``uq_narrative_relations_source_target_type`` unique constraint.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from moj_projekt.domain.enums import RelationType
from moj_projekt.domain.narrative_relation import NarrativeRelation
from moj_projekt.persistence.models import NarrativeRelationModel

__all__ = ["SqlAlchemyNarrativeRelationRepository"]


def _to_domain(row: NarrativeRelationModel) -> NarrativeRelation:
    return NarrativeRelation(
        id=row.id,
        source_narrative_id=row.source_narrative_id,
        target_narrative_id=row.target_narrative_id,
        relation_type=RelationType(row.relation_type),
    )


class SqlAlchemyNarrativeRelationRepository:
    """Persists NarrativeRelations. No update path - a relation is written
    once; MVP has no merge/split UI to change it.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, relation: NarrativeRelation) -> NarrativeRelation:
        row = NarrativeRelationModel(
            source_narrative_id=relation.source_narrative_id,
            target_narrative_id=relation.target_narrative_id,
            relation_type=relation.relation_type.value,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, relation_id: UUID) -> NarrativeRelation | None:
        row = self._session.get(NarrativeRelationModel, relation_id)
        return _to_domain(row) if row is not None else None
