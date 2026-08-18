"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.EventRepository`.

``source_ids`` is stored as a JSONB array of stringified UUIDs. The
"non-empty" invariant is enforced twice: structurally, by
:meth:`Event.__post_init__ <moj_projekt.domain.event.Event.__post_init__>`,
and at the database level by the ``ck_events_source_ids_not_empty`` CHECK
constraint from the migration.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from moj_projekt.domain.event import Event
from moj_projekt.persistence.models import EventModel

__all__ = ["SqlAlchemyEventRepository"]


def _to_domain(row: EventModel) -> Event:
    return Event(
        id=row.id,
        type=row.type,
        title=row.title,
        occurred_at=row.occurred_at,
        source_ids=tuple(UUID(value) for value in row.source_ids),
        confidence=row.confidence,
        entities=tuple(row.entities),
        topics=tuple(row.topics),
        extracted_facts=tuple(row.extracted_facts),
        source_claims=tuple(row.source_claims),
    )


class SqlAlchemyEventRepository:
    """Persists Events. No update path - an Event is written once."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: Event) -> Event:
        row = EventModel(
            type=event.type,
            title=event.title,
            occurred_at=event.occurred_at,
            entities=list(event.entities),
            topics=list(event.topics),
            extracted_facts=[dict(item) for item in event.extracted_facts],
            source_claims=[dict(item) for item in event.source_claims],
            source_ids=[str(source_id) for source_id in event.source_ids],
            confidence=event.confidence,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, event_id: UUID) -> Event | None:
        row = self._session.get(EventModel, event_id)
        return _to_domain(row) if row is not None else None
