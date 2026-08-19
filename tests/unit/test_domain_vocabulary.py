"""Enforces DOMAIN_MODEL.md section 7: the terms ``sentiment_score``,
"prediction", "signal", and "forecast" are deliberately absent from the
ubiquitous language and must not appear in code or docs.
"""

from __future__ import annotations

import re
from pathlib import Path

import moj_projekt.domain as domain_package

FORBIDDEN_TERMS = ("sentiment_score", "prediction", "signal", "forecast")

# Forbidden terms may be multi-word (``sentiment_score``). Each term is
# represented as a sequence of lowercase tokens, e.g. ("sentiment", "score").
_FORBIDDEN_TOKEN_SEQUENCES: tuple[tuple[str, ...], ...] = tuple(
    tuple(term.lower().split("_")) for term in FORBIDDEN_TERMS
)

# Matches any Python identifier (snake_case or camelCase), including the
# underscores that separate its words.
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Splits a single underscore-delimited part of an identifier into its
# camelCase words, if any (e.g. "sentimentScore" -> ["sentiment", "Score"]).
_CAMEL_WORD_PATTERN = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")


def _tokenize(identifier: str) -> list[str]:
    """Split an identifier into lowercase whole-word tokens.

    Splits on ``_`` (snake_case) and on camelCase word boundaries, so that
    a forbidden term is only recognised when it occupies one or more whole
    tokens - never when it is merely a substring of a larger token.

    Examples:
        "signal_strength"        -> ["signal", "strength"]
        "raw_sentiment_score"    -> ["raw", "sentiment", "score"]
        "contradiction_signals"  -> ["contradiction", "signals"]  (no match)
        "signaled_at"            -> ["signaled", "at"]            (no match)
        "postsignal"             -> ["postsignal"]                (no match)
    """
    tokens: list[str] = []
    for part in identifier.split("_"):
        if not part:
            continue
        camel_words = _CAMEL_WORD_PATTERN.findall(part)
        tokens.extend(camel_words if camel_words else [part])
    return [token.lower() for token in tokens]


def _matched_forbidden_term(tokens: list[str]) -> str | None:
    """Return the forbidden term matched by a contiguous run of tokens, if any."""
    for sequence in _FORBIDDEN_TOKEN_SEQUENCES:
        window = len(sequence)
        for start in range(len(tokens) - window + 1):
            if tuple(tokens[start : start + window]) == sequence:
                return "_".join(sequence)
    return None


def find_forbidden_vocabulary(text: str) -> list[str]:
    """Return the forbidden terms found in ``text``, as whole tokens.

    A forbidden term is flagged when it appears as its own word (e.g. the
    bare identifier/word "signal") or as one or more whole tokens within a
    compound snake_case/camelCase identifier (e.g. "signal_strength",
    "raw_sentiment_score", "trading_signal", "weather_forecast_model"). It is
    NOT flagged when it is merely a substring of a larger token that isn't
    itself split into the forbidden word (e.g. "contradiction_signals",
    "signaled_at", "postsignal").
    """
    found: set[str] = set()
    for match in _IDENTIFIER_PATTERN.finditer(text):
        tokens = _tokenize(match.group(0))
        term = _matched_forbidden_term(tokens)
        if term is not None:
            found.add(term)
    return sorted(found)


def test_domain_source_uses_none_of_the_forbidden_vocabulary() -> None:
    domain_dir = Path(domain_package.__file__).parent
    violations: dict[str, list[str]] = {}

    for path in sorted(domain_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        found = find_forbidden_vocabulary(text)
        if found:
            violations[str(path)] = found

    assert not violations, (
        "Forbidden vocabulary (DOMAIN_MODEL.md section 7) found in domain/: "
        f"{violations}"
    )


def test_bare_forbidden_terms_are_flagged() -> None:
    for term in ("signal", "prediction", "forecast", "sentiment_score"):
        assert find_forbidden_vocabulary(f"x = {term}") == [term]


def test_forbidden_terms_are_flagged_inside_compound_snake_case_identifiers() -> None:
    assert find_forbidden_vocabulary("signal_strength = 1") == ["signal"]
    assert find_forbidden_vocabulary("raw_sentiment_score = 1") == ["sentiment_score"]
    assert find_forbidden_vocabulary("trading_signal = 1") == ["signal"]
    assert find_forbidden_vocabulary("weather_forecast_model = 1") == ["forecast"]


def test_legitimate_compound_identifiers_are_not_flagged() -> None:
    # DOMAIN_MODEL.md section 3: Narrative.contradiction_signals is required
    # vocabulary, not the forbidden term "signal".
    assert find_forbidden_vocabulary("contradiction_signals: list[str]") == []
    # "signal" only as a substring of a larger token, not a whole token.
    assert find_forbidden_vocabulary("signaled_at: datetime") == []
    assert find_forbidden_vocabulary("postsignal_flag = True") == []
    # Adjacent, non-forbidden domain vocabulary must never be mistakenly
    # caught by the token matcher.
    assert find_forbidden_vocabulary("momentum: float") == []
    assert find_forbidden_vocabulary("velocity: float") == []
