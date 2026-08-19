"""SQLAlchemy unit of work: session lifecycle and the single commit/rollback.

Repositories only :meth:`~sqlalchemy.orm.Session.flush` (and
:meth:`~sqlalchemy.orm.Session.refresh` when the caller needs a
server-assigned id). This object is the transaction boundary so an Event
and its ``LLMRun`` can later be persisted together (D-S002-04 clause 6).
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from moj_projekt.domain.repositories import (
    AlertRepository,
    AuditEntryRepository,
    CycleRunRepository,
    DocumentRepository,
    EventRepository,
    EvidencePackRepository,
    LLMRunRepository,
    NarrativeEpisodeRepository,
    NarrativeEventRepository,
    NarrativeInstrumentImpactRepository,
    NarrativeRelationRepository,
    NarrativeRepository,
    SourceRepository,
)
from moj_projekt.persistence.alert_repository import SqlAlchemyAlertRepository
from moj_projekt.persistence.audit_entry_repository import SqlAlchemyAuditEntryRepository
from moj_projekt.persistence.cycle_run_repository import SqlAlchemyCycleRunRepository
from moj_projekt.persistence.document_repository import SqlAlchemyDocumentRepository
from moj_projekt.persistence.event_repository import SqlAlchemyEventRepository
from moj_projekt.persistence.evidence_pack_repository import (
    SqlAlchemyEvidencePackRepository,
)
from moj_projekt.persistence.instrument_impact_repository import (
    SqlAlchemyNarrativeInstrumentImpactRepository,
)
from moj_projekt.persistence.llm_run_repository import SqlAlchemyLLMRunRepository
from moj_projekt.persistence.narrative_episode_repository import (
    SqlAlchemyNarrativeEpisodeRepository,
)
from moj_projekt.persistence.narrative_event_repository import (
    SqlAlchemyNarrativeEventRepository,
)
from moj_projekt.persistence.narrative_relation_repository import (
    SqlAlchemyNarrativeRelationRepository,
)
from moj_projekt.persistence.narrative_repository import SqlAlchemyNarrativeRepository
from moj_projekt.persistence.source_repository import SqlAlchemySourceRepository

__all__ = ["SqlAlchemyUnitOfWork", "sqlalchemy_unit_of_work_factory"]


class SqlAlchemyUnitOfWork:
    """Opens a ``Session`` on ``engine``, binds every repository, and commits once.

    Each ``with`` block is one transaction: success commits, an exception
    rolls back, and the session is closed either way. Nested units of
    work / savepoints are out of scope (S002-T002).
    """

    sources: SourceRepository
    documents: DocumentRepository
    events: EventRepository
    evidence_packs: EvidencePackRepository
    narratives: NarrativeRepository
    narrative_episodes: NarrativeEpisodeRepository
    narrative_events: NarrativeEventRepository
    narrative_relations: NarrativeRelationRepository
    instrument_impacts: NarrativeInstrumentImpactRepository
    alerts: AlertRepository
    llm_runs: LLMRunRepository
    audit_entries: AuditEntryRepository
    cycle_runs: CycleRunRepository

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None

    def __enter__(self) -> Self:
        session = Session(self._engine)
        self._session = session
        self.sources = SqlAlchemySourceRepository(session)
        self.documents = SqlAlchemyDocumentRepository(session)
        self.events = SqlAlchemyEventRepository(session)
        self.evidence_packs = SqlAlchemyEvidencePackRepository(session)
        self.narratives = SqlAlchemyNarrativeRepository(session)
        self.narrative_episodes = SqlAlchemyNarrativeEpisodeRepository(session)
        self.narrative_events = SqlAlchemyNarrativeEventRepository(session)
        self.narrative_relations = SqlAlchemyNarrativeRelationRepository(session)
        self.instrument_impacts = SqlAlchemyNarrativeInstrumentImpactRepository(session)
        self.alerts = SqlAlchemyAlertRepository(session)
        self.llm_runs = SqlAlchemyLLMRunRepository(session)
        self.audit_entries = SqlAlchemyAuditEntryRepository(session)
        self.cycle_runs = SqlAlchemyCycleRunRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            if exc_type is not None:
                session.rollback()
            else:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            self._session = None


def sqlalchemy_unit_of_work_factory(
    engine: Engine,
) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Return a factory that opens a fresh unit of work on ``engine``."""

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(engine)

    return factory
