"""Extraction service: one Document -> verdict -> Event + LLMRun atomically.

The validator judges; this module is the only extraction code that
constructs an :class:`~moj_projekt.domain.event.Event`, and only when the
verdict is ``accepted`` (ADR-0002). Persistence goes through a caller-owned
:class:`~moj_projekt.domain.repositories.UnitOfWork` so the ``LLMRun`` and
any Events commit or roll back together (ADR-0007, D-S002-04 clause 6).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from moj_projekt.domain.clock import Clock
from moj_projekt.domain.document import Document
from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.domain.event import Event
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.extraction.types import (
    DocumentContext,
    ExtractionValidationResult,
    ValidationConfig,
)
from moj_projekt.extraction.validator import validate_extraction
from moj_projekt.llm.artifacts import (
    ArtifactVersions,
    extraction_artifact_versions,
    load_output_schema,
    load_system_prompt,
    render_extraction_prompt,
)
from moj_projekt.llm.client import InferenceParams, LLMClient, LLMResponse, TokenUsage
from moj_projekt.llm.models import EVENT_EXTRACTION_TASK_TYPE, ModelSpec, model_spec_for

__all__ = [
    "EXTRACTION_MAX_TOKENS",
    "EXTRACTION_PROVIDER",
    "EXTRACTION_TEMPERATURE",
    "ExtractionOutcome",
    "ExtractionService",
    "assemble_llm_run",
    "document_text_for_extraction",
    "events_from_accepted_output",
    "hash_extraction_input",
    "token_usage_mapping",
]

EXTRACTION_PROVIDER = "anthropic"
EXTRACTION_TEMPERATURE = 0.0
EXTRACTION_MAX_TOKENS = 4096


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    """Persisted consequences of one Document extraction."""

    verdict: CandidateStatus
    llm_run: LLMRun
    events: tuple[Event, ...]


def document_text_for_extraction(document: Document) -> str:
    """Compose the text substituted into the versioned extraction prompt."""
    return f"{document.title}\n\n{document.content}"


def hash_extraction_input(rendered_prompt: str) -> str:
    """SHA-256 of the rendered prompt the model actually saw (ADR-0007)."""
    return hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()


def token_usage_mapping(usage: TokenUsage) -> dict[str, int]:
    """``LLMRun.token_usage`` payload, including unused cache counters."""
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        "cache_read_input_tokens": usage.cache_read_input_tokens,
    }


def assemble_llm_run(
    *,
    document_id: UUID,
    rendered_prompt: str,
    response: LLMResponse,
    validation: ExtractionValidationResult,
    versions: ArtifactVersions,
    model_spec: ModelSpec,
    created_at: datetime,
    temperature: float,
    max_tokens: int,
) -> LLMRun:
    """Build the ADR-0007 audit record for one extraction call."""
    parsed = validation.parsed_output
    return LLMRun(
        task_type=EVENT_EXTRACTION_TASK_TYPE,
        provider=EXTRACTION_PROVIDER,
        model=model_spec.model_id,
        model_version=model_spec.model_version,
        prompt_version=versions.prompt_version,
        system_prompt_version=versions.system_prompt_version,
        input_hash=hash_extraction_input(rendered_prompt),
        input_reference_ids=(str(document_id),),
        output_schema_version=versions.output_schema_version,
        raw_output=response.raw_output,
        validation_status=validation.verdict,
        created_at=created_at,
        parsed_output=dict(parsed) if parsed is not None else None,
        validation_errors=validation.llm_run_records(),
        temperature=temperature,
        inference_parameters={"max_tokens": max_tokens},
        token_usage=token_usage_mapping(response.token_usage),
        latency=response.latency_seconds,
    )


def events_from_accepted_output(
    parsed_output: Mapping[str, Any],
    *,
    document_id: UUID,
) -> tuple[Event, ...]:
    """Construct domain Events from a schema-valid accepted payload.

    ``source_ids`` always reference the Document under extraction, not a
    model-supplied id. Candidate mechanism/interpretation stay on the
    ``LLMRun.parsed_output``; they are not Event columns (D-S002-04 clause 11).
    """
    raw_events = parsed_output["events"]
    if not isinstance(raw_events, list):
        raise TypeError("accepted parsed_output.events must be a list")
    return tuple(
        _event_from_payload(cast(Mapping[str, Any], item), document_id=document_id)
        for item in raw_events
    )


def _event_from_payload(payload: Mapping[str, Any], *, document_id: UUID) -> Event:
    occurred_at = datetime.fromisoformat(cast(str, payload["occurred_at"]))
    return Event(
        type=cast(str, payload["type"]),
        title=cast(str, payload["title"]),
        occurred_at=occurred_at,
        source_ids=(document_id,),
        confidence=float(cast(int | float, payload["confidence"])),
        entities=_string_tuple(payload.get("entities")),
        topics=_string_tuple(payload.get("topics")),
        extracted_facts=_mapping_tuple(payload.get("extracted_facts")),
        source_claims=_mapping_tuple(payload.get("source_claims")),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _mapping_tuple(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


class ExtractionService:
    """Render, call, validate, and persist one Document's extraction."""

    def __init__(
        self,
        *,
        client: LLMClient,
        clock: Clock,
        validation_config: ValidationConfig,
    ) -> None:
        self._client = client
        self._clock = clock
        self._validation_config = validation_config

    def extract(self, document: Document, uow: UnitOfWork) -> ExtractionOutcome:
        """Produce a verdict and persist its consequences in ``uow``.

        The ``LLMRun`` is always written. Event rows are written only when
        the validator returns ``accepted``. The caller owns commit/rollback.
        """
        if document.id is None:
            raise ValueError(
                "Extraction requires a persisted Document with an id "
                "(LLMRun.input_reference_ids must resolve to documents.id)"
            )

        schema = load_output_schema()
        versions = extraction_artifact_versions()
        model_spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
        rendered_prompt = render_extraction_prompt(document_text_for_extraction(document))
        response = self._client.complete(
            rendered_prompt,
            InferenceParams(
                model=model_spec.model_id,
                temperature=EXTRACTION_TEMPERATURE,
                max_tokens=EXTRACTION_MAX_TOKENS,
                system_prompt=load_system_prompt(),
                output_schema=schema,
            ),
        )
        validation = validate_extraction(
            response.raw_output,
            document=DocumentContext(
                document_id=document.id,
                published_at=document.published_at,
            ),
            config=self._validation_config,
            schema=schema,
        )
        events: tuple[Event, ...] = ()
        if validation.verdict is CandidateStatus.ACCEPTED:
            if validation.parsed_output is None:
                raise RuntimeError(
                    "accepted extraction is missing parsed_output; "
                    "the validator must not accept unparseable output"
                )
            events = events_from_accepted_output(
                validation.parsed_output, document_id=document.id
            )

        llm_run = assemble_llm_run(
            document_id=document.id,
            rendered_prompt=rendered_prompt,
            response=response,
            validation=validation,
            versions=versions,
            model_spec=model_spec,
            created_at=self._clock.now(),
            temperature=EXTRACTION_TEMPERATURE,
            max_tokens=EXTRACTION_MAX_TOKENS,
        )
        stored_run = uow.llm_runs.add(llm_run)
        stored_events = tuple(uow.events.add(event) for event in events)
        return ExtractionOutcome(
            verdict=validation.verdict,
            llm_run=stored_run,
            events=stored_events,
        )
