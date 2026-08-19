"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.NarrativeEpisodeRepository`.

Overlap prevention within one Narrative is enforced at the database level
(the ``ex_narrative_episodes_no_overlap`` ``EXCLUDE`` constraint from the
migration) - it is a cross-row invariant a single episode cannot check on
its own, so this repository does not duplicate the check in Python.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from moj_projekt.domain.narrative_episode import NarrativeEpisode
from moj_projekt.persistence.models import NarrativeEpisodeModel

__all__ = ["SqlAlchemyNarrativeEpisodeRepository"]


def _to_domain(row: NarrativeEpisodeModel) -> NarrativeEpisode:
    return NarrativeEpisode(
        id=row.id,
        narrative_id=row.narrative_id,
        started_at=row.started_at,
        ended_at=row.ended_at,
        notes=row.notes,
    )


class SqlAlchemyNarrativeEpisodeRepository:
    """Persists NarrativeEpisodes. No update path - an episode is written
    once, then superseded by a new episode rather than mutated.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, episode: NarrativeEpisode) -> NarrativeEpisode:
        row = NarrativeEpisodeModel(
            narrative_id=episode.narrative_id,
            started_at=episode.started_at,
            ended_at=episode.ended_at,
            notes=episode.notes,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, episode_id: UUID) -> NarrativeEpisode | None:
        row = self._session.get(NarrativeEpisodeModel, episode_id)
        return _to_domain(row) if row is not None else None
