"""Unit tests for extraction prompt rendering and LLMRun field assembly."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from moj_projekt.domain.document import Document
from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.extraction.service import (
    EXTRACTION_MAX_TOKENS,
    EXTRACTION_PROVIDER,
    EXTRACTION_TEMPERATURE,
    ExtractionService,
    assemble_llm_run,
    document_text_for_extraction,
    events_from_accepted_output,
    hash_extraction_input,
    token_usage_mapping,
)
from moj_projekt.extraction.types import (
    DocumentContext,
    ExtractionValidationResult,
    ValidationConfig,
    ValidationError,
    ValidationErrorCode,
)
from moj_projekt.llm.artifacts import (
    DOCUMENT_TEXT_PLACEHOLDER,
    extraction_artifact_versions,
    render_extraction_prompt,
)
from moj_projekt.llm.client import LLMResponse, TokenUsage
from moj_projekt.llm.fake import FakeLLMClient
from moj_projekt.llm.models import EVENT_EXTRACTION_TASK_TYPE, EXTRACTION_MODEL_ID, model_spec_for

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / "extraction_response_v1.json"
_T0 = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 17, 18, 0, tzinfo=UTC)
_DOCUMENT_ID = uuid4()
_CONFIG = ValidationConfig(
    auto_accept_min_confidence=0.7,
    occurred_at_max_before=timedelta(days=365),
    occurred_at_max_after=timedelta(days=2),
)


class _FixedClock:
    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at


def _document(**overrides: object) -> Document:
    defaults: dict[str, object] = dict(
        source_key="bloomberg_markets",
        source_type="rss",
        url="https://example.com/fed-holds",
        published_at=_PUBLISHED,
        collected_at=_PUBLISHED + timedelta(minutes=5),
        title="Fed holds policy rate",
        content="The Federal Reserve left the policy rate unchanged.",
        source_native_id="guid-1",
        id=_DOCUMENT_ID,
    )
    defaults.update(overrides)
    return Document(**defaults)  # type: ignore[arg-type]


def test_document_text_is_substituted_into_the_versioned_prompt() -> None:
    document = _document()
    text = document_text_for_extraction(document)
    rendered = render_extraction_prompt(text)

    assert document.title in text
    assert document.content in text
    assert DOCUMENT_TEXT_PLACEHOLDER not in rendered
    assert document.title in rendered
    assert document.content in rendered
    versions = extraction_artifact_versions()
    assert versions.prompt_version == "v1"


def test_input_hash_is_sha256_of_the_rendered_prompt() -> None:
    rendered = render_extraction_prompt("hello")
    digest = hash_extraction_input(rendered)

    assert digest == hash_extraction_input(rendered)
    assert digest != hash_extraction_input(render_extraction_prompt("other"))
    assert len(digest) == 64
    assert digest == hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def test_assemble_llm_run_carries_every_adr_0007_field() -> None:
    raw = _FIXTURE.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    document = _document()
    rendered = render_extraction_prompt(document_text_for_extraction(document))
    usage = TokenUsage(
        input_tokens=11,
        output_tokens=22,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    response = LLMResponse(raw_output=raw, token_usage=usage, latency_seconds=1.25)
    validation = ExtractionValidationResult(
        verdict=CandidateStatus.ACCEPTED,
        errors=(),
        parsed_output=parsed,
        raw_output=raw,
    )
    spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
    run = assemble_llm_run(
        document_id=_DOCUMENT_ID,
        rendered_prompt=rendered,
        response=response,
        validation=validation,
        versions=extraction_artifact_versions(),
        model_spec=spec,
        created_at=_T0,
        temperature=EXTRACTION_TEMPERATURE,
        max_tokens=EXTRACTION_MAX_TOKENS,
    )

    assert run.task_type == EVENT_EXTRACTION_TASK_TYPE
    assert run.provider == EXTRACTION_PROVIDER
    assert run.model == EXTRACTION_MODEL_ID
    assert run.model != "latest"
    assert run.model_version == spec.model_version
    assert run.prompt_version == "v1"
    assert run.system_prompt_version == "v1"
    assert run.output_schema_version == "v1"
    assert run.input_hash == hash_extraction_input(rendered)
    assert run.input_reference_ids == (str(_DOCUMENT_ID),)
    assert run.raw_output == raw
    assert run.parsed_output == parsed
    assert run.validation_status is CandidateStatus.ACCEPTED
    assert run.validation_errors == ()
    assert run.temperature == EXTRACTION_TEMPERATURE
    assert run.inference_parameters == {"max_tokens": EXTRACTION_MAX_TOKENS}
    assert run.token_usage == token_usage_mapping(usage)
    assert run.latency == 1.25
    assert run.created_at == _T0


def test_assemble_llm_run_keeps_rejected_raw_output_and_errors() -> None:
    raw = "this is not json {"
    response = LLMResponse(
        raw_output=raw,
        token_usage=TokenUsage(1, 2, 0, 0),
        latency_seconds=0.1,
    )
    error = ValidationError(
        code=ValidationErrorCode.UNPARSEABLE,
        message="Raw model output is not valid JSON",
        json_path="$",
    )
    validation = ExtractionValidationResult(
        verdict=CandidateStatus.REJECTED,
        errors=(error,),
        parsed_output=None,
        raw_output=raw,
    )
    run = assemble_llm_run(
        document_id=_DOCUMENT_ID,
        rendered_prompt="unused",
        response=response,
        validation=validation,
        versions=extraction_artifact_versions(),
        model_spec=model_spec_for(EVENT_EXTRACTION_TASK_TYPE),
        created_at=_T0,
        temperature=EXTRACTION_TEMPERATURE,
        max_tokens=EXTRACTION_MAX_TOKENS,
    )

    assert run.validation_status is CandidateStatus.REJECTED
    assert run.raw_output == raw
    assert run.parsed_output is None
    assert run.validation_errors == (error.to_llm_run_record(),)


def test_events_from_accepted_output_reference_the_document() -> None:
    parsed = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    events = events_from_accepted_output(parsed, document_id=_DOCUMENT_ID)

    assert len(events) == 1
    event = events[0]
    assert event.source_ids == (_DOCUMENT_ID,)
    assert event.type == "rate_decision"
    assert event.title == "Federal Reserve holds the policy rate unchanged"
    assert event.confidence == 0.86
    assert event.extracted_facts
    assert event.source_claims
    assert "candidate_mechanism" not in event.__dataclass_fields__


def test_empty_accepted_payload_yields_no_events() -> None:
    events = events_from_accepted_output({"events": []}, document_id=_DOCUMENT_ID)
    assert events == ()


def test_unpersisted_document_is_rejected_before_the_model_call() -> None:
    client = FakeLLMClient(b'{"events":[]}')
    service = ExtractionService(
        client=client,
        clock=_FixedClock(_T0),
        validation_config=_CONFIG,
    )
    document = _document(id=None)

    with pytest.raises(ValueError, match="persisted Document"):
        service.extract(document, uow=None)  # type: ignore[arg-type]

    assert client.call_count == 0


def test_document_context_from_document_keeps_published_at() -> None:
    document = _document()
    context = DocumentContext(document_id=document.id, published_at=document.published_at)
    assert context.document_id == _DOCUMENT_ID
    assert context.published_at == _PUBLISHED
