"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.AlertRepository`.

Deduplication is enforced at the database level (the
``uq_alerts_narrative_type_trigger`` unique constraint from the migration),
not by a select-then-insert race: an ``INSERT ... ON CONFLICT DO NOTHING``
either creates the row or is a no-op when one already matches, and the row
is then always read back - mirroring
:class:`~moj_projekt.persistence.document_repository.SqlAlchemyDocumentRepository`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from moj_projekt.domain.alert import Alert
from moj_projekt.domain.enums import AlertType
from moj_projekt.persistence.models import AlertModel

__all__ = ["SqlAlchemyAlertRepository"]


def _to_domain(row: AlertModel) -> Alert:
    return Alert(
        id=row.id,
        narrative_id=row.narrative_id,
        alert_type=AlertType(row.alert_type),
        trigger_key=row.trigger_key,
        details=dict(row.details),
        created_at=row.created_at,
    )


class SqlAlchemyAlertRepository:
    """Persists Alerts, deduplicated on
    ``(narrative_id, alert_type, trigger_key)``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, alert: Alert) -> Alert:
        statement = (
            pg_insert(AlertModel)
            .values(
                narrative_id=alert.narrative_id,
                alert_type=alert.alert_type.value,
                trigger_key=alert.trigger_key,
                details=dict(alert.details),
                created_at=alert.created_at,
            )
            .on_conflict_do_nothing(constraint="uq_alerts_narrative_type_trigger")
        )
        self._session.execute(statement)
        self._session.flush()

        row = self._session.execute(
            select(AlertModel).where(
                AlertModel.narrative_id == alert.narrative_id,
                AlertModel.alert_type == alert.alert_type.value,
                AlertModel.trigger_key == alert.trigger_key,
            )
        ).scalar_one()
        return _to_domain(row)

    def get(self, alert_id: UUID) -> Alert | None:
        row = self._session.get(AlertModel, alert_id)
        return _to_domain(row) if row is not None else None
