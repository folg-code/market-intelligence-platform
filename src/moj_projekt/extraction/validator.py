"""Deterministic validation layer for event-extraction model output (ADR-0002).

Raw text becomes exactly one of ``accepted`` / ``proposed`` / ``rejected``.
This module never calls a model, never talks to HTTP, never touches a
database, never mutates the input, and never constructs a domain ``Event``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Any, cast

from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.extraction.market_language import find_market_pricing_language
from moj_projekt.extraction.parser import parse_extraction_output
from moj_projekt.extraction.schema import schema_v1_errors
from moj_projekt.extraction.types import (
    DocumentContext,
    ExtractionValidationResult,
    ValidationConfig,
    ValidationError,
    ValidationErrorCode,
)
from moj_projekt.extraction.vocabulary import find_forbidden_vocabulary
from moj_projekt.llm.artifacts import load_output_schema

__all__ = ["validate_extraction"]


def validate_extraction(
    raw_output: str,
    *,
    document: DocumentContext,
    config: ValidationConfig,
    schema: Mapping[str, Any] | None = None,
) -> ExtractionValidationResult:
    """Judge ``raw_output`` against schema v1 and the hard/soft extraction rules.

    ``schema`` defaults to the versioned T006 artifact. Callers that already
    loaded it (the extraction service) may pass it in. Thresholds come from
    ``config``, never from literals in the rule bodies.
    """
    parsed = parse_extraction_output(raw_output)
    if parsed.error is not None:
        return ExtractionValidationResult(
            verdict=CandidateStatus.REJECTED,
            errors=(parsed.error,),
            parsed_output=None,
            raw_output=raw_output,
        )

    assert parsed.parsed is not None
    payload = parsed.parsed
    loaded_schema = schema if schema is not None else load_output_schema()
    structural_errors = tuple(schema_v1_errors(payload, loaded_schema))
    if structural_errors:
        return ExtractionValidationResult(
            verdict=CandidateStatus.REJECTED,
            errors=structural_errors,
            parsed_output=payload,
            raw_output=raw_output,
        )

    events = cast(list[Any], payload["events"])
    hard_errors: list[ValidationError] = []
    for index, event in enumerate(events):
        event_map = cast(Mapping[str, Any], event)
        event_path = f"$.events[{index}]"
        hard_errors.extend(
            _hard_errors_for_event(event_map, event_path, document, config)
        )

    if hard_errors:
        return ExtractionValidationResult(
            verdict=CandidateStatus.REJECTED,
            errors=tuple(hard_errors),
            parsed_output=payload,
            raw_output=raw_output,
        )

    soft_errors: list[ValidationError] = []
    for index, event in enumerate(events):
        event_map = cast(Mapping[str, Any], event)
        confidence = cast(float, event_map["confidence"])
        if confidence < config.auto_accept_min_confidence:
            soft_errors.append(
                ValidationError(
                    code=ValidationErrorCode.BELOW_AUTO_ACCEPT_THRESHOLD,
                    message=(
                        f"confidence {confidence} at $.events[{index}].confidence "
                        "is below the auto-accept threshold "
                        f"{config.auto_accept_min_confidence}"
                    ),
                    json_path=f"$.events[{index}].confidence",
                )
            )

    if soft_errors:
        return ExtractionValidationResult(
            verdict=CandidateStatus.PROPOSED,
            errors=tuple(soft_errors),
            parsed_output=payload,
            raw_output=raw_output,
        )

    return ExtractionValidationResult(
        verdict=CandidateStatus.ACCEPTED,
        errors=(),
        parsed_output=payload,
        raw_output=raw_output,
    )


def _hard_errors_for_event(
    event: Mapping[str, Any],
    event_path: str,
    document: DocumentContext,
    config: ValidationConfig,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    errors.extend(_document_reference_errors(event, event_path))
    errors.extend(_occurred_at_errors(event, event_path, document, config))
    errors.extend(_merged_facts_claims_errors(event, event_path))
    errors.extend(_forbidden_vocabulary_errors(event, event_path))
    errors.extend(_market_language_errors(event, event_path))
    errors.extend(_event_invariant_errors(event, event_path, document))
    return errors


def _document_reference_errors(
    event: Mapping[str, Any],
    event_path: str,
) -> list[ValidationError]:
    facts = event.get("extracted_facts")
    claims = event.get("source_claims")
    if not isinstance(facts, list) or not isinstance(claims, list):
        return []
    if facts or claims:
        return []
    return [
        ValidationError(
            code=ValidationErrorCode.MISSING_DOCUMENT_REFERENCE,
            message=(
                f"Event at {event_path} has no supporting document reference: "
                "extracted_facts and source_claims are both empty"
            ),
            json_path=event_path,
        )
    ]


def _occurred_at_errors(
    event: Mapping[str, Any],
    event_path: str,
    document: DocumentContext,
    config: ValidationConfig,
) -> list[ValidationError]:
    raw = event["occurred_at"]
    occurred_at = datetime.fromisoformat(cast(str, raw)).astimezone(UTC)
    published_at = document.published_at.astimezone(UTC)
    earliest = published_at - config.occurred_at_max_before
    latest = published_at + config.occurred_at_max_after
    if earliest <= occurred_at <= latest:
        return []
    path = f"{event_path}.occurred_at"
    return [
        ValidationError(
            code=ValidationErrorCode.OCCURRED_AT_IMPLAUSIBLE,
            message=(
                f"occurred_at {raw} at {path} is outside the plausibility "
                f"window [{earliest.isoformat()}, {latest.isoformat()}] "
                f"relative to document published_at {published_at.isoformat()}"
            ),
            json_path=path,
        )
    ]


def _merged_facts_claims_errors(
    event: Mapping[str, Any],
    event_path: str,
) -> list[ValidationError]:
    facts = event.get("extracted_facts")
    claims = event.get("source_claims")
    if not isinstance(facts, list) or not isinstance(claims, list):
        return []
    fact_texts = {
        item["text"]
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    }
    errors: list[ValidationError] = []
    for item in claims:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text in fact_texts:
            errors.append(
                ValidationError(
                    code=ValidationErrorCode.MERGED_FACTS_AND_CLAIMS,
                    message=(
                        f"extracted_facts and source_claims share text {text!r} "
                        f"at {event_path}, which merges facts and claims "
                        "(ADR-0008)"
                    ),
                    json_path=event_path,
                )
            )
    return errors


def _forbidden_vocabulary_errors(
    event: Mapping[str, Any],
    event_path: str,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for path, text in _string_fields(event, event_path):
        found = find_forbidden_vocabulary(text)
        if not found:
            continue
        quoted = ", ".join(repr(term) for term in found)
        errors.append(
            ValidationError(
                code=ValidationErrorCode.FORBIDDEN_VOCABULARY,
                message=(
                    f"Forbidden vocabulary {quoted} in generated text at {path} "
                    "(DOMAIN_MODEL.md section 7)"
                ),
                json_path=path,
            )
        )
    return errors


def _market_language_errors(
    event: Mapping[str, Any],
    event_path: str,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for path, text in _string_fields(event, event_path):
        found = find_market_pricing_language(text)
        if not found:
            continue
        quoted = ", ".join(repr(phrase) for phrase in found)
        errors.append(
            ValidationError(
                code=ValidationErrorCode.MARKET_PRICING_LANGUAGE,
                message=(
                    f"Market-pricing language {quoted} at {path} "
                    "(ARCHITECTURE_FOUNDATIONS.md section 6)"
                ),
                json_path=path,
            )
        )
    return errors


def _event_invariant_errors(
    event: Mapping[str, Any],
    event_path: str,
    document: DocumentContext,
) -> list[ValidationError]:
    """Mirror Event.__post_init__ without constructing an Event."""
    errors: list[ValidationError] = []
    for field_name in ("type", "title"):
        value = event[field_name]
        if isinstance(value, str) and not value.strip():
            errors.append(
                ValidationError(
                    code=ValidationErrorCode.EVENT_INVARIANT,
                    message=(
                        f"Event invariant: {field_name} is empty or whitespace "
                        f"at {event_path}.{field_name}"
                    ),
                    json_path=f"{event_path}.{field_name}",
                )
            )
    if document.document_id is None:
        errors.append(
            ValidationError(
                code=ValidationErrorCode.EVENT_INVARIANT,
                message=(
                    f"Event invariant: source_ids would be empty at {event_path} "
                    "(no source document id)"
                ),
                json_path=event_path,
            )
        )
    confidence = event["confidence"]
    if (
        isinstance(confidence, int | float)
        and not isinstance(confidence, bool)
        and not (0.0 <= float(confidence) <= 1.0)
    ):
        errors.append(
            ValidationError(
                code=ValidationErrorCode.EVENT_INVARIANT,
                message=(
                    f"Event invariant: confidence {confidence} is outside "
                    f"0.0..1.0 at {event_path}.confidence"
                ),
                json_path=f"{event_path}.confidence",
            )
        )
    return errors


def _string_fields(value: object, json_path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield json_path, value
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _string_fields(child, f"{json_path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _string_fields(child, f"{json_path}[{index}]")
