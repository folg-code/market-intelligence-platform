"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.NarrativeInstrumentImpactRepository`.

"One current assessment per (narrative_id, instrument)" (DOMAIN_MODEL.md)
is implemented as a genuine upsert: ``INSERT ... ON CONFLICT
(narrative_id, instrument) DO UPDATE`` replaces every column of the
existing row for that pair. This differs from
:class:`~moj_projekt.persistence.document_repository.SqlAlchemyDocumentRepository`'s
``DO NOTHING`` dedup (a duplicate write there is a no-op) - here a repeated
write for the same pair is a deliberate re-assessment that should win (see
the domain type's module docstring for the underlying judgment call: this
is a "current state" row, not a versioned history like EvidencePack).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from moj_projekt.domain.enums import (
    CandidateStatus,
    EvidenceRefKind,
    ImpactDirection,
    ImpactHorizon,
    Instrument,
)
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.instrument_impact import NarrativeInstrumentImpact
from moj_projekt.persistence.models import NarrativeInstrumentImpactModel

__all__ = ["SqlAlchemyNarrativeInstrumentImpactRepository"]


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


def _to_domain(row: NarrativeInstrumentImpactModel) -> NarrativeInstrumentImpact:
    return NarrativeInstrumentImpact(
        id=row.id,
        narrative_id=row.narrative_id,
        instrument=Instrument(row.instrument),
        relevance=row.relevance,
        direction=ImpactDirection(row.direction),
        confidence=row.confidence,
        horizon=ImpactHorizon(row.horizon),
        rationale=row.rationale,
        impact_channels=tuple(row.impact_channels),
        evidence_refs=_refs_to_domain(row.evidence_refs),
        status=CandidateStatus(row.status),
        llm_run_id=row.llm_run_id,
    )


class SqlAlchemyNarrativeInstrumentImpactRepository:
    """Persists NarrativeInstrumentImpact rows, one current row per
    ``(narrative_id, instrument)``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self, impact: NarrativeInstrumentImpact
    ) -> NarrativeInstrumentImpact:
        values = dict(
            narrative_id=impact.narrative_id,
            instrument=impact.instrument.value,
            relevance=impact.relevance,
            direction=impact.direction.value,
            confidence=impact.confidence,
            horizon=impact.horizon.value,
            rationale=impact.rationale,
            impact_channels=list(impact.impact_channels),
            evidence_refs=_refs_to_storage(tuple(impact.evidence_refs)),
            status=impact.status.value,
            llm_run_id=impact.llm_run_id,
        )
        update_values = {
            key: value
            for key, value in values.items()
            if key not in ("narrative_id", "instrument")
        }
        statement = (
            pg_insert(NarrativeInstrumentImpactModel)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_narrative_instrument_impacts_narrative_instrument",
                set_=update_values,
            )
        )
        self._session.execute(statement)
        self._session.commit()

        row = self._session.execute(
            select(NarrativeInstrumentImpactModel).where(
                NarrativeInstrumentImpactModel.narrative_id == impact.narrative_id,
                NarrativeInstrumentImpactModel.instrument == impact.instrument.value,
            )
        ).scalar_one()
        return _to_domain(row)

    def get(
        self, narrative_id: UUID, instrument: Instrument
    ) -> NarrativeInstrumentImpact | None:
        row = self._session.execute(
            select(NarrativeInstrumentImpactModel).where(
                NarrativeInstrumentImpactModel.narrative_id == narrative_id,
                NarrativeInstrumentImpactModel.instrument == instrument.value,
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row is not None else None
