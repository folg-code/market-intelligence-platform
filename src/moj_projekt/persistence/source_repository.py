"""SQLAlchemy implementation of :class:`~moj_projekt.domain.repositories.SourceRepository`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source
from moj_projekt.persistence.models import SourceModel

__all__ = ["SqlAlchemySourceRepository"]


def _to_domain(row: SourceModel) -> Source:
    return Source(
        key=row.key,
        name=row.name,
        source_type=row.source_type,
        tier=SourceTier(row.tier),
        publisher=row.publisher,
        endpoint_config=dict(row.endpoint_config),
        active=row.active,
    )


class SqlAlchemySourceRepository:
    """Persists Sources, keyed by ``Source.key``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, source: Source) -> Source:
        statement = (
            pg_insert(SourceModel)
            .values(
                key=source.key,
                name=source.name,
                source_type=source.source_type,
                tier=int(source.tier),
                publisher=source.publisher,
                endpoint_config=dict(source.endpoint_config),
                active=source.active,
            )
            .on_conflict_do_nothing(index_elements=[SourceModel.key])
        )
        self._session.execute(statement)
        self._session.flush()
        stored = self._session.get(SourceModel, source.key)
        if stored is None:
            raise RuntimeError(f"Source {source.key!r} missing immediately after upsert")
        return _to_domain(stored)

    def get(self, key: str) -> Source | None:
        row = self._session.get(SourceModel, key)
        return _to_domain(row) if row is not None else None

    def list_active(self) -> list[Source]:
        rows = self._session.scalars(
            select(SourceModel)
            .where(SourceModel.active.is_(True))
            .order_by(SourceModel.key)
        ).all()
        return [_to_domain(row) for row in rows]
