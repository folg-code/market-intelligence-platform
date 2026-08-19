"""Unit tests for monthly LLM cost arithmetic and threshold bands.

No database, no network: pure functions over token counts and rates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from moj_projekt.domain.budget import (
    BudgetBand,
    BudgetPolicy,
    LLMRunSpendSlice,
    classify_spend,
    cost_from_token_usage,
    cost_usd,
    spend_usd,
    utc_month_bounds,
)
from moj_projekt.llm.models import EVENT_EXTRACTION_TASK_TYPE, model_spec_for

_T0 = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


def _policy(
    *,
    ceiling: str = "10",
    ratio: str = "0.80",
) -> BudgetPolicy:
    return BudgetPolicy(ceiling_usd=Decimal(ceiling), soft_threshold_ratio=Decimal(ratio))


def test_cost_for_known_tokens_and_rate_matches_hand_computed_figure_to_the_cent() -> None:
    # 100_000 input @ $1/M = $0.10; 40_000 output @ $5/M = $0.20; total $0.30.
    cost = cost_usd(
        100_000,
        40_000,
        input_rate_per_million=1.0,
        output_rate_per_million=5.0,
    )

    assert cost == Decimal("0.30")
    assert cost.quantize(Decimal("0.01")) == Decimal("0.30")


def test_cost_from_token_usage_ignores_cache_counters() -> None:
    cost = cost_from_token_usage(
        {
            "input_tokens": 1_000_000,
            "output_tokens": 0,
            "cache_creation_input_tokens": 9_000_000,
            "cache_read_input_tokens": 9_000_000,
        },
        input_rate_per_million=1.0,
        output_rate_per_million=5.0,
    )

    assert cost == Decimal("1.00")


def test_missing_token_usage_keys_count_as_zero() -> None:
    assert cost_from_token_usage(
        {}, input_rate_per_million=1.0, output_rate_per_million=5.0
    ) == Decimal("0")


def test_negative_token_counts_are_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        cost_usd(-1, 0, input_rate_per_million=1.0, output_rate_per_million=5.0)


def test_spend_sums_runs_using_the_model_actually_used() -> None:
    spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
    slices = (
        LLMRunSpendSlice(
            model=spec.model_id,
            token_usage={"input_tokens": 1_000_000, "output_tokens": 0},
            created_at=_T0,
        ),
        LLMRunSpendSlice(
            model=spec.model_id,
            token_usage={"input_tokens": 0, "output_tokens": 200_000},
            created_at=_T0,
        ),
    )
    rates = {spec.model_id: (spec.input_rate_per_million, spec.output_rate_per_million)}

    # $1.00 input + 200_000 * $5/M = $1.00; total $2.00.
    assert spend_usd(slices, rates_per_million=rates) == Decimal("2.00")


def test_spend_rejects_a_model_missing_from_the_rate_table() -> None:
    slices = (
        LLMRunSpendSlice(
            model="claude-unknown-20990101",
            token_usage={"input_tokens": 1, "output_tokens": 0},
            created_at=_T0,
        ),
    )

    with pytest.raises(KeyError, match="no rate table row"):
        spend_usd(slices, rates_per_million={})


def test_below_soft_threshold_is_below_soft() -> None:
    assert classify_spend(Decimal("7.99"), _policy()) is BudgetBand.BELOW_SOFT


def test_exactly_at_soft_threshold_is_approaching() -> None:
    assert classify_spend(Decimal("8.00"), _policy()) is BudgetBand.APPROACHING


def test_between_soft_and_ceiling_is_approaching() -> None:
    assert classify_spend(Decimal("9.99"), _policy()) is BudgetBand.APPROACHING


def test_exactly_at_ceiling_is_at_ceiling() -> None:
    assert classify_spend(Decimal("10.00"), _policy()) is BudgetBand.AT_CEILING


def test_above_ceiling_is_at_ceiling() -> None:
    assert classify_spend(Decimal("10.01"), _policy()) is BudgetBand.AT_CEILING


def test_budget_policy_rejects_non_positive_ceiling_and_non_interior_ratio() -> None:
    with pytest.raises(ValueError, match="ceiling_usd"):
        _policy(ceiling="0")
    with pytest.raises(ValueError, match="soft_threshold_ratio"):
        _policy(ratio="0")
    with pytest.raises(ValueError, match="soft_threshold_ratio"):
        _policy(ratio="1")


def test_utc_month_bounds_are_half_open_calendar_month() -> None:
    start, end = utc_month_bounds(_T0)

    assert start == datetime(2026, 8, 1, tzinfo=UTC)
    assert end == datetime(2026, 9, 1, tzinfo=UTC)


def test_utc_month_bounds_roll_december_into_january() -> None:
    start, end = utc_month_bounds(datetime(2026, 12, 31, 23, 0, tzinfo=UTC))

    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


def test_utc_month_bounds_reject_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_month_bounds(datetime(2026, 8, 19, 12, 0))


def test_projected_monthly_cost_at_observed_document_rate_is_under_the_ceiling() -> None:
    """ADR-0015: ~2,500 in / ~500 out, ~900 docs/month, Haiku $1/$5 per 1M."""
    spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
    per_document = cost_usd(
        2_500,
        500,
        input_rate_per_million=spec.input_rate_per_million,
        output_rate_per_million=spec.output_rate_per_million,
    )
    projected = per_document * 900
    ceiling = Decimal("10")

    assert spec.model_id == "claude-haiku-4-5-20251001"
    assert per_document == Decimal("0.005")
    assert projected == Decimal("4.500")
    assert projected < ceiling
