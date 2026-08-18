"""Unit tests for LLMRun invariants (S001-T009) - no database.

Covers ARCHITECTURE_FOUNDATIONS.md section 7 and ADR-0007/ADR-0010:
`input_hash` alone is not sufficient (`input_reference_ids` must be
present), and model identifiers must be pinned, never a floating "latest"
alias.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.domain.llm_run import LLMRun

_CREATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _make_run(**overrides: object) -> LLMRun:
    defaults: dict[str, object] = dict(
        task_type="narrative_event_assignment",
        provider="anthropic",
        model="claude-sonnet-4-5-20250929",
        model_version="20250929",
        prompt_version="v1",
        system_prompt_version="v1",
        input_hash="abc123",
        input_reference_ids=("event:1234",),
        output_schema_version="v1",
        raw_output="{}",
        validation_status=CandidateStatus.ACCEPTED,
        created_at=_CREATED_AT,
    )
    defaults.update(overrides)
    return LLMRun(**defaults)  # type: ignore[arg-type]


def test_llm_run_rejects_empty_input_reference_ids() -> None:
    with pytest.raises(ValueError, match="input_reference_ids"):
        _make_run(input_reference_ids=())


@pytest.mark.parametrize("field_name", ["model", "model_version"])
def test_llm_run_rejects_floating_latest_alias(field_name: str) -> None:
    with pytest.raises(ValueError, match="pinned"):
        _make_run(**{field_name: "latest"})


def test_llm_run_rejects_negative_temperature() -> None:
    with pytest.raises(ValueError, match="temperature"):
        _make_run(temperature=-0.1)


def test_llm_run_rejects_negative_latency() -> None:
    with pytest.raises(ValueError, match="latency"):
        _make_run(latency=-1.0)


@pytest.mark.parametrize(
    "attr_name",
    [
        "task_type",
        "provider",
        "model",
        "model_version",
        "prompt_version",
        "system_prompt_version",
        "input_hash",
        "output_schema_version",
    ],
)
def test_llm_run_rejects_empty_required_string_fields(attr_name: str) -> None:
    with pytest.raises(ValueError, match=attr_name):
        _make_run(**{attr_name: "  "})


def test_llm_run_accepts_a_valid_run() -> None:
    run = _make_run()

    assert run.validation_status is CandidateStatus.ACCEPTED
    assert run.input_reference_ids == ("event:1234",)
