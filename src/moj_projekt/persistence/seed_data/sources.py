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
ingest adapter (S001-T012), not hardcoded in adapter code.

Active flag (S002-T005, PRB-002, D-S002-04 clause 14): a source is seeded
``active=True`` only when it has both a working adapter and a live feed, so a
clean cycle over this registry records no expected per-source failures.

- ``fed_fomc``: ``active=False`` - ``source_type=official_api``, no adapter yet.
- ``bls``: ``active=False`` - ``source_type=official_api``, no adapter yet.
- ``sec_edgar``: ``active=False`` - ``source_type=official_api``, no adapter yet.
- ``reuters_markets``: ``active=False`` - seeded URL returned HTTP 404 (HTML,
  not RSS) on 2026-08-19; ``feeds.reuters.com`` does not resolve; no
  replacement public RSS was found.
- ``ap_news``: ``active=False`` - ``https://apnews.com/rss`` returned HTTP 404
  (HTML, not RSS) on 2026-08-19; no replacement public RSS was found.
- ``bloomberg_markets``: ``active=True`` -
  ``https://feeds.bloomberg.com/markets/news.rss`` returned a live RSS
  document on 2026-08-19.

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
        active=False,
    ),
    Source(
        key="bls",
        name="U.S. Bureau of Labor Statistics",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="U.S. Bureau of Labor Statistics",
        endpoint_config={"base_url": "https://www.bls.gov"},
        active=False,
    ),
    Source(
        key="sec_edgar",
        name="SEC EDGAR",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="U.S. Securities and Exchange Commission",
        endpoint_config={"base_url": "https://www.sec.gov/cgi-bin/browse-edgar"},
        active=False,
    ),
    Source(
        key="reuters_markets",
        name="Reuters Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Reuters",
        endpoint_config={"feed_url": "https://www.reutersagency.com/feed/?best-topics=markets"},
        active=False,
    ),
    Source(
        key="ap_news",
        name="Associated Press News",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Associated Press",
        endpoint_config={"feed_url": "https://apnews.com/rss"},
        active=False,
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
