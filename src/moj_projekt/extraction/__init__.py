"""Parse, judge, and persist event-extraction results (ADR-0002).

Parser and validator import no SQLAlchemy, httpx, or Anthropic SDK.
The extraction service calls an injected ``LLMClient`` and writes through
a caller-owned ``UnitOfWork``.
"""

from __future__ import annotations

from moj_projekt.extraction.parser import parse_extraction_output
from moj_projekt.extraction.service import (
    EXTRACTION_MAX_TOKENS,
    EXTRACTION_PROVIDER,
    EXTRACTION_TEMPERATURE,
    ExtractionOutcome,
    ExtractionService,
    assemble_llm_run,
    document_text_for_extraction,
    events_from_accepted_output,
    hash_extraction_input,
    token_usage_mapping,
)
from moj_projekt.extraction.types import (
    DEFAULT_VALIDATION_CONFIG,
    MERGE_FIELD_NAMES,
    DocumentContext,
    ExtractionValidationResult,
    ParseResult,
    ValidationConfig,
    ValidationError,
    ValidationErrorCode,
)
from moj_projekt.extraction.validator import validate_extraction

__all__ = [
    "DEFAULT_VALIDATION_CONFIG",
    "EXTRACTION_MAX_TOKENS",
    "EXTRACTION_PROVIDER",
    "EXTRACTION_TEMPERATURE",
    "MERGE_FIELD_NAMES",
    "DocumentContext",
    "ExtractionOutcome",
    "ExtractionService",
    "ExtractionValidationResult",
    "ParseResult",
    "ValidationConfig",
    "ValidationError",
    "ValidationErrorCode",
    "assemble_llm_run",
    "document_text_for_extraction",
    "events_from_accepted_output",
    "hash_extraction_input",
    "parse_extraction_output",
    "token_usage_mapping",
    "validate_extraction",
]
