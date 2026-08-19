"""Unit tests for NarrativeInstrumentImpact invariants (S001-T009) - no
database.

Covers DOMAIN_MODEL.md section 3 "NarrativeInstrumentImpact" and ADR-0006:
confidence range, and the "non-neutral direction requires rationale and
evidence_refs" rule.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from moj_projekt.domain.enums import EvidenceRefKind, ImpactDirection, ImpactHorizon, Instrument
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.instrument_impact import NarrativeInstrumentImpact

_EVIDENCE_REF = EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4()))


def _make_impact(**overrides: object) -> NarrativeInstrumentImpact:
    defaults: dict[str, object] = dict(
        narrative_id=uuid4(),
        instrument=Instrument.NQ,
        relevance=True,
        direction=ImpactDirection.NEUTRAL,
        confidence=0.5,
        horizon=ImpactHorizon.UNKNOWN,
    )
    defaults.update(overrides)
    return NarrativeInstrumentImpact(**defaults)  # type: ignore[arg-type]


def test_neutral_direction_does_not_require_rationale_or_evidence() -> None:
    impact = _make_impact(direction=ImpactDirection.NEUTRAL, rationale="", evidence_refs=())

    assert impact.direction is ImpactDirection.NEUTRAL


@pytest.mark.parametrize(
    "direction",
    [
        ImpactDirection.STRONGLY_BEARISH,
        ImpactDirection.BEARISH,
        ImpactDirection.MIXED,
        ImpactDirection.BULLISH,
        ImpactDirection.STRONGLY_BULLISH,
        ImpactDirection.UNCERTAIN,
    ],
)
def test_non_neutral_direction_rejects_empty_rationale(
    direction: ImpactDirection,
) -> None:
    with pytest.raises(ValueError, match="rationale"):
        _make_impact(direction=direction, rationale="", evidence_refs=(_EVIDENCE_REF,))


def test_non_neutral_direction_rejects_empty_evidence_refs() -> None:
    with pytest.raises(ValueError, match="evidence_refs"):
        _make_impact(
            direction=ImpactDirection.BEARISH,
            rationale="Lower rates hurt gold's opportunity cost narrative.",
            evidence_refs=(),
        )


def test_non_neutral_direction_accepted_with_rationale_and_evidence() -> None:
    impact = _make_impact(
        direction=ImpactDirection.BULLISH,
        rationale="Lower discount rate supports higher equity multiples.",
        evidence_refs=(_EVIDENCE_REF,),
    )

    assert impact.direction is ImpactDirection.BULLISH
    assert impact.evidence_refs == (_EVIDENCE_REF,)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_out_of_range_is_rejected(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        _make_impact(confidence=confidence)


def test_confidence_boundaries_are_accepted() -> None:
    assert _make_impact(confidence=0.0).confidence == 0.0
    assert _make_impact(confidence=1.0).confidence == 1.0
