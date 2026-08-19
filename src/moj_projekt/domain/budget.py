"""Monthly LLM cost ceiling: pure cost arithmetic and threshold bands.

ADR-0015: spend is derived from recorded ``token_usage`` and the rate that
applied to the model actually used. The extract stage compares that spend
to a configured ceiling and soft threshold; this module has no repository
or clock of its own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

__all__ = [
    "BUDGET_APPROACHING_KEY",
    "BUDGET_CEILING_KEY",
    "CEILING_REACHED_REASON",
    "BudgetBand",
    "BudgetPolicy",
    "LLMRunSpendSlice",
    "classify_spend",
    "cost_from_token_usage",
    "cost_usd",
    "spend_usd",
    "utc_month_bounds",
]

# CycleRun.source_outcomes keys. Document ids and ingest source keys do not
# collide with these names. The approaching band records presence only
# (succeeded=True); the ceiling band carries the human-readable reason.
BUDGET_APPROACHING_KEY = "llm_budget_approaching"
BUDGET_CEILING_KEY = "llm_budget_ceiling"
CEILING_REACHED_REASON = (
    "monthly LLM cost ceiling reached; remaining COLLECTED documents were not sent for extraction"
)

_MILLION = Decimal("1000000")


class BudgetBand(StrEnum):
    """Where current-period spend sits relative to the configured policy."""

    BELOW_SOFT = "below_soft"
    APPROACHING = "approaching"
    AT_CEILING = "at_ceiling"


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """Configured monthly ceiling and the soft threshold as a fraction of it.

    Both values are configuration, not constants in the extract stage.
    ``soft_threshold_ratio`` is exclusive of 0 and 1 so the three bands stay
    distinguishable (ADR-0015 clause 4).
    """

    ceiling_usd: Decimal
    soft_threshold_ratio: Decimal

    def __post_init__(self) -> None:
        if self.ceiling_usd <= 0:
            raise ValueError("BudgetPolicy.ceiling_usd must be positive")
        if self.soft_threshold_ratio <= 0 or self.soft_threshold_ratio >= 1:
            raise ValueError("BudgetPolicy.soft_threshold_ratio must be between 0 and 1 exclusive")

    @property
    def soft_threshold_usd(self) -> Decimal:
        return self.ceiling_usd * self.soft_threshold_ratio


@dataclass(frozen=True, slots=True)
class LLMRunSpendSlice:
    """The fields needed to price one ``LLMRun``. Not the full audit record."""

    model: str
    token_usage: Mapping[str, Any]
    created_at: datetime


def utc_month_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """Return the half-open UTC calendar month ``[start, end)`` containing ``moment``.

    The budget period is the calendar month of the injected cycle clock
    (``CycleRun.started_at``), never ``datetime.now()``.
    """
    if moment.tzinfo is None:
        raise ValueError("utc_month_bounds requires a timezone-aware datetime")
    utc_moment = moment.astimezone(UTC)
    start = datetime(utc_moment.year, utc_moment.month, 1, tzinfo=UTC)
    if utc_moment.month == 12:
        end = datetime(utc_moment.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(utc_moment.year, utc_moment.month + 1, 1, tzinfo=UTC)
    return start, end


def cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    input_rate_per_million: float | Decimal,
    output_rate_per_million: float | Decimal,
) -> Decimal:
    """USD cost of one run from token counts and per-1M rates.

    Cache counters are not priced: the rate table has input/output rates
    only (ADR-0015 clause 6 records cache tokens; it does not bill them).
    """
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must not be negative")
    input_rate = _as_decimal(input_rate_per_million)
    output_rate = _as_decimal(output_rate_per_million)
    if input_rate < 0 or output_rate < 0:
        raise ValueError("token rates must not be negative")
    return (
        Decimal(input_tokens) / _MILLION * input_rate
        + Decimal(output_tokens) / _MILLION * output_rate
    )


def cost_from_token_usage(
    token_usage: Mapping[str, Any],
    *,
    input_rate_per_million: float | Decimal,
    output_rate_per_million: float | Decimal,
) -> Decimal:
    """USD cost of a stored ``LLMRun.token_usage`` mapping against given rates."""
    return cost_usd(
        _token_count(token_usage, "input_tokens"),
        _token_count(token_usage, "output_tokens"),
        input_rate_per_million=input_rate_per_million,
        output_rate_per_million=output_rate_per_million,
    )


def spend_usd(
    slices: Sequence[LLMRunSpendSlice],
    *,
    rates_per_million: Mapping[str, tuple[float, float]],
) -> Decimal:
    """Sum USD cost of ``slices`` using per-model input/output rates.

    Raises:
        KeyError: if a slice's ``model`` has no row in ``rates_per_million``.
    """
    total = Decimal("0")
    for item in slices:
        try:
            input_rate, output_rate = rates_per_million[item.model]
        except KeyError as exc:
            raise KeyError(f"no rate table row for model {item.model!r}") from exc
        total += cost_from_token_usage(
            item.token_usage,
            input_rate_per_million=input_rate,
            output_rate_per_million=output_rate,
        )
    return total


def classify_spend(spend: Decimal, policy: BudgetPolicy) -> BudgetBand:
    """Place ``spend`` in the below-soft / approaching / at-ceiling band."""
    if spend >= policy.ceiling_usd:
        return BudgetBand.AT_CEILING
    if spend >= policy.soft_threshold_usd:
        return BudgetBand.APPROACHING
    return BudgetBand.BELOW_SOFT


def _as_decimal(value: float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _token_count(token_usage: Mapping[str, Any], key: str) -> int:
    raw = token_usage.get(key, 0)
    if raw is None:
        raw = 0
    count = int(raw)
    if count < 0:
        raise ValueError(f"token_usage[{key!r}] must not be negative")
    return count
