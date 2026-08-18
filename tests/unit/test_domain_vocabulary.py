"""Enforces DOMAIN_MODEL.md section 7: the terms ``sentiment_score``,
"prediction", "signal", and "forecast" are deliberately absent from the
ubiquitous language and must not appear in code or docs.
"""

from __future__ import annotations

import re
from pathlib import Path

import moj_projekt.domain as domain_package

FORBIDDEN_TERMS = ("sentiment_score", "prediction", "signal", "forecast")
_WORD_PATTERN = re.compile(
    "(" + "|".join(re.escape(term) for term in FORBIDDEN_TERMS) + ")",
    re.IGNORECASE,
)


def test_domain_source_uses_none_of_the_forbidden_vocabulary() -> None:
    domain_dir = Path(domain_package.__file__).parent
    violations: dict[str, list[str]] = {}

    for path in sorted(domain_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        found = sorted(set(_WORD_PATTERN.findall(text)))
        if found:
            violations[str(path)] = found

    assert not violations, (
        "Forbidden vocabulary (DOMAIN_MODEL.md section 7) found in domain/: "
        f"{violations}"
    )
