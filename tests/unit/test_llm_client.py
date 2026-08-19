"""Unit tests for the LLM client port (S002-T006) - no API key, no network."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from moj_projekt.config.settings import Settings
from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.domain.llm_run import LLMRun, reject_floating_model_alias
from moj_projekt.llm.anthropic_client import AnthropicClient, MissingAnthropicAPIKeyError
from moj_projekt.llm.artifacts import (
    DOCUMENT_TEXT_PLACEHOLDER,
    extraction_artifact_versions,
    load_event_extraction_prompt,
    load_output_schema,
    load_system_prompt,
    render_extraction_prompt,
)
from moj_projekt.llm.client import InferenceParams, LLMClient
from moj_projekt.llm.fake import FakeLLMClient
from moj_projekt.llm.models import (
    EVENT_EXTRACTION_TASK_TYPE,
    EXTRACTION_MODEL_ID,
    ModelSpec,
    model_spec_for,
    spec_for_model_id,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
_FIXTURE = _FIXTURES / "extraction_response_v1.json"
_CREATED_AT = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)

_FORBIDDEN_SCHEMA_FIELDS = frozenset(
    {
        "narrative_membership",
        "narrative_id",
        "assigned_narrative",
        "canonical_key",
        "instrument_relevance",
        "relevance",
        "direction",
        "instrument_direction",
        "impact_direction",
        "facts_and_claims",
        "merged_facts_and_claims",
        "combined_facts_and_claims",
    }
)
_REQUIRED_EVENT_FIELDS = frozenset(
    {
        "candidate_mechanism",
        "affected_entities_or_exposures",
        "candidate_interpretation",
        "extracted_facts",
        "source_claims",
    }
)


def _params() -> InferenceParams:
    spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
    return InferenceParams(
        model=spec.model_id,
        temperature=0.0,
        max_tokens=1024,
        system_prompt=load_system_prompt(),
        output_schema=load_output_schema(),
    )


def test_llm_client_exposes_exactly_one_call_method() -> None:
    public = {
        name
        for name, value in vars(LLMClient).items()
        if not name.startswith("_") and callable(value)
    }
    assert public == {"complete"}


def test_artifact_versions_are_explicit_and_returned_for_llmrun_recording() -> None:
    versions = extraction_artifact_versions()

    assert versions.prompt_version == "v1"
    assert versions.system_prompt_version == "v1"
    assert versions.output_schema_version == "v1"
    assert "v1" in load_system_prompt().splitlines()[0]
    assert DOCUMENT_TEXT_PLACEHOLDER in load_event_extraction_prompt()
    assert load_output_schema()["$id"].endswith(":v1")


def test_extraction_model_is_dated_pin_rejected_by_llmrun_latest_rule() -> None:
    spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)

    assert spec.model_id == EXTRACTION_MODEL_ID
    assert spec.model_id == "claude-haiku-4-5-20251001"
    assert spec.model_id != "claude-haiku-4-5"

    run = LLMRun(
        task_type=EVENT_EXTRACTION_TASK_TYPE,
        provider="anthropic",
        model=spec.model_id,
        model_version=spec.model_version,
        prompt_version="v1",
        system_prompt_version="v1",
        input_hash="abc123",
        input_reference_ids=("document:1",),
        output_schema_version="v1",
        raw_output="{}",
        validation_status=CandidateStatus.ACCEPTED,
        created_at=_CREATED_AT,
    )
    assert run.model == spec.model_id

    with pytest.raises(ValueError, match="pinned"):
        reject_floating_model_alias("latest", field_name="model")
    with pytest.raises(ValueError, match="pinned"):
        LLMRun(
            task_type=EVENT_EXTRACTION_TASK_TYPE,
            provider="anthropic",
            model="latest",
            model_version=spec.model_version,
            prompt_version="v1",
            system_prompt_version="v1",
            input_hash="abc123",
            input_reference_ids=("document:1",),
            output_schema_version="v1",
            raw_output="{}",
            validation_status=CandidateStatus.ACCEPTED,
            created_at=_CREATED_AT,
        )


def test_spec_for_model_id_returns_the_extraction_rate_row() -> None:
    spec = spec_for_model_id(EXTRACTION_MODEL_ID)

    assert spec == model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
    assert spec.input_rate_per_million == 1.0
    assert spec.output_rate_per_million == 5.0
    with pytest.raises(KeyError, match="no rate table row"):
        spec_for_model_id("claude-unknown-20990101")


def test_undated_alias_is_rejected_by_the_rate_table() -> None:
    with pytest.raises(ValueError, match="dated pinned"):
        ModelSpec(
            model_id="claude-haiku-4-5",
            model_version="4-5",
            input_rate_per_million=1.0,
            output_rate_per_million=5.0,
        )
    with pytest.raises(ValueError, match="pinned"):
        ModelSpec(
            model_id="latest",
            model_version="20251001",
            input_rate_per_million=1.0,
            output_rate_per_million=5.0,
        )


def test_fake_llm_client_replays_fixture_byte_for_byte_and_counts_calls() -> None:
    recorded = _FIXTURE.read_bytes()
    client = FakeLLMClient.from_fixture(_FIXTURE)

    first = client.complete("ignored-prompt", _params())
    second = client.complete("another-prompt", _params())

    assert first.raw_output.encode("utf-8") == recorded
    assert second.raw_output.encode("utf-8") == recorded
    assert client.call_count == 2
    assert first.token_usage.cache_creation_input_tokens == 0
    assert first.token_usage.cache_read_input_tokens == 0


def test_anthropic_client_without_key_fails_clearly() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        postgres_password="secret",
        anthropic_api_key=None,
    )

    with pytest.raises(MissingAnthropicAPIKeyError, match="ANTHROPIC_API_KEY"):
        AnthropicClient(settings)


def test_anthropic_client_blank_key_fails_clearly() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        postgres_password="secret",
        anthropic_api_key="   ",
    )

    with pytest.raises(MissingAnthropicAPIKeyError, match="ANTHROPIC_API_KEY"):
        AnthropicClient(settings)


def _schema_property_names(node: object) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(str(key) for key in properties)
            for value in properties.values():
                names |= _schema_property_names(value)
        for key, value in node.items():
            if key != "properties":
                names |= _schema_property_names(value)
    elif isinstance(node, list):
        for item in node:
            names |= _schema_property_names(item)
    return names


def test_output_schema_v1_carries_extracted_material_and_forbids_phase4_fields() -> None:
    schema = load_output_schema()
    names = _schema_property_names(schema)

    assert names >= _REQUIRED_EVENT_FIELDS
    assert not (names & _FORBIDDEN_SCHEMA_FIELDS)
    assert "extracted_facts" in names
    assert "source_claims" in names
    assert not any("merged" in name or "combined" in name for name in names)


def test_render_extraction_prompt_substitutes_document_text() -> None:
    rendered = render_extraction_prompt("The committee held rates.")

    assert "The committee held rates." in rendered
    assert DOCUMENT_TEXT_PLACEHOLDER not in rendered
