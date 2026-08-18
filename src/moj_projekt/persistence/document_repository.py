"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.DocumentRepository`.

Deduplication is enforced at the database level (the ``uq_documents_dedupe_key``
unique constraint from the migration), not by a select-then-insert race: an
``INSERT ... ON CONFLICT DO NOTHING`` either creates the row or is a no-op
when one already matches, and the row is then always read back - so the
caller gets one row back either way, with no exception to catch.

Immutability is enforced twice: structurally (there is no "update content"
method on this class or on the domain repository interface) and at the
database level (the ``documents_enforce_immutability_trigger`` from the
migration rejects any UPDATE that touches a column other than
``processing_status``, or moves it backwards).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.persistence.models import DocumentModel

__all__ = ["SqlAlchemyDocumentRepository"]


def _to_domain(row: DocumentModel) -> Document:
    return Document(
        id=row.id,
        source_key=row.source_key,
        source_type=row.source_type,
        url=row.url,
        source_native_id=row.source_native_id,
        published_at=row.published_at,
        collected_at=row.collected_at,
        title=row.title,
        content=row.content,
        language=row.language,
        raw_metadata=dict(row.raw_metadata),
        processing_status=ProcessingStatus(row.processing_status),
    )


class SqlAlchemyDocumentRepository:
    """Persists Documents, deduplicated on the (source, natural key,
    published_at) natural key.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: Document) -> Document:
        statement = (
            pg_insert(DocumentModel)
            .values(
                source_key=document.source_key,
                source_type=document.source_type,
                url=document.url,
                source_native_id=document.source_native_id,
                natural_key=document.natural_key,
                published_at=document.published_at,
                collected_at=document.collected_at,
                title=document.title,
                content=document.content,
                language=document.language,
                raw_metadata=dict(document.raw_metadata),
                processing_status=int(document.processing_status),
            )
            .on_conflict_do_nothing(constraint="uq_documents_dedupe_key")
        )
        self._session.execute(statement)
        self._session.commit()

        row = self._session.execute(
            select(DocumentModel).where(
                DocumentModel.source_key == document.source_key,
                DocumentModel.natural_key == document.natural_key,
                DocumentModel.published_at == document.published_at,
            )
        ).scalar_one()
        return _to_domain(row)

    def get(self, document_id: UUID) -> Document | None:
        row = self._session.get(DocumentModel, document_id)
        return _to_domain(row) if row is not None else None

    def advance_processing_status(
        self, document_id: UUID, new_status: ProcessingStatus
    ) -> Document:
        result = self._session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == document_id,
                DocumentModel.processing_status <= int(new_status),
            )
            .values(processing_status=int(new_status))
        )
        self._session.commit()

        # `execute()` on an UPDATE returns a CursorResult at runtime, which
        # does have `rowcount` - the generic `Result[Any]` return type just
        # doesn't expose it statically.
        if result.rowcount == 0:  # type: ignore[attr-defined]
            existing = self._session.get(DocumentModel, document_id)
            if existing is None:
                raise ValueError(f"Document {document_id} does not exist")
            raise ValueError(
                "processing_status cannot regress: "
                f"{ProcessingStatus(existing.processing_status)!r} -> {new_status!r}"
            )

        row = self._session.get(DocumentModel, document_id)
        if row is None:
            raise ValueError(f"Document {document_id} does not exist")
        return _to_domain(row)
