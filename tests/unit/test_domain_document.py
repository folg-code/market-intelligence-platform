"""Unit tests for Document invariants (S001-T006) - no database.

Covers DOMAIN_MODEL.md section 3 "Document" invariants: immutability
(structural - no update-content method exists), monotonic
`processing_status`, the dedupe natural key, and the
`collected_at < published_at` data-quality flag.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from moj_projekt.domain.document import Document, ProcessingStatus

_PUBLISHED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_COLLECTED = _PUBLISHED + timedelta(minutes=5)


def _make_document(**overrides: object) -> Document:
    defaults: dict[str, object] = dict(
        source_key="reuters_markets",
        source_type="rss",
        url="https://example.com/article-1",
        published_at=_PUBLISHED,
        collected_at=_COLLECTED,
        title="Fed signals rate path",
        content="Full article body.",
    )
    defaults.update(overrides)
    return Document(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    ["source_key", "source_type", "url", "title", "content"],
)
def test_document_rejects_blank_required_fields(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _make_document(**{field_name: "   "})


def test_document_rejects_blank_source_native_id_when_provided() -> None:
    with pytest.raises(ValueError, match="source_native_id"):
        _make_document(source_native_id="  ")


def test_natural_key_uses_source_native_id_when_present() -> None:
    document = _make_document(source_native_id="guid-123")

    assert document.natural_key == "guid-123"


def test_natural_key_falls_back_to_url_when_no_native_id() -> None:
    document = _make_document(source_native_id=None)

    assert document.natural_key == document.url


def test_dedupe_key_combines_source_natural_key_and_published_at() -> None:
    document = _make_document(source_native_id="guid-123")

    key = document.dedupe_key

    assert key.source_key == "reuters_markets"
    assert key.natural_key == "guid-123"
    assert key.published_at == _PUBLISHED


def test_collected_after_published_has_no_anomaly() -> None:
    document = _make_document(published_at=_PUBLISHED, collected_at=_COLLECTED)

    assert document.has_collection_timestamp_anomaly is False


def test_collected_before_published_is_flagged_not_corrected() -> None:
    anomalous_collected_at = _PUBLISHED - timedelta(minutes=1)

    document = _make_document(collected_at=anomalous_collected_at)

    # The raw value is kept exactly as given - it is flagged, not silently
    # corrected to something >= published_at.
    assert document.collected_at == anomalous_collected_at
    assert document.has_collection_timestamp_anomaly is True


def test_advance_processing_status_allows_forward_transition() -> None:
    document = _make_document(processing_status=ProcessingStatus.COLLECTED)

    advanced = document.advance_processing_status(ProcessingStatus.EVENTS_EXTRACTED)

    assert advanced.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    # Immutable: the original instance is untouched.
    assert document.processing_status is ProcessingStatus.COLLECTED


def test_advance_processing_status_allows_staying_at_the_same_status() -> None:
    document = _make_document(processing_status=ProcessingStatus.EVENTS_EXTRACTED)

    advanced = document.advance_processing_status(ProcessingStatus.EVENTS_EXTRACTED)

    assert advanced.processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_advance_processing_status_rejects_regression() -> None:
    document = _make_document(processing_status=ProcessingStatus.PROCESSED)

    with pytest.raises(ValueError, match="cannot regress"):
        document.advance_processing_status(ProcessingStatus.COLLECTED)


def test_document_has_no_update_content_method() -> None:
    # Structural immutability: nothing on Document can rewrite collected
    # content - the only mutator is advance_processing_status.
    document = _make_document()

    mutators = [
        name
        for name in dir(document)
        if not name.startswith("_") and callable(getattr(document, name))
    ]

    assert mutators == ["advance_processing_status"]
