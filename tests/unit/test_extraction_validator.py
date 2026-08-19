"""Unit tests for the extraction validation layer (S002-T007) - no infrastructure."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.domain.event import Event
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.extraction import (
    DocumentContext,
    ExtractionValidationResult,
    ValidationConfig,
    ValidationErrorCode,
    validate_extraction,
)
from moj_projekt.extraction.market_language import ALLOWED_MARKET_PHRASES, FORBIDDEN_MARKET_PHRASES
from moj_projekt.llm.artifacts import load_output_schema
from moj_projekt.llm.models import EVENT_EXTRACTION_TASK_TYPE, EXTRACTION_MODEL_ID

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / "extraction_response_v1.json"
_PUBLISHED_AT = datetime(2026, 8, 17, 18, 0, tzinfo=UTC)
_DOCUMENT_ID = uuid4()
_CONFIG = ValidationConfig(
    auto_accept_min_confidence=0.7,
    occurred_at_max_before=timedelta(days=365),
    occurred_at_max_after=timedelta(days=2),
)


def _load_fixture() -> dict[str, object]:
    loaded: object = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _event(**overrides: object) -> dict[str, object]:
    events = _load_fixture()["events"]
    assert isinstance(events, list)
    event = deepcopy(events[0])
    assert isinstance(event, dict)
    event.update(overrides)
    return event


def _raw(events: list[object]) -> str:
    return json.dumps({"events": events})


def _document(
    *,
    document_id: UUID | None = _DOCUMENT_ID,
    published_at: datetime = _PUBLISHED_AT,
) -> DocumentContext:
    return DocumentContext(document_id=document_id, published_at=published_at)


def _validate(
    raw: str,
    *,
    document: DocumentContext | None = None,
    config: ValidationConfig | None = None,
) -> ExtractionValidationResult:
    return validate_extraction(
        raw,
        document=document if document is not None else _document(),
        config=config if config is not None else _CONFIG,
        schema=load_output_schema(),
    )


def _assert_only_rule(
    result: ExtractionValidationResult,
    code: ValidationErrorCode,
    *,
    verdict: CandidateStatus = CandidateStatus.REJECTED,
    message_must_include: str,
) -> None:
    assert result.verdict is verdict
    assert result.error_codes
    assert set(result.error_codes) == {code}
    assert any(message_must_include in error.message for error in result.errors)
    for error in result.errors:
        assert error.message.strip()
        assert isinstance(error.to_llm_run_record(), str)


# --- hard rules (one isolated test each) ---


def test_unparseable_output_is_rejected() -> None:
    result = _validate("this is not json {")

    _assert_only_rule(
        result,
        ValidationErrorCode.UNPARSEABLE,
        message_must_include="not valid JSON",
    )
    assert result.parsed_output is None
    assert result.raw_output == "this is not json {"


def test_json_array_is_unparseable_not_a_schema_miss() -> None:
    result = _validate("[]")

    _assert_only_rule(
        result,
        ValidationErrorCode.UNPARSEABLE,
        message_must_include="JSON object",
    )


def test_schema_v1_violation_is_rejected() -> None:
    event = _event()
    del event["title"]
    result = _validate(_raw([event]))

    _assert_only_rule(
        result,
        ValidationErrorCode.SCHEMA_V1_VIOLATION,
        message_must_include="missing required property 'title'",
    )


def test_confidence_outside_zero_one_is_a_schema_v1_violation() -> None:
    result = _validate(_raw([_event(confidence=1.5)]))

    _assert_only_rule(
        result,
        ValidationErrorCode.SCHEMA_V1_VIOLATION,
        message_must_include="maximum",
    )


def test_event_with_no_facts_or_claims_is_rejected_for_missing_document_reference() -> None:
    result = _validate(_raw([_event(extracted_facts=[], source_claims=[])]))

    _assert_only_rule(
        result,
        ValidationErrorCode.MISSING_DOCUMENT_REFERENCE,
        message_must_include="no supporting document reference",
    )


def test_occurred_at_outside_plausibility_window_is_rejected() -> None:
    result = _validate(_raw([_event(occurred_at="2020-01-01T00:00:00Z")]))

    _assert_only_rule(
        result,
        ValidationErrorCode.OCCURRED_AT_IMPLAUSIBLE,
        message_must_include="outside the plausibility window",
    )


def test_merge_field_is_rejected_as_merged_facts_and_claims_not_schema() -> None:
    event = _event()
    event["facts_and_claims"] = []
    result = _validate(_raw([event]))

    _assert_only_rule(
        result,
        ValidationErrorCode.MERGED_FACTS_AND_CLAIMS,
        message_must_include="merges facts and claims",
    )


def test_duplicate_fact_and_claim_text_is_rejected_as_merged_facts_and_claims() -> None:
    shared = "The Federal Reserve left the policy rate unchanged."
    result = _validate(
        _raw(
            [
                _event(
                    extracted_facts=[
                        {"text": shared, "epistemic_category": "observed_fact"}
                    ],
                    source_claims=[
                        {
                            "text": shared,
                            "epistemic_category": "source_claim",
                            "attributed_to": "FOMC statement",
                        }
                    ],
                )
            ]
        )
    )

    _assert_only_rule(
        result,
        ValidationErrorCode.MERGED_FACTS_AND_CLAIMS,
        message_must_include="share text",
    )


@pytest.mark.parametrize("term", ["forecast", "prediction", "signal", "sentiment_score"])
def test_forbidden_vocabulary_in_generated_text_is_rejected(term: str) -> None:
    result = _validate(_raw([_event(title=f"Federal Reserve {term} of an unchanged rate")]))

    _assert_only_rule(
        result,
        ValidationErrorCode.FORBIDDEN_VOCABULARY,
        message_must_include=term,
    )


@pytest.mark.parametrize("phrase", FORBIDDEN_MARKET_PHRASES)
def test_forbidden_market_pricing_language_is_rejected(phrase: str) -> None:
    result = _validate(
        _raw([_event(candidate_interpretation=f"{phrase} a prolonged pause.")])
    )

    _assert_only_rule(
        result,
        ValidationErrorCode.MARKET_PRICING_LANGUAGE,
        message_must_include=phrase,
    )


@pytest.mark.parametrize("field_name", ["type", "title"])
def test_whitespace_only_event_field_is_rejected_as_event_invariant(field_name: str) -> None:
    result = _validate(_raw([_event(**{field_name: "   "})]))

    _assert_only_rule(
        result,
        ValidationErrorCode.EVENT_INVARIANT,
        message_must_include=field_name,
    )


def test_missing_document_id_is_rejected_as_empty_source_ids_invariant() -> None:
    result = _validate(_raw([_event()]), document=_document(document_id=None))

    _assert_only_rule(
        result,
        ValidationErrorCode.EVENT_INVARIANT,
        message_must_include="source_ids would be empty",
    )


# --- soft rule ---


def test_below_threshold_confidence_yields_proposed_without_constructing_event() -> None:
    result = _validate(_raw([_event(confidence=0.4)]))

    _assert_only_rule(
        result,
        ValidationErrorCode.BELOW_AUTO_ACCEPT_THRESHOLD,
        verdict=CandidateStatus.PROPOSED,
        message_must_include="below the auto-accept threshold",
    )
    assert "event" not in result.__dataclass_fields__
    assert not isinstance(result.parsed_output, Event)


def test_auto_accept_threshold_is_taken_from_config_not_rule_bodies() -> None:
    raw = _raw([_event(confidence=0.5)])
    accepted = _validate(
        raw,
        config=ValidationConfig(
            auto_accept_min_confidence=0.4,
            occurred_at_max_before=_CONFIG.occurred_at_max_before,
            occurred_at_max_after=_CONFIG.occurred_at_max_after,
        ),
    )
    proposed = _validate(
        raw,
        config=ValidationConfig(
            auto_accept_min_confidence=0.7,
            occurred_at_max_before=_CONFIG.occurred_at_max_before,
            occurred_at_max_after=_CONFIG.occurred_at_max_after,
        ),
    )

    assert accepted.verdict is CandidateStatus.ACCEPTED
    assert proposed.verdict is CandidateStatus.PROPOSED


def test_occurred_at_window_is_taken_from_config() -> None:
    raw = _raw([_event(occurred_at="2025-08-17T18:00:00Z")])
    tight = _validate(
        raw,
        config=ValidationConfig(
            auto_accept_min_confidence=_CONFIG.auto_accept_min_confidence,
            occurred_at_max_before=timedelta(days=30),
            occurred_at_max_after=_CONFIG.occurred_at_max_after,
        ),
    )
    wide = _validate(
        raw,
        config=ValidationConfig(
            auto_accept_min_confidence=_CONFIG.auto_accept_min_confidence,
            occurred_at_max_before=timedelta(days=400),
            occurred_at_max_after=_CONFIG.occurred_at_max_after,
        ),
    )

    assert tight.verdict is CandidateStatus.REJECTED
    assert tight.error_codes == (ValidationErrorCode.OCCURRED_AT_IMPLAUSIBLE,)
    assert wide.verdict is CandidateStatus.ACCEPTED


# --- pass cases ---


@pytest.mark.parametrize(
    "label, raw",
    [
        ("fixture_v1", _FIXTURE.read_text(encoding="utf-8")),
        ("empty_events", json.dumps({"events": []})),
        (
            "confidence_at_threshold",
            _raw([_event(confidence=0.7)]),
        ),
        (
            "occurred_at_equals_published_at",
            _raw([_event(occurred_at="2026-08-17T18:00:00Z")]),
        ),
        *[
            (
                f"allowed_market_phrase_{index}",
                _raw([_event(candidate_interpretation=f"{phrase} a pause.")]),
            )
            for index, phrase in enumerate(ALLOWED_MARKET_PHRASES)
        ],
    ],
)
def test_table_driven_pass_is_accepted(label: str, raw: str) -> None:
    result = _validate(raw)

    assert result.verdict is CandidateStatus.ACCEPTED, label
    assert result.errors == ()
    assert result.raw_output == raw
    if result.parsed_output is not None:
        assert result.parsed_output == json.loads(raw)


def test_validator_does_not_mutate_or_repair_model_output() -> None:
    event = _event(title="  Federal Reserve holds the policy rate unchanged")
    raw = _raw([event])
    original = json.loads(raw)
    result = _validate(raw)

    assert result.raw_output is raw
    assert result.parsed_output == original
    assert original["events"][0]["title"].startswith("  ")


def test_validation_errors_are_storable_verbatim_on_llmrun() -> None:
    result = _validate("not-json")
    records = result.llm_run_records()
    run = LLMRun(
        task_type=EVENT_EXTRACTION_TASK_TYPE,
        provider="anthropic",
        model=EXTRACTION_MODEL_ID,
        model_version="4.5",
        prompt_version="v1",
        system_prompt_version="v1",
        input_hash="abc123",
        input_reference_ids=(str(_DOCUMENT_ID),),
        output_schema_version="v1",
        raw_output="not-json",
        validation_status=result.verdict,
        created_at=_PUBLISHED_AT,
        validation_errors=records,
    )
    stored = json.loads(run.validation_errors[0])
    assert stored["code"] == ValidationErrorCode.UNPARSEABLE
    assert stored["message"]
    assert stored["json_path"] == "$"
    assert run.validation_errors == records


def test_hard_rule_beats_low_confidence_and_does_not_propose() -> None:
    result = _validate(_raw([_event(title="   ", confidence=0.1)]))

    _assert_only_rule(
        result,
        ValidationErrorCode.EVENT_INVARIANT,
        message_must_include="title",
    )
