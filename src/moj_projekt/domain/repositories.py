"""Repository interfaces for the Ingestion, Event Extraction, and Evidence &
Trust bounded contexts.

Domain code (and anything calling into these contexts) depends on these
interfaces, never on a SQLAlchemy session directly - "Persistence is reached
through repository interfaces" (root ``CLAUDE.md``). No SQLAlchemy type
appears in any signature here (Wave 0 decision D-S001-04); implementations
live in :mod:`moj_projekt.persistence`.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.domain.event import Event
from moj_projekt.domain.evidence_pack import EvidencePack
from moj_projekt.domain.narrative import Narrative
from moj_projekt.domain.narrative_episode import NarrativeEpisode
from moj_projekt.domain.narrative_event import NarrativeEvent
from moj_projekt.domain.narrative_relation import NarrativeRelation
from moj_projekt.domain.source import Source

__all__ = [
    "DocumentRepository",
    "EventRepository",
    "EvidencePackRepository",
    "NarrativeEpisodeRepository",
    "NarrativeEventRepository",
    "NarrativeRelationRepository",
    "NarrativeRepository",
    "SourceRepository",
]


class SourceRepository(Protocol):
    """Persists and retrieves :class:`Source` rows, keyed by ``Source.key``."""

    def add(self, source: Source) -> Source:
        """Persist ``source``. Idempotent: adding the same key twice leaves
        one row and returns it unchanged rather than raising.
        """
        ...

    def get(self, key: str) -> Source | None: ...


class DocumentRepository(Protocol):
    """Persists and retrieves :class:`Document` rows.

    Deliberately has no "update" method: a collected Document's content is
    immutable, so there is no operation that could mutate it. The only
    permitted change over time is moving ``processing_status`` forward via
    :meth:`advance_processing_status`.
    """

    def add(self, document: Document) -> Document:
        """Persist ``document`` and return the stored row.

        Idempotent on the dedupe natural key (source, source-native id or
        URL, published timestamp): if a matching row already exists, it is
        returned unchanged and no new row is written and no error is
        raised - the caller never has to special-case a duplicate.
        """
        ...

    def get(self, document_id: UUID) -> Document | None: ...

    def advance_processing_status(
        self, document_id: UUID, new_status: ProcessingStatus
    ) -> Document:
        """Move ``processing_status`` forward for the given document.

        Rejects (raises) a transition that would move the status backwards.
        """
        ...


class EventRepository(Protocol):
    """Persists and retrieves :class:`Event` rows.

    Deliberately has no "update" method - there is no operation defined on
    an Event after it is stored.
    """

    def add(self, event: Event) -> Event:
        """Persist ``event`` and return the stored row, with its assigned
        ``id``.
        """
        ...

    def get(self, event_id: UUID) -> Event | None: ...


class EvidencePackRepository(Protocol):
    """Persists and retrieves :class:`EvidencePack` snapshots.

    Deliberately has no "update" method: an EvidencePack is never mutated
    in place - a rebuild produces a new ``evidence_version`` (ADR-0003).
    """

    def add(self, evidence_pack: EvidencePack) -> EvidencePack:
        """Persist ``evidence_pack`` as a new version and return the stored
        row. Raises if ``(narrative_id, evidence_version)`` already exists.
        """
        ...

    def get_current(self, narrative_id: UUID) -> EvidencePack | None:
        """Return the highest-``evidence_version`` pack for ``narrative_id``,
        or ``None`` if the narrative has no pack yet.
        """
        ...

    def get_version(
        self, narrative_id: UUID, evidence_version: int
    ) -> EvidencePack | None: ...


class NarrativeRepository(Protocol):
    """Persists and retrieves :class:`Narrative` rows, keyed by system id.

    Deliberately has no "update" method: nothing in this sprint's scope
    mutates a stored Narrative (no matching logic, no lifecycle
    automation). ``canonical_key`` uniqueness is enforced at the database
    level, not re-checked here.
    """

    def add(self, narrative: Narrative) -> Narrative:
        """Persist ``narrative`` and return the stored row, with its
        assigned ``id``. Raises if ``canonical_key`` already exists.
        """
        ...

    def get(self, narrative_id: UUID) -> Narrative | None: ...

    def get_by_canonical_key(self, canonical_key: str) -> Narrative | None: ...


class NarrativeEpisodeRepository(Protocol):
    """Persists and retrieves :class:`NarrativeEpisode` rows.

    Overlap prevention within one Narrative is enforced at the database
    level (an ``EXCLUDE`` constraint from the migration), since it is a
    cross-row invariant a single episode cannot check on its own.
    """

    def add(self, episode: NarrativeEpisode) -> NarrativeEpisode:
        """Persist ``episode`` and return the stored row. Raises if it
        overlaps an existing episode of the same Narrative.
        """
        ...

    def get(self, episode_id: UUID) -> NarrativeEpisode | None: ...


class NarrativeEventRepository(Protocol):
    """Persists and retrieves :class:`NarrativeEvent` assignments, keyed by
    ``(narrative_id, event_id)``.
    """

    def add(self, narrative_event: NarrativeEvent) -> NarrativeEvent:
        """Persist ``narrative_event`` and return the stored row. Raises if
        this ``(narrative_id, event_id)`` pair already exists.
        """
        ...

    def get(self, narrative_id: UUID, event_id: UUID) -> NarrativeEvent | None: ...


class NarrativeRelationRepository(Protocol):
    """Persists and retrieves :class:`NarrativeRelation` rows, keyed by
    ``(source_narrative_id, target_narrative_id, relation_type)``.
    """

    def add(self, relation: NarrativeRelation) -> NarrativeRelation:
        """Persist ``relation`` and return the stored row. Raises for a
        self-relation or a duplicate ``(source, target, type)`` triple.
        """
        ...

    def get(
        self, relation_id: UUID
    ) -> NarrativeRelation | None: ...
