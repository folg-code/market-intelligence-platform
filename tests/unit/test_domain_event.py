"""Unit tests for Event invariants (S001-T007) - no database.

Covers DOMAIN_MODEL.md section 3 "Event" invariants: at least one source
Document (`source_ids` never empty), and `extracted_facts` / `source_claims`
staying structurally separate (ADR-0008).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from moj_projekt.domain.event import Event

_OCCURRED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _make_event(**overrides: object) -> Event:
    defaults: dict[str, object] = dict(
        type="rate_decision",
        title="Fed holds rates steady",
        occurred_at=_OCCURRED_AT,
        source_ids=(uuid4(),),
        confidence=0.8,
    )
    defaults.update(overrides)
    return Event(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["type", "title"])
def test_event_rejects_blank_required_fields(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _make_event(**{field_name: "   "})


def test_event_rejects_empty_source_ids() -> None:
    with pytest.raises(ValueError, match="source_ids"):
        _make_event(source_ids=())


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_event_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        _make_event(confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 1.0, 0.5])
def test_event_accepts_confidence_at_bounds(confidence: float) -> None:
    event = _make_event(confidence=confidence)

    assert event.confidence == confidence


def test_extracted_facts_and_source_claims_are_kept_separate() -> None:
    fact = {"text": "The Fed left rates unchanged.", "category": "observed_fact"}
    claim = {"text": "Analysts expect a cut next quarter.", "category": "source_claim"}

    event = _make_event(extracted_facts=(fact,), source_claims=(claim,))

    assert event.extracted_facts == (fact,)
    assert event.source_claims == (claim,)
    # Structural separation: no attribute merges the two.
    field_names = {name for name in dir(event) if not name.startswith("_")}
    assert not any("merged" in name or "combined" in name for name in field_names)
