"""Market-pricing language is forbidden while there is no market data feed.

Phrases are from ARCHITECTURE_FOUNDATIONS.md section 6 and are checked
deterministically after generation, not by the prompt (D-S002-04 clause 12).
"""

from __future__ import annotations

__all__ = [
    "ALLOWED_MARKET_PHRASES",
    "FORBIDDEN_MARKET_PHRASES",
    "find_market_pricing_language",
]

# Trailing ellipses from the foundations document are not part of the match.
FORBIDDEN_MARKET_PHRASES: tuple[str, ...] = (
    "markets are pricing in",
    "market pricing suggests",
    "options pricing reflects",
)

ALLOWED_MARKET_PHRASES: tuple[str, ...] = (
    "Financial commentary increasingly expects",
    "Monitored sources increasingly frame this as",
    "Discussion is shifting toward",
    "The dominant interpretation among monitored sources is",
)


def find_market_pricing_language(text: str) -> list[str]:
    """Return the forbidden phrases that appear in ``text`` (case-insensitive)."""
    lowered = text.lower()
    found: list[str] = []
    for phrase in FORBIDDEN_MARKET_PHRASES:
        if phrase in lowered:
            found.append(phrase)
    return found
