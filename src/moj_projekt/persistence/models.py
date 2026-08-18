"""SQLAlchemy ORM models for the Ingestion bounded context.

Maps :class:`~moj_projekt.domain.source.Source` and
:class:`~moj_projekt.domain.document.Document` to PostgreSQL tables. Schema
changes for these tables live exclusively in ``migrations/`` (Alembic) - this
module declares the mapping, it never calls ``Base.metadata.create_all()``
(root ``CLAUDE.md``, ADR-0013).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "DocumentModel", "SourceModel"]


class Base(DeclarativeBase):
    pass


class SourceModel(Base):
    """Row for a :class:`~moj_projekt.domain.source.Source`.

    ``key`` is the primary key: Source identity is the stable source key,
    not a surrogate id (DOMAIN_MODEL.md section 3).
    """

    __tablename__ = "sources"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    publisher: Mapped[str] = mapped_column(String(200), nullable=False)
    endpoint_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DocumentModel(Base):
    """Row for a :class:`~moj_projekt.domain.document.Document`.

    ``natural_key`` is ``source_native_id`` when present, else ``url`` -
    computed by the repository at write time, matching
    ``Document.natural_key``. Together with ``source_key`` and
    ``published_at`` it forms the deduplication natural key
    (DOMAIN_MODEL.md section 3); the unique constraint enforcing it and the
    immutability trigger both live in the migration, not here.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(
        String(100), ForeignKey("sources.key"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_native_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    natural_key: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    processing_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
