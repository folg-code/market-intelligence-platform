"""Unit tests for Narrative invariants (S001-T008) - no database.

Covers DOMAIN_MODEL.md section 3 "Narrative" invariants: a Narrative
without an `economic_mechanism` or `market_interpretation` is rejected, a
NULL `identity_embedding` is fully valid, and `first_seen <= last_seen`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from moj_projekt.domain.embedding import IdentityEmbedding
from moj_projekt.domain.narrative import Narrative

_FIRST_SEEN = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_LAST_SEEN = _FIRST_SEEN + timedelta(hours=1)


def _make_narrative(**overrides: object) -> Narrative:
    defaults: dict[str, object] = dict(
        canonical_key="fed_rate_cut_expectations",
        display_title="Fed rate cut expectations",
        economic_mechanism="Lower policy rate reduces the discount rate.",
        market_interpretation="Bullish for risk assets, bearish for the dollar.",
        category="monetary_policy",
        first_seen=_FIRST_SEEN,
        last_seen=_LAST_SEEN,
        updated_at=_LAST_SEEN,
    )
    defaults.update(overrides)
    return Narrative(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    [
        "canonical_key",
        "display_title",
        "economic_mechanism",
        "market_interpretation",
        "category",
    ],
)
def test_narrative_rejects_blank_required_fields(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _make_narrative(**{field_name: "   "})


def test_narrative_is_valid_with_null_identity_embedding() -> None:
    narrative = _make_narrative(identity_embedding=None)

    assert narrative.identity_embedding is None


def test_narrative_accepts_a_populated_identity_embedding() -> None:
    embedding = IdentityEmbedding(
        embedding_model="local-minilm",
        embedding_version="v1",
        vector=(0.1, 0.2, 0.3),
    )

    narrative = _make_narrative(identity_embedding=embedding)

    assert narrative.identity_embedding == embedding


def test_narrative_rejects_first_seen_after_last_seen() -> None:
    with pytest.raises(ValueError, match="first_seen"):
        _make_narrative(first_seen=_LAST_SEEN, last_seen=_FIRST_SEEN)


def test_narrative_accepts_first_seen_equal_to_last_seen() -> None:
    narrative = _make_narrative(first_seen=_FIRST_SEEN, last_seen=_FIRST_SEEN)

    assert narrative.first_seen == narrative.last_seen


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_narrative_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        _make_narrative(confidence=confidence)
