"""Unit tests for RSS HTTP fetch (S001-T012) - httpx mocked, no network."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source
from moj_projekt.ingestion.adapter import SourceFetchError
from moj_projekt.ingestion.rss import RssFeedAdapter

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "rss"
_COLLECTED = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
_FEED_URL = "https://feeds.bloomberg.com/markets/news.rss"


class _FixedClock:
    def now(self) -> datetime:
        return _COLLECTED


def _source() -> Source:
    return Source(
        key="bloomberg_markets",
        name="Bloomberg Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Bloomberg L.P.",
        endpoint_config={"feed_url": _FEED_URL},
    )


def _adapter_for(handler: httpx.MockTransport) -> RssFeedAdapter:
    client = httpx.Client(transport=handler, timeout=15.0)
    return RssFeedAdapter(clock=_FixedClock(), client=client)


def test_fetch_documents_uses_injected_clock_for_collected_at() -> None:
    payload = (_FIXTURES / "sample_feed.xml").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == _FEED_URL
        return httpx.Response(200, content=payload)

    adapter = _adapter_for(httpx.MockTransport(handler))
    try:
        documents = adapter.fetch_documents(_source())
    finally:
        adapter.close()

    assert len(documents) == 2
    assert all(document.collected_at == _COLLECTED for document in documents)


def test_fetch_documents_timeout_raises_source_fetch_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    adapter = _adapter_for(httpx.MockTransport(handler))
    try:
        with pytest.raises(SourceFetchError, match="timeout"):
            adapter.fetch_documents(_source())
    finally:
        adapter.close()


def test_fetch_documents_http_error_raises_source_fetch_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    adapter = _adapter_for(httpx.MockTransport(handler))
    try:
        with pytest.raises(SourceFetchError, match="HTTP 503"):
            adapter.fetch_documents(_source())
    finally:
        adapter.close()


def test_fetch_documents_malformed_payload_raises_source_fetch_error() -> None:
    payload = (_FIXTURES / "malformed_feed.html").read_bytes()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    adapter = _adapter_for(httpx.MockTransport(handler))
    try:
        with pytest.raises(SourceFetchError, match="malformed feed"):
            adapter.fetch_documents(_source())
    finally:
        adapter.close()


def test_fetch_documents_requires_feed_url_in_endpoint_config() -> None:
    source = _source()
    source_without_url = Source(
        key=source.key,
        name=source.name,
        source_type=source.source_type,
        tier=source.tier,
        publisher=source.publisher,
        endpoint_config={},
    )
    adapter = RssFeedAdapter(clock=_FixedClock(), client=httpx.Client())
    try:
        with pytest.raises(SourceFetchError, match="feed_url"):
            adapter.fetch_documents(source_without_url)
    finally:
        adapter.close()
