"""Tier 2 RSS/news adapter (S001-T012).

Feed URL comes from ``Source.endpoint_config["feed_url"]`` - data-driven,
not hardcoded here. Network I/O is confined to :class:`RssFeedAdapter`;
:func:`parse_rss_documents` is a pure parse of an already-fetched payload
so unit tests never touch the network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
import httpx

from moj_projekt.domain.clock import Clock
from moj_projekt.domain.document import Document
from moj_projekt.domain.source import Source
from moj_projekt.ingestion.adapter import SourceFetchError

__all__ = [
    "FEED_URL_KEY",
    "RSS_SOURCE_TYPE",
    "RssFeedAdapter",
    "parse_rss_documents",
]

RSS_SOURCE_TYPE = "rss"
FEED_URL_KEY = "feed_url"

_DEFAULT_TIMEOUT_SECONDS = 15.0
_USER_AGENT = "moj-projekt/0.1 (+rss-ingest)"


def parse_rss_documents(
    payload: bytes | str,
    *,
    source: Source,
    collected_at: datetime,
) -> list[Document]:
    """Normalize an RSS/Atom payload into Documents.

    Raises :class:`SourceFetchError` when the payload is not a usable feed
    (empty body, HTML error page, unparseable XML). A well-formed feed with
    zero entries is success and returns an empty list. Individual entries
    missing a URL, title, or published timestamp are skipped rather than
    failing the source.
    """
    if not payload.strip():
        raise SourceFetchError(f"malformed feed for {source.key}: empty payload")

    parsed = feedparser.parse(payload)
    if not parsed.entries and (parsed.bozo or not parsed.get("version")):
        detail = parsed.get("bozo_exception")
        suffix = f": {detail}" if detail is not None else ""
        raise SourceFetchError(f"malformed feed for {source.key}{suffix}")

    documents: list[Document] = []
    for entry in parsed.entries:
        document = _entry_to_document(entry, source=source, collected_at=collected_at)
        if document is not None:
            documents.append(document)
    return documents


def _entry_to_document(
    entry: Any, *, source: Source, collected_at: datetime
) -> Document | None:
    url = str(entry.get("link") or "").strip()
    title = str(entry.get("title") or "").strip()
    published_at = _published_at(entry)
    if not url or not title or published_at is None:
        return None

    content = _entry_body(entry)
    if not content:
        content = title

    native_id = str(entry.get("id") or "").strip() or None

    return Document(
        source_key=source.key,
        source_type=source.source_type,
        url=url,
        published_at=published_at,
        collected_at=collected_at,
        title=title,
        content=content,
        source_native_id=native_id,
        language=_optional_language(entry, source),
    )


def _entry_body(entry: Any) -> str:
    content = entry.get("content")
    if content:
        first = content[0]
        value = first.get("value") if hasattr(first, "get") else getattr(first, "value", "")
        body = str(value or "").strip()
        if body:
            return body
    return str(entry.get("summary") or "").strip()


def _published_at(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    if not isinstance(parsed, struct_time):
        return None
    return datetime(
        parsed.tm_year,
        parsed.tm_mon,
        parsed.tm_mday,
        parsed.tm_hour,
        parsed.tm_min,
        parsed.tm_sec,
        tzinfo=UTC,
    )


def _optional_language(entry: Any, source: Source) -> str | None:
    language = entry.get("language") or source.endpoint_config.get("language")
    if language is None:
        return None
    text = str(language).strip()
    return text or None


class RssFeedAdapter:
    """Fetch one RSS/Atom ``Source`` over HTTP and normalize it to Documents.

    Timeout is simple and there is no retry (S001-T012 out of scope). The
    adapter owns an :class:`httpx.Client` unless the caller injects one
    (tests inject a client with ``MockTransport``).
    """

    def __init__(
        self,
        *,
        clock: Clock,
        client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._clock = clock
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_documents(self, source: Source) -> list[Document]:
        payload = self._download(source)
        return parse_rss_documents(
            payload, source=source, collected_at=self._clock.now()
        )

    def _download(self, source: Source) -> bytes:
        feed_url = source.endpoint_config.get(FEED_URL_KEY)
        if not isinstance(feed_url, str) or not feed_url.strip():
            raise SourceFetchError(
                f"{source.key} has no {FEED_URL_KEY} in endpoint_config"
            )
        try:
            response = self._client.get(feed_url)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SourceFetchError(f"timeout fetching {source.key}") from exc
        except httpx.HTTPStatusError as exc:
            raise SourceFetchError(
                f"HTTP {exc.response.status_code} fetching {source.key}"
            ) from exc
        except httpx.RequestError as exc:
            raise SourceFetchError(f"request failed fetching {source.key}: {exc}") from exc
        return response.content
