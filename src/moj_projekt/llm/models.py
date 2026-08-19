"""Declarative task-type -> pinned model id, version, and per-1M rates.

Extraction maps to ``claude-haiku-4-5-20251001`` (ADR-0016). Rates are the
current Haiku 4.5 figures recorded in ADR-0015 ($1 in / $5 out per 1M).
Undated aliases and ``latest`` are rejected by the same rule ``LLMRun`` uses.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from moj_projekt.domain.llm_run import reject_floating_model_alias

__all__ = [
    "EVENT_EXTRACTION_TASK_TYPE",
    "EXTRACTION_MODEL_ID",
    "ModelSpec",
    "TASK_MODELS",
    "model_spec_for",
    "rates_per_million_by_model_id",
    "spec_for_model_id",
]

EVENT_EXTRACTION_TASK_TYPE = "event_extraction"
EXTRACTION_MODEL_ID = "claude-haiku-4-5-20251001"

# Haiku 4.5 current rates (ADR-0015). A provider price change is a row edit.
_HAIKU_4_5_INPUT_RATE_PER_MILLION = 1.0
_HAIKU_4_5_OUTPUT_RATE_PER_MILLION = 5.0

_DATED_MODEL_ID = re.compile(r".+-\d{8}$")


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Pinned model identity and the rates ADR-0015 derives cost from."""

    model_id: str
    model_version: str
    input_rate_per_million: float
    output_rate_per_million: float

    def __post_init__(self) -> None:
        reject_floating_model_alias(self.model_id, field_name="model_id")
        reject_floating_model_alias(self.model_version, field_name="model_version")
        if _DATED_MODEL_ID.match(self.model_id) is None:
            raise ValueError(
                f"model_id {self.model_id!r} is not a dated pinned identifier "
                "(ADR-0010, ADR-0016); undated aliases are forbidden"
            )


TASK_MODELS: Mapping[str, ModelSpec] = {
    EVENT_EXTRACTION_TASK_TYPE: ModelSpec(
        model_id=EXTRACTION_MODEL_ID,
        model_version="20251001",
        input_rate_per_million=_HAIKU_4_5_INPUT_RATE_PER_MILLION,
        output_rate_per_million=_HAIKU_4_5_OUTPUT_RATE_PER_MILLION,
    ),
}


def model_spec_for(task_type: str) -> ModelSpec:
    """Return the pinned spec for ``task_type``.

    Raises:
        KeyError: if ``task_type`` has no row in ``TASK_MODELS``.
    """
    return TASK_MODELS[task_type]


def spec_for_model_id(model_id: str) -> ModelSpec:
    """Return the rate-table row for the pinned ``model_id`` actually used.

    Cost follows the model on the ``LLMRun``, not the current task-type
    mapping, so a later remapping does not rewrite historical spend
    (ADR-0015 clause 3, ADR-0016 clause 3).
    """
    for spec in TASK_MODELS.values():
        if spec.model_id == model_id:
            return spec
    raise KeyError(f"no rate table row for model {model_id!r}")


def rates_per_million_by_model_id() -> Mapping[str, tuple[float, float]]:
    """``model_id -> (input_rate_per_million, output_rate_per_million)``."""
    return {
        spec.model_id: (spec.input_rate_per_million, spec.output_rate_per_million)
        for spec in TASK_MODELS.values()
    }
