"""Unit tests for EvidencePack invariants (S001-T007) - no database.

Covers DOMAIN_MODEL.md section 3 "EvidencePack" invariants and ADR-0003:
`independent_source_count <= source_count`, positive `evidence_version`,
and `market_evidence` staying empty in MVP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from moj_projekt.domain.enums import EvidenceRefKind
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.evidence_pack import EvidencePack

_GENERATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _make_pack(**overrides: object) -> EvidencePack:
    defaults: dict[str, object] = dict(
        narrative_id=uuid4(),
        evidence_version=1,
        generated_at=_GENERATED_AT,
        source_count=3,
        independent_source_count=2,
        source_diversity=2,
    )
    defaults.update(overrides)
    return EvidencePack(**defaults)  # type: ignore[arg-type]


def test_evidence_pack_rejects_independent_count_above_source_count() -> None:
    with pytest.raises(ValueError, match="independent_source_count"):
        _make_pack(source_count=1, independent_source_count=2)


def test_evidence_pack_accepts_independent_count_equal_to_source_count() -> None:
    pack = _make_pack(source_count=2, independent_source_count=2)

    assert pack.independent_source_count == pack.source_count


def test_evidence_pack_rejects_negative_source_count() -> None:
    with pytest.raises(ValueError, match="source_count"):
        _make_pack(source_count=-1, independent_source_count=0)


def test_evidence_pack_rejects_negative_independent_source_count() -> None:
    with pytest.raises(ValueError, match="independent_source_count"):
        _make_pack(independent_source_count=-1)


def test_evidence_pack_rejects_negative_source_diversity() -> None:
    with pytest.raises(ValueError, match="source_diversity"):
        _make_pack(source_diversity=-1)


@pytest.mark.parametrize("version", [0, -1])
def test_evidence_pack_rejects_non_positive_evidence_version(version: int) -> None:
    with pytest.raises(ValueError, match="evidence_version"):
        _make_pack(evidence_version=version)


def test_evidence_pack_rejects_non_empty_market_evidence_in_mvp() -> None:
    market_ref = EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4()))

    with pytest.raises(ValueError, match="market_evidence"):
        _make_pack(market_evidence=(market_ref,))


def test_evidence_pack_accepts_empty_market_evidence() -> None:
    pack = _make_pack(market_evidence=())

    assert pack.market_evidence == ()


def test_evidence_pack_traces_evidence_items_via_evidence_ref() -> None:
    document_ref = EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4()))
    event_ref = EvidenceRef(kind=EvidenceRefKind.EVENT, target_id=str(uuid4()))

    pack = _make_pack(
        supporting_evidence=(document_ref,),
        contradicting_evidence=(event_ref,),
        official_evidence=(document_ref,),
    )

    assert pack.supporting_evidence == (document_ref,)
    assert pack.contradicting_evidence == (event_ref,)
    assert pack.official_evidence == (document_ref,)
