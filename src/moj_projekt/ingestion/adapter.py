"""Source adapter interface (S001-T012).

Adapters fetch and normalize a Source into Documents. They do not persist
and they do not import SQLAlchemy - the cycle ingest stage writes through
:class:`~moj_projekt.domain.repositories.DocumentRepository`. Network I/O
belongs in concrete adapters, not in ``domain/`` or ``cycle/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from moj_projekt.domain.document import Document
from moj_projekt.domain.source import Source

__all__ = ["SourceAdapter", "SourceFetchError"]


class SourceFetchError(Exception):
    """A source adapter could not produce documents.

    Caught per source by the ingest stage so a failing source is recorded
    on the CycleRun and does not fail the cycle (root ``CLAUDE.md``, ADR-0004).
    """


class SourceAdapter(Protocol):
    """Fetches one Source and returns normalized Documents.

    Adding a later adapter (Fed/FOMC, BLS, SEC, another news outlet) is
    implementing this method and registering the instance against that
    source's ``source_type``. The ingest loop does not change.
    """

    def fetch_documents(self, source: Source) -> Sequence[Document]:
        """Return normalized Documents for ``source``.

        Raises :class:`SourceFetchError` on timeout, HTTP error, or a
        malformed payload. Must not perform partial persistence - it
        returns an in-memory sequence, or it raises before returning.
        """
        ...
