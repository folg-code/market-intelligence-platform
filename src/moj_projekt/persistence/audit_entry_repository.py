"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.AuditEntryRepository`.

Append-only (ADR-0009): this class exposes no update or delete method, and
the ``audit_entries_append_only_trigger`` from the migration rejects any
UPDATE or DELETE attempted through a raw SQL statement as well.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from moj_projekt.domain.audit_entry import AuditEntry
from moj_projekt.persistence.models import AuditEntryModel

__all__ = ["SqlAlchemyAuditEntryRepository"]


def _to_domain(row: AuditEntryModel) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        actor=row.actor,
        action=row.action,
        target_id=row.target_id,
        previous_value=dict(row.previous_value),
        new_value=dict(row.new_value),
        timestamp=row.timestamp,
        reason=row.reason,
    )


class SqlAlchemyAuditEntryRepository:
    """Persists AuditEntries. No update or delete path - the record is
    append-only (ADR-0009).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditEntry) -> AuditEntry:
        row = AuditEntryModel(
            actor=entry.actor,
            action=entry.action,
            target_id=entry.target_id,
            previous_value=dict(entry.previous_value),
            new_value=dict(entry.new_value),
            timestamp=entry.timestamp,
            reason=entry.reason,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, entry_id: UUID) -> AuditEntry | None:
        row = self._session.get(AuditEntryModel, entry_id)
        return _to_domain(row) if row is not None else None
