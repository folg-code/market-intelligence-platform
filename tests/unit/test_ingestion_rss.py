"""Fixture-based unit tests for RSS parsing (S001-T012) - no network."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source
from moj_projekt.ingestion.adapter import SourceFetchError
from moj_projekt.ingestion.rss import parse_rss_documents

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "rss"
_COLLECTED = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _source() -> Source:
    return Source(
        key="bloomberg_markets",
        name="Bloomberg Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Bloomberg L.P.",
        endpoint_config={"feed_url": "https://feeds.bloomberg.com/markets/news.rss"},
    )


def test_parse_rss_documents_reads_title_url_published_and_body() -> None:
    payload = (_FIXTURES / "sample_feed.xml").read_bytes()

    documents = parse_rss_documents(payload, source=_source(), collected_at=_COLLECTED)

    assert len(documents) == 2
    first = documents[0]
    assert first.source_key == "bloomberg_markets"
    assert first.source_type == "rss"
    assert first.url == "https://example.com/markets/article-rate-hold"
    assert first.title == "Central bank holds policy rate"
    assert "policy rate unchanged" in first.content
    assert first.source_native_id == "fixture-guid-rate-hold"
    assert first.published_at == datetime(2026, 8, 17, 14, 0, tzinfo=UTC)
    assert first.collected_at == _COLLECTED
    assert first.has_collection_timestamp_anomaly is False


def test_parse_rss_documents_skips_entries_missing_a_link() -> None:
    payload = (_FIXTURES / "sample_feed.xml").read_bytes()

    documents = parse_rss_documents(payload, source=_source(), collected_at=_COLLECTED)

    assert [document.source_native_id for document in documents] == [
        "fixture-guid-rate-hold",
        "fixture-guid-oil",
    ]


def test_parse_rss_documents_accepts_a_well_formed_empty_feed() -> None:
    payload = (_FIXTURES / "empty_feed.xml").read_bytes()

    documents = parse_rss_documents(payload, source=_source(), collected_at=_COLLECTED)

    assert documents == []


def test_parse_rss_documents_rejects_html_as_malformed() -> None:
    payload = (_FIXTURES / "malformed_feed.html").read_bytes()

    with pytest.raises(SourceFetchError, match="malformed feed"):
        parse_rss_documents(payload, source=_source(), collected_at=_COLLECTED)


def test_parse_rss_documents_rejects_an_empty_payload() -> None:
    with pytest.raises(SourceFetchError, match="empty payload"):
        parse_rss_documents(b"", source=_source(), collected_at=_COLLECTED)
