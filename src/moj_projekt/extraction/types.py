"""Value objects for extraction parsing and validation (ADR-0002)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from moj_projekt.domain.enums import CandidateStatus

__all__ = [
    "DEFAULT_VALIDATION_CONFIG",
    "MERGE_FIELD_NAMES",
    "DocumentContext",
    "ExtractionValidationResult",
    "ParseResult",
    "ValidationConfig",
    "ValidationError",
    "ValidationErrorCode",
]

# Field names that would collapse extracted_facts and source_claims into one
# list (ADR-0008). Schema v1 forbids them; the validator still names this
# failure as a merge, not a generic schema miss.
MERGE_FIELD_NAMES = frozenset(
    {
        "facts_and_claims",
        "merged_facts_and_claims",
        "combined_facts_and_claims",
    }
)


class ValidationErrorCode(StrEnum):
    """Stable code stored verbatim on ``LLMRun.validation_errors``."""

    UNPARSEABLE = "unparseable"
    SCHEMA_V1_VIOLATION = "schema_v1_violation"
    MISSING_DOCUMENT_REFERENCE = "missing_document_reference"
    OCCURRED_AT_IMPLAUSIBLE = "occurred_at_implausible"
    MERGED_FACTS_AND_CLAIMS = "merged_facts_and_claims"
    FORBIDDEN_VOCABULARY = "forbidden_vocabulary"
    MARKET_PRICING_LANGUAGE = "market_pricing_language"
    EVENT_INVARIANT = "event_invariant"
    BELOW_AUTO_ACCEPT_THRESHOLD = "below_auto_accept_threshold"


@dataclass(frozen=True, slots=True)
class ValidationError:
    """One structured judgement the validator can store on an ``LLMRun``."""

    code: ValidationErrorCode
    message: str
    json_path: str = "$"

    def to_llm_run_record(self) -> str:
        """Serialize to a JSON object string for ``LLMRun.validation_errors``."""
        return json.dumps(
            {
                "code": str(self.code),
                "json_path": self.json_path,
                "message": self.message,
            },
            ensure_ascii=True,
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Thresholds for extraction rules. Rule bodies must not hard-code these."""

    auto_accept_min_confidence: float
    occurred_at_max_before: timedelta
    occurred_at_max_after: timedelta

    def __post_init__(self) -> None:
        if not (0.0 <= self.auto_accept_min_confidence <= 1.0):
            raise ValueError(
                "ValidationConfig.auto_accept_min_confidence must be between 0.0 and 1.0"
            )
        if self.occurred_at_max_before < timedelta(0):
            raise ValueError("ValidationConfig.occurred_at_max_before must not be negative")
        if self.occurred_at_max_after < timedelta(0):
            raise ValueError("ValidationConfig.occurred_at_max_after must not be negative")


DEFAULT_VALIDATION_CONFIG = ValidationConfig(
    auto_accept_min_confidence=0.7,
    occurred_at_max_before=timedelta(days=365),
    occurred_at_max_after=timedelta(days=2),
)


@dataclass(frozen=True, slots=True)
class DocumentContext:
    """The source Document the candidate events must be attributable to.

    ``document_id`` is ``None`` when the Document has not been persisted;
    constructing an ``Event`` would then violate ``source_ids`` never empty.
    """

    document_id: UUID | None
    published_at: datetime

    def __post_init__(self) -> None:
        if self.published_at.tzinfo is None:
            raise ValueError("DocumentContext.published_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Raw text turned into a JSON object, or a parse failure.

    ``parsed`` is the decoded object as produced by ``json.loads`` - never a
    repaired or default-filled copy.
    """

    parsed: Mapping[str, Any] | None
    error: ValidationError | None


@dataclass(frozen=True, slots=True)
class ExtractionValidationResult:
    """Verdict plus structured errors. Never carries a domain ``Event``.

    ``parsed_output`` is the unmodified ``json.loads`` result when parsing
    succeeded, else ``None``. ``raw_output`` is the input string unchanged.
    """

    verdict: CandidateStatus
    errors: tuple[ValidationError, ...]
    parsed_output: Mapping[str, Any] | None
    raw_output: str

    def llm_run_records(self) -> tuple[str, ...]:
        """``LLMRun.validation_errors`` payload, one JSON object string per error."""
        return tuple(error.to_llm_run_record() for error in self.errors)

    @property
    def error_codes(self) -> Sequence[ValidationErrorCode]:
        return tuple(error.code for error in self.errors)
