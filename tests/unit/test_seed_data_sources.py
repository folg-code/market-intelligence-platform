"""Unit tests for the declarative Source seed data (S001-T010) - no database.

Covers the structural guarantees the integration test cannot cheaply assert
in isolation from a live database: no duplicate keys, every entry
well-formed, and Tier 1/Tier 2 publishers are pairwise distinct (so the
independence-grouping key in DOMAIN_MODEL.md section 3 is meaningful for
this seed data, not accidentally defeated by two entries sharing a
publisher).
"""

from __future__ import annotations

from moj_projekt.domain.enums import SourceTier
from moj_projekt.persistence.seed_data.sources import SEED_SOURCES


def test_seed_sources_is_non_empty() -> None:
    assert len(SEED_SOURCES) > 0


def test_seed_sources_have_no_duplicate_keys() -> None:
    keys = [source.key for source in SEED_SOURCES]
    assert len(keys) == len(set(keys))


def test_every_seed_source_has_non_empty_required_fields() -> None:
    for source in SEED_SOURCES:
        assert source.key.strip() != ""
        assert source.name.strip() != ""
        assert source.source_type.strip() != ""
        assert source.publisher.strip() != ""


def test_seed_sources_include_expected_tier_1_keys() -> None:
    tier_1_keys = {
        source.key for source in SEED_SOURCES if source.tier is SourceTier.PRIMARY
    }
    assert tier_1_keys == {"fed_fomc", "bls", "sec_edgar"}


def test_seed_sources_include_at_least_two_tier_2_sources() -> None:
    tier_2 = [source for source in SEED_SOURCES if source.tier is SourceTier.PROFESSIONAL]
    assert len(tier_2) >= 2


def test_every_seed_source_has_exactly_one_tier() -> None:
    for source in SEED_SOURCES:
        assert isinstance(source.tier, SourceTier)


def test_seed_sources_have_pairwise_distinct_publishers() -> None:
    publishers = [source.publisher for source in SEED_SOURCES]
    assert len(publishers) == len(set(publishers))


def test_seed_sources_are_active_by_default() -> None:
    for source in SEED_SOURCES:
        assert source.active is True


def test_bloomberg_seed_uses_the_public_markets_rss_url() -> None:
    bloomberg = next(source for source in SEED_SOURCES if source.key == "bloomberg_markets")
    assert bloomberg.source_type == "rss"
    assert bloomberg.endpoint_config["feed_url"] == (
        "https://feeds.bloomberg.com/markets/news.rss"
    )
