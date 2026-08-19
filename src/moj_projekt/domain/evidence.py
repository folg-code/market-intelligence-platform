"""``EvidenceRef`` - a pointer to a Document, an Event, or a fact within an
extraction result (DOMAIN_MODEL.md section 4).

Used by EvidencePack and NarrativeInstrumentImpact to trace every evidence
item back to stored content, without carrying persistence concerns here.
"""

from __future__ import annotations

from dataclasses import dataclass

from moj_projekt.domain.enums import EvidenceRefKind

__all__ = ["EvidenceRef"]


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """A pointer to the Document/Event/fact that backs one piece of evidence.

    ``target_id`` identifies the referenced Document or Event. When ``kind``
    is :attr:`EvidenceRefKind.FACT`, ``fact_locator`` is mandatory and
    identifies the specific fact within that Event's ``extracted_facts``
    (e.g. a key or index); for ``DOCUMENT``/``EVENT`` refs it must be absent.
    """

    kind: EvidenceRefKind
    target_id: str
    fact_locator: str | None = None

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("EvidenceRef.target_id must not be empty")
        if self.kind is EvidenceRefKind.FACT:
            if self.fact_locator is None or not self.fact_locator.strip():
                raise ValueError(
                    "EvidenceRef.fact_locator is required when kind is FACT"
                )
        elif self.fact_locator is not None:
            raise ValueError(
                "EvidenceRef.fact_locator is only meaningful when kind is FACT"
            )
