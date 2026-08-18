"""Unit tests for Source invariants (S001-T006) - no database."""

from __future__ import annotations

import pytest

from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source


def _make_source(**overrides: object) -> Source:
    defaults: dict[str, object] = dict(
        key="reuters_markets",
        name="Reuters Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Reuters",
    )
    defaults.update(overrides)
    return Source(**defaults)  # type: ignore[arg-type]


def test_source_has_exactly_one_tier() -> None:
    source = _make_source(tier=SourceTier.PRIMARY)

    assert source.tier is SourceTier.PRIMARY


@pytest.mark.parametrize("field_name", ["key", "name", "source_type", "publisher"])
def test_source_rejects_blank_required_fields(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _make_source(**{field_name: "  "})


def test_source_defaults_endpoint_config_to_empty_and_active_true() -> None:
    source = _make_source()

    assert source.endpoint_config == {}
    assert source.active is True
