"""Unit tests for NarrativeEpisode invariants (S001-T008) - no database.

Overlap prevention between episodes of the *same* Narrative is a cross-row
invariant and is covered at the database level, not here (see
tests/integration/test_narrative_persistence.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from moj_projekt.domain.narrative_episode import NarrativeEpisode

_STARTED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _make_episode(**overrides: object) -> NarrativeEpisode:
    defaults: dict[str, object] = dict(
        narrative_id=uuid4(),
        started_at=_STARTED_AT,
    )
    defaults.update(overrides)
    return NarrativeEpisode(**defaults)  # type: ignore[arg-type]


def test_narrative_episode_accepts_no_end_date() -> None:
    episode = _make_episode(ended_at=None)

    assert episode.ended_at is None


def test_narrative_episode_rejects_ended_before_started() -> None:
    with pytest.raises(ValueError, match="ended_at"):
        _make_episode(ended_at=_STARTED_AT - timedelta(hours=1))


def test_narrative_episode_accepts_ended_equal_to_started() -> None:
    episode = _make_episode(ended_at=_STARTED_AT)

    assert episode.ended_at == episode.started_at
