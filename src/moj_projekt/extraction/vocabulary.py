"""Forbidden ubiquitous-language terms in generated extraction text.

DOMAIN_MODEL.md section 7 deliberately excludes ``sentiment_score``,
"prediction", "signal", and "forecast". Enforcement is post-generation
(D-S002-04 clause 12), not in the prompt.
"""

from __future__ import annotations

import re

__all__ = ["FORBIDDEN_TERMS", "find_forbidden_vocabulary"]

FORBIDDEN_TERMS: tuple[str, ...] = (
    "sentiment_score",
    "prediction",
    "signal",
    "forecast",
)

_FORBIDDEN_TOKEN_SEQUENCES: tuple[tuple[str, ...], ...] = tuple(
    tuple(term.lower().split("_")) for term in FORBIDDEN_TERMS
)

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL_WORD_PATTERN = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")


def find_forbidden_vocabulary(text: str) -> list[str]:
    """Return forbidden terms found as whole tokens in ``text``.

    Matches the domain source-code checker: ``signal`` in ``signal_strength``
    is flagged; ``signal`` as a substring of ``contradiction_signals`` is not.
    """
    found: set[str] = set()
    for match in _IDENTIFIER_PATTERN.finditer(text):
        tokens = _tokenize(match.group(0))
        term = _matched_forbidden_term(tokens)
        if term is not None:
            found.add(term)
    return sorted(found)


def _tokenize(identifier: str) -> list[str]:
    tokens: list[str] = []
    for part in identifier.split("_"):
        if not part:
            continue
        camel_words = _CAMEL_WORD_PATTERN.findall(part)
        tokens.extend(camel_words if camel_words else [part])
    return [token.lower() for token in tokens]


def _matched_forbidden_term(tokens: list[str]) -> str | None:
    for sequence in _FORBIDDEN_TOKEN_SEQUENCES:
        window = len(sequence)
        for start in range(len(tokens) - window + 1):
            if tuple(tokens[start : start + window]) == sequence:
                return "_".join(sequence)
    return None
