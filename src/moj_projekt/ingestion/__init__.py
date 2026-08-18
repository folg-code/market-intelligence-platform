"""Fetches and normalizes external sources into Documents.

Per-source failure isolation lives in the cycle ingest stage; this package
only produces Documents (or raises :class:`SourceFetchError`). Network
access is confined here. See docs/reference/MODULE_MAP.md.
"""

from __future__ import annotations

from moj_projekt.ingestion.adapter import SourceAdapter, SourceFetchError
from moj_projekt.ingestion.rss import RSS_SOURCE_TYPE, RssFeedAdapter, parse_rss_documents

__all__ = [
    "RSS_SOURCE_TYPE",
    "RssFeedAdapter",
    "SourceAdapter",
    "SourceFetchError",
    "parse_rss_documents",
]
