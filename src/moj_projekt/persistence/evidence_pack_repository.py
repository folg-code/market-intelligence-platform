"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.EvidencePackRepository`.

There is no update path: an EvidencePack is a versioned, immutable
snapshot (ADR-0003). Writing a version that already exists for a narrative
raises (the ``uq_evidence_packs_narrative_version`` unique constraint from
the migration), and the ``evidence_packs_enforce_immutability_trigger``
rejects any UPDATE at the database level, matching Document's layered
immutability enforcement from S001-T006.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from moj_projekt.domain.enums import EvidenceRefKind
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.evidence_pack import EvidencePack
from moj_projekt.persistence.models import EvidencePackModel

__all__ = ["SqlAlchemyEvidencePackRepository"]


def _refs_to_domain(items: list[dict[str, object]]) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(
            kind=EvidenceRefKind(item["kind"]),  # type: ignore[arg-type]
            target_id=item["target_id"],  # type: ignore[arg-type]
            fact_locator=item.get("fact_locator"),  # type: ignore[arg-type]
        )
        for item in items
    )


def _refs_to_storage(refs: tuple[EvidenceRef, ...]) -> list[dict[str, object]]:
    return [
        {
            "kind": ref.kind.value,
            "target_id": ref.target_id,
            "fact_locator": ref.fact_locator,
        }
        for ref in refs
    ]


def _to_domain(row: EvidencePackModel) -> EvidencePack:
    return EvidencePack(
        id=row.id,
        narrative_id=row.narrative_id,
        evidence_version=row.evidence_version,
        generated_at=row.generated_at,
        source_count=row.source_count,
        independent_source_count=row.independent_source_count,
        source_diversity=row.source_diversity,
        supporting_evidence=_refs_to_domain(row.supporting_evidence),
        contradicting_evidence=_refs_to_domain(row.contradicting_evidence),
        top_supporting_events=tuple(UUID(value) for value in row.top_supporting_events),
        key_facts=tuple(row.key_facts),
        strongest_sources=tuple(row.strongest_sources),
        dissenting_sources=tuple(row.dissenting_sources),
        official_evidence=_refs_to_domain(row.official_evidence),
        media_evidence=_refs_to_domain(row.media_evidence),
        social_evidence=_refs_to_domain(row.social_evidence),
        market_evidence=_refs_to_domain(row.market_evidence),
        missing_evidence=tuple(row.missing_evidence),
        evidence_gaps=tuple(row.evidence_gaps),
    )


class SqlAlchemyEvidencePackRepository:
    """Persists EvidencePack snapshots, keyed by (narrative_id, evidence_version)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, evidence_pack: EvidencePack) -> EvidencePack:
        row = EvidencePackModel(
            narrative_id=evidence_pack.narrative_id,
            evidence_version=evidence_pack.evidence_version,
            generated_at=evidence_pack.generated_at,
            source_count=evidence_pack.source_count,
            independent_source_count=evidence_pack.independent_source_count,
            source_diversity=evidence_pack.source_diversity,
            supporting_evidence=_refs_to_storage(evidence_pack.supporting_evidence),
            contradicting_evidence=_refs_to_storage(evidence_pack.contradicting_evidence),
            top_supporting_events=[
                str(event_id) for event_id in evidence_pack.top_supporting_events
            ],
            key_facts=list(evidence_pack.key_facts),
            strongest_sources=list(evidence_pack.strongest_sources),
            dissenting_sources=list(evidence_pack.dissenting_sources),
            official_evidence=_refs_to_storage(evidence_pack.official_evidence),
            media_evidence=_refs_to_storage(evidence_pack.media_evidence),
            social_evidence=_refs_to_storage(evidence_pack.social_evidence),
            market_evidence=_refs_to_storage(evidence_pack.market_evidence),
            missing_evidence=list(evidence_pack.missing_evidence),
            evidence_gaps=list(evidence_pack.evidence_gaps),
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_domain(row)

    def get_current(self, narrative_id: UUID) -> EvidencePack | None:
        row = self._session.execute(
            select(EvidencePackModel)
            .where(EvidencePackModel.narrative_id == narrative_id)
            .order_by(EvidencePackModel.evidence_version.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    def get_version(
        self, narrative_id: UUID, evidence_version: int
    ) -> EvidencePack | None:
        row = self._session.execute(
            select(EvidencePackModel).where(
                EvidencePackModel.narrative_id == narrative_id,
                EvidencePackModel.evidence_version == evidence_version,
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row is not None else None
