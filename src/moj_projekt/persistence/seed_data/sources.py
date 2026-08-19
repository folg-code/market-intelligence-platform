"""Declarative MVP Source registry data (S001-T010, DOMAIN_MODEL.md section 3).

Plain data, no branching: :mod:`moj_projekt.persistence.seed_sources` iterates
``SEED_SOURCES`` and persists each entry the same way, so adding a source is a
matter of appending a tuple entry here, never adding an ``if``/``elif``.

``publisher`` doubles as the independence-grouping key (``Source`` docstring,
DOMAIN_MODEL.md section 3 invariant: "sources sharing an originating
publisher are not independent of each other"). Every entry below has a
distinct publisher, so all six seeded sources are independent of one
another - in particular, the Tier 2 outlets are deliberately drawn from three
different parent organizations rather than, say, two outlets owned by the
same media group.

Tier 1 (``SourceTier.PRIMARY``): the three official/primary MVP sources named
in `docs/planning/sprints/SPRINT_001.md` section 5.1 (S001-T010) - Fed/FOMC,
BLS, SEC EDGAR. Tier 2 (``SourceTier.PROFESSIONAL``): three established,
independently-owned newswires. RSS ``feed_url`` values are data for the
ingest adapter (S001-T012), not hardcoded in adapter code. Bloomberg Markets
uses a live public RSS URL; Reuters and AP entries keep structurally-real
placeholders until those outlets expose a public feed again.

"""

from __future__ import annotations

from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source

__all__ = ["SEED_SOURCES"]

SEED_SOURCES: tuple[Source, ...] = (
    Source(
        key="fed_fomc",
        name="Federal Reserve / FOMC",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="Federal Reserve",
        endpoint_config={"base_url": "https://www.federalreserve.gov"},
    ),
    Source(
        key="bls",
        name="U.S. Bureau of Labor Statistics",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="U.S. Bureau of Labor Statistics",
        endpoint_config={"base_url": "https://www.bls.gov"},
    ),
    Source(
        key="sec_edgar",
        name="SEC EDGAR",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="U.S. Securities and Exchange Commission",
        endpoint_config={"base_url": "https://www.sec.gov/cgi-bin/browse-edgar"},
    ),
    Source(
        key="reuters_markets",
        name="Reuters Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Reuters",
        endpoint_config={"feed_url": "https://www.reutersagency.com/feed/?best-topics=markets"},
    ),
    Source(
        key="ap_news",
        name="Associated Press News",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Associated Press",
        endpoint_config={"feed_url": "https://apnews.com/rss"},
    ),
    Source(
        key="bloomberg_markets",
        name="Bloomberg Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Bloomberg L.P.",
        endpoint_config={"feed_url": "https://feeds.bloomberg.com/markets/news.rss"},
    ),
)
