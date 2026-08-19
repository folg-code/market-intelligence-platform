"""``Document`` - normalized, immutable raw input from a Source
(DOMAIN_MODEL.md section 3, "Ingestion").

Pure domain representation: no persistence concern, no infrastructure
import. The dataclass is frozen; there is deliberately no "update content"
method anywhere on this type - immutability after collection is a structural
property, not something callers have to remember to respect (root
``CLAUDE.md``: "Documents are immutable. A changed page becomes a new
Document; nothing overwrites collected content.").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import IntEnum
from typing import Any
from uuid import UUID

__all__ = ["Document", "DocumentDedupeKey", "ProcessingStatus"]


class ProcessingStatus(IntEnum):
    """How far a Document has moved through the processing pipeline.

    Not a DOMAIN_MODEL.md section 4 value object (the document does not list
    its members) - it is the concrete shape of the "processing_status
    advances monotonically" invariant from section 3. Ordinal order *is* the
    monotonic order: a transition is legal only when the new value is
    greater than or equal to the current one (see
    :meth:`Document.advance_processing_status`).
    """

    COLLECTED = 1
    """Persisted, unprocessed by any later stage."""
    EVENTS_EXTRACTED = 2
    """Extraction attempted and a terminal verdict reached.

    A terminal verdict is ``accepted``, ``proposed``, or ``rejected``
    (including a legitimate zero-event extraction). This status does
    **not** mean an Event row exists (D-S002-04 clause 3).
    """
    PROCESSED = 3
    """This Document's contribution to narratives/evidence is complete."""


@dataclass(frozen=True, slots=True)
class DocumentDedupeKey:
    """The natural key used for deduplication (DOMAIN_MODEL.md section 3):
    (source, source-native id or URL, published timestamp).
    """

    source_key: str
    natural_key: str
    published_at: datetime


@dataclass(frozen=True, slots=True)
class Document:
    """Normalized, immutable raw input from one Source.

    ``id`` is ``None`` until the repository assigns one on first persistence
    (idempotent insert - see :mod:`moj_projekt.domain.repositories`).
    ``source_native_id`` is the source's own identifier for the item when it
    has one (e.g. a GUID from an RSS feed); when absent, ``url`` stands in
    for it in the dedupe key.
    """

    source_key: str
    source_type: str
    url: str
    published_at: datetime
    collected_at: datetime
    title: str
    content: str
    source_native_id: str | None = None
    language: str | None = None
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)
    processing_status: ProcessingStatus = ProcessingStatus.COLLECTED
    id: UUID | None = None

    def __post_init__(self) -> None:
        for attr_name in ("source_key", "source_type", "url", "title", "content"):
            value = getattr(self, attr_name)
            if not value.strip():
                raise ValueError(f"Document.{attr_name} must not be empty")
        if self.source_native_id is not None and not self.source_native_id.strip():
            raise ValueError("Document.source_native_id must not be blank when provided")

    @property
    def natural_key(self) -> str:
        """The source-native id when present, else the URL."""
        return self.source_native_id if self.source_native_id is not None else self.url

    @property
    def dedupe_key(self) -> DocumentDedupeKey:
        return DocumentDedupeKey(
            source_key=self.source_key,
            natural_key=self.natural_key,
            published_at=self.published_at,
        )

    @property
    def has_collection_timestamp_anomaly(self) -> bool:
        """``collected_at >= published_at`` is expected; a violation is a
        data-quality flag, not a silent correction (DOMAIN_MODEL.md section
        3). The raw timestamps are kept exactly as observed - this property
        only *reports* the anomaly, it never changes either value.
        """
        return self.collected_at < self.published_at

    def advance_processing_status(self, new_status: ProcessingStatus) -> Document:
        """Return a copy with ``processing_status`` moved forward.

        Rejects any transition that would move the status backwards -
        "a document cannot silently regress to unprocessed" (DOMAIN_MODEL.md
        section 3).
        """
        if new_status < self.processing_status:
            raise ValueError(
                "processing_status cannot regress: "
                f"{self.processing_status!r} -> {new_status!r}"
            )
        return replace(self, processing_status=new_status)
