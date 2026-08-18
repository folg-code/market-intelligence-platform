"""Unit tests for NarrativeEvent invariants (S001-T008) - no database.

The three-condition assignment rule itself (DOMAIN_MODEL.md section 5) is
judged upstream (LLM + validation layer) and out of scope for this sprint;
this type only stores the result plus its retrieval context.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from moj_projekt.domain.narrative_event import NarrativeEvent


def _make_narrative_event(**overrides: object) -> NarrativeEvent:
    defaults: dict[str, object] = dict(
        narrative_id=uuid4(),
        event_id=uuid4(),
        assignment_rationale="Same mechanism, same instrument exposure.",
        assignment_confidence=0.7,
    )
    defaults.update(overrides)
    return NarrativeEvent(**defaults)  # type: ignore[arg-type]


def test_narrative_event_rejects_blank_rationale() -> None:
    with pytest.raises(ValueError, match="assignment_rationale"):
        _make_narrative_event(assignment_rationale="   ")


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_narrative_event_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValueError, match="assignment_confidence"):
        _make_narrative_event(assignment_confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 1.0, 0.5])
def test_narrative_event_accepts_confidence_at_bounds(confidence: float) -> None:
    narrative_event = _make_narrative_event(assignment_confidence=confidence)

    assert narrative_event.assignment_confidence == confidence


def test_narrative_event_records_candidate_shortlist() -> None:
    shortlist = ({"canonical_key": "fed_rate_cut_expectations", "score": 0.91},)

    narrative_event = _make_narrative_event(candidate_shortlist=shortlist)

    assert narrative_event.candidate_shortlist == shortlist
