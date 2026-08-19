"""Parse raw model output into a JSON object, or a parse failure.

Does not validate against schema v1 and does not repair malformed text.
"""

from __future__ import annotations

import json
from typing import Any, cast

from moj_projekt.extraction.types import ParseResult, ValidationError, ValidationErrorCode

__all__ = ["parse_extraction_output"]


def parse_extraction_output(raw_output: str) -> ParseResult:
    """Decode ``raw_output`` as a JSON object.

    Anything that is not well-formed JSON, or JSON that is not an object
    (array, string, number, ``null``), is a parse failure. Schema checking
    happens later and is a different hard rule.
    """
    try:
        loaded: object = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return ParseResult(
            parsed=None,
            error=ValidationError(
                code=ValidationErrorCode.UNPARSEABLE,
                message=(
                    f"Raw model output is not valid JSON: {exc.msg} "
                    f"at line {exc.lineno} column {exc.colno}"
                ),
                json_path="$",
            ),
        )
    if not isinstance(loaded, dict):
        return ParseResult(
            parsed=None,
            error=ValidationError(
                code=ValidationErrorCode.UNPARSEABLE,
                message=(
                    "Raw model output must be a JSON object "
                    f"(got {type(loaded).__name__})"
                ),
                json_path="$",
            ),
        )
    return ParseResult(parsed=cast(dict[str, Any], loaded), error=None)
