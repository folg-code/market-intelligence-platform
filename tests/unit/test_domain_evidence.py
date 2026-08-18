import pytest

from moj_projekt.domain.enums import EvidenceRefKind
from moj_projekt.domain.evidence import EvidenceRef


def test_document_ref_is_valid_without_a_fact_locator() -> None:
    ref = EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id="doc-1")

    assert ref.kind is EvidenceRefKind.DOCUMENT
    assert ref.target_id == "doc-1"
    assert ref.fact_locator is None


def test_event_ref_is_valid_without_a_fact_locator() -> None:
    ref = EvidenceRef(kind=EvidenceRefKind.EVENT, target_id="event-1")

    assert ref.fact_locator is None


def test_fact_ref_requires_a_fact_locator() -> None:
    with pytest.raises(ValueError):
        EvidenceRef(kind=EvidenceRefKind.FACT, target_id="event-1")


def test_fact_ref_with_a_locator_is_valid() -> None:
    ref = EvidenceRef(
        kind=EvidenceRefKind.FACT, target_id="event-1", fact_locator="extracted_facts[0]"
    )

    assert ref.fact_locator == "extracted_facts[0]"


def test_non_fact_ref_rejects_a_fact_locator() -> None:
    with pytest.raises(ValueError):
        EvidenceRef(
            kind=EvidenceRefKind.DOCUMENT, target_id="doc-1", fact_locator="extracted_facts[0]"
        )


@pytest.mark.parametrize("target_id", ["", "   "])
def test_empty_target_id_is_rejected(target_id: str) -> None:
    with pytest.raises(ValueError):
        EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=target_id)


def test_evidence_ref_is_immutable() -> None:
    ref = EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id="doc-1")

    with pytest.raises(AttributeError):
        ref.target_id = "doc-2"  # type: ignore[misc]
