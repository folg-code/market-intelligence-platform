"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.NarrativeEventRepository`.

Identity is the composite primary key ``(narrative_id, event_id)``; inserting
a duplicate pair raises ``IntegrityError`` rather than being special-cased
here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from moj_projekt.domain.enums import CandidateStatus, OverrideState
from moj_projekt.domain.narrative_event import NarrativeEvent
from moj_projekt.persistence.models import NarrativeEventModel

__all__ = ["SqlAlchemyNarrativeEventRepository"]


def _to_domain(row: NarrativeEventModel) -> NarrativeEvent:
    return NarrativeEvent(
        narrative_id=row.narrative_id,
        event_id=row.event_id,
        assignment_rationale=row.assignment_rationale,
        assignment_confidence=row.assignment_confidence,
        assignment_status=CandidateStatus(row.assignment_status),
        llm_run_id=row.llm_run_id,
        candidate_shortlist=tuple(row.candidate_shortlist),
        override_state=OverrideState(row.override_state),
    )


class SqlAlchemyNarrativeEventRepository:
    """Persists NarrativeEvent assignments. No update path in this
    sprint's scope.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, narrative_event: NarrativeEvent) -> NarrativeEvent:
        row = NarrativeEventModel(
            narrative_id=narrative_event.narrative_id,
            event_id=narrative_event.event_id,
            assignment_rationale=narrative_event.assignment_rationale,
            assignment_confidence=narrative_event.assignment_confidence,
            assignment_status=narrative_event.assignment_status.value,
            llm_run_id=narrative_event.llm_run_id,
            candidate_shortlist=[dict(item) for item in narrative_event.candidate_shortlist],
            override_state=narrative_event.override_state.value,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, narrative_id: UUID, event_id: UUID) -> NarrativeEvent | None:
        row = self._session.get(NarrativeEventModel, (narrative_id, event_id))
        return _to_domain(row) if row is not None else None
