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

from moj_projekt.domain.alert import Alert
from moj_projekt.domain.audit_entry import AuditEntry
from moj_projekt.domain.cycle_run import CycleRun
from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.domain.enums import Instrument
from moj_projekt.domain.event import Event
from moj_projekt.domain.evidence_pack import EvidencePack
from moj_projekt.domain.instrument_impact import NarrativeInstrumentImpact
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.domain.narrative import Narrative
from moj_projekt.domain.narrative_episode import NarrativeEpisode
from moj_projekt.domain.narrative_event import NarrativeEvent
from moj_projekt.domain.narrative_relation import NarrativeRelation
from moj_projekt.domain.source import Source

__all__ = [
    "AlertRepository",
    "AuditEntryRepository",
    "CycleRunRepository",
    "DocumentRepository",
    "EventRepository",
    "EvidencePackRepository",
    "LLMRunRepository",
    "NarrativeEpisodeRepository",
    "NarrativeEventRepository",
    "NarrativeInstrumentImpactRepository",
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


class NarrativeInstrumentImpactRepository(Protocol):
    """Persists and retrieves :class:`NarrativeInstrumentImpact` rows, keyed
    by ``(narrative_id, instrument)``.

    Deliberately named ``upsert``, not ``add``: DOMAIN_MODEL.md states there
    is **one current** assessment per pair, so writing a new assessment for
    a pair that already has one replaces it rather than raising or creating
    a second row (a documented judgment call - see the module docstring on
    :class:`~moj_projekt.domain.instrument_impact.NarrativeInstrumentImpact`).
    """

    def upsert(
        self, impact: NarrativeInstrumentImpact
    ) -> NarrativeInstrumentImpact:
        """Persist ``impact`` as the current assessment for its
        ``(narrative_id, instrument)`` pair, replacing any existing one.
        """
        ...

    def get(
        self, narrative_id: UUID, instrument: Instrument
    ) -> NarrativeInstrumentImpact | None: ...


class AlertRepository(Protocol):
    """Persists and retrieves :class:`Alert` rows.

    ``add`` is idempotent on the ``(narrative_id, alert_type, trigger_key)``
    dedup key: a repeated cycle that would fire the same alert again is a
    no-op returning the existing row, mirroring
    :meth:`DocumentRepository.add`.
    """

    def add(self, alert: Alert) -> Alert: ...

    def get(self, alert_id: UUID) -> Alert | None: ...


class LLMRunRepository(Protocol):
    """Persists and retrieves :class:`LLMRun` rows.

    Append-only (ADR-0007): deliberately has no update or delete method,
    and the database rejects both at the trigger level as well.
    """

    def add(self, llm_run: LLMRun) -> LLMRun: ...

    def get(self, llm_run_id: UUID) -> LLMRun | None: ...


class AuditEntryRepository(Protocol):
    """Persists and retrieves :class:`AuditEntry` rows.

    Append-only (ADR-0009): deliberately has no update or delete method,
    and the database rejects both at the trigger level as well.
    """

    def add(self, entry: AuditEntry) -> AuditEntry: ...

    def get(self, entry_id: UUID) -> AuditEntry | None: ...


class CycleRunRepository(Protocol):
    """Persists and retrieves :class:`CycleRun` rows (ADR-0004, ADR-0011).

    Unlike the append-only or immutable-after-insert repositories above, a
    CycleRun is written twice: once as ``RUNNING`` when the cycle starts
    (:meth:`add`), then once more with its terminal state
    (:meth:`update`) - there is no in-between write, so no "advance one
    field" method is needed the way
    :meth:`DocumentRepository.advance_processing_status` is.
    """

    def add(self, cycle_run: CycleRun) -> CycleRun:
        """Persist a new ``RUNNING`` CycleRun and return the stored row,
        with its assigned ``id``.
        """
        ...

    def update(self, cycle_run: CycleRun) -> CycleRun:
        """Persist the current state of an existing CycleRun (matched by
        ``cycle_run.id``) - status, ``ended_at``, stage/source outcomes,
        and ``failure_reason``. Raises if no row with that id exists.
        """
        ...

    def get(self, cycle_run_id: UUID) -> CycleRun | None: ...

    def get_running(self) -> CycleRun | None:
        """Return the currently ``RUNNING`` CycleRun, if any.

        This is the data-level overlap guard (ADR-0011: "the cycle's
        idempotency is not allowed to depend on the scheduler behaving
        correctly") - the orchestration function checks this before
        starting a new run, independent of the scheduler's own
        ``max_instances=1``.
        """
        ...
