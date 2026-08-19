"""Live-database tests for the unit-of-work boundary (S002-T002).

Two repositories in one unit of work commit or roll back together; the
cycle's RUNNING row survives a failed stage's rollback.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.alert import Alert
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus
from moj_projekt.domain.document import Document
from moj_projekt.domain.enums import (
    AlertType,
    CandidateStatus,
    EvidenceRefKind,
    ImpactDirection,
    ImpactHorizon,
    Instrument,
    SourceTier,
)
from moj_projekt.domain.event import Event
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.instrument_impact import NarrativeInstrumentImpact
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.domain.narrative import Narrative
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.domain.source import Source
from moj_projekt.persistence.seed_data.sources import SEED_SOURCES
from moj_projekt.persistence.unit_of_work import (
    SqlAlchemyUnitOfWork,
    sqlalchemy_unit_of_work_factory,
)

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_T0 = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_COLLECTED = _PUBLISHED + timedelta(minutes=5)


class _FakeClock:
    def __init__(self, times: list[datetime]) -> None:
        self._times = iter(times)

    def now(self) -> datetime:
        return next(self._times)


@pytest.fixture
def alembic_config(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
    return config


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    settings = Settings()
    db_engine = create_engine(settings.database_url)
    try:
        yield db_engine
    finally:
        db_engine.dispose()


@pytest.fixture
def migrated_session(alembic_config: Config, engine: Engine) -> Iterator[Session]:
    command.upgrade(alembic_config, "head")
    try:
        with Session(engine) as session:
            yield session
    finally:
        command.downgrade(alembic_config, "base")


def _make_event() -> Event:
    return Event(
        type="rate_decision",
        title="Fed holds rates steady",
        occurred_at=_PUBLISHED,
        source_ids=(uuid4(),),
        confidence=0.75,
    )


def _make_llm_run() -> LLMRun:
    return LLMRun(
        task_type="instrument_impact",
        provider="anthropic",
        model="claude-sonnet-4-5-20250929",
        model_version="20250929",
        prompt_version="v1",
        system_prompt_version="v1",
        input_hash="abc123",
        input_reference_ids=("event:1234",),
        output_schema_version="v1",
        raw_output="{}",
        validation_status=CandidateStatus.ACCEPTED,
        created_at=_T0,
    )


def _make_narrative() -> Narrative:
    return Narrative(
        canonical_key=f"narrative_{uuid4().hex[:8]}",
        display_title="Fed rate cut expectations",
        economic_mechanism="Lower policy rate reduces the discount rate.",
        market_interpretation="Bullish for risk assets.",
        category="monetary_policy",
        first_seen=_T0,
        last_seen=_T0,
        updated_at=_T0,
    )


def _count(session: Session, table: str) -> int:
    return int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


def test_two_repositories_are_visible_after_commit(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        event = uow.events.add(_make_event())
        llm_run = uow.llm_runs.add(_make_llm_run())
        event_id = event.id
        llm_run_id = llm_run.id

    with SqlAlchemyUnitOfWork(engine) as uow:
        assert uow.events.get(event_id) is not None  # type: ignore[arg-type]
        assert uow.llm_runs.get(llm_run_id) is not None  # type: ignore[arg-type]
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 1


def test_two_repositories_are_absent_after_rollback(
    migrated_session: Session, engine: Engine
) -> None:
    with pytest.raises(RuntimeError, match="boom"), SqlAlchemyUnitOfWork(engine) as uow:
        uow.events.add(_make_event())
        uow.llm_runs.add(_make_llm_run())
        raise RuntimeError("boom")

    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 0


def test_source_add_is_idempotent_across_units_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    source = SEED_SOURCES[0]
    with SqlAlchemyUnitOfWork(engine) as uow:
        first = uow.sources.add(source)
    with SqlAlchemyUnitOfWork(engine) as uow:
        second = uow.sources.add(source)

    assert first.key == second.key
    assert _count(migrated_session, "sources") == 1


def test_document_add_on_conflict_do_nothing_across_units_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    source = Source(
        key="reuters_markets",
        name="Reuters Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Reuters",
    )
    document = Document(
        source_key="reuters_markets",
        source_type="rss",
        url="https://example.com/article-1",
        source_native_id="guid-1",
        published_at=_PUBLISHED,
        collected_at=_COLLECTED,
        title="Fed signals rate path",
        content="Full article body.",
    )
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(source)
        first = uow.documents.add(document)
    with SqlAlchemyUnitOfWork(engine) as uow:
        second = uow.documents.add(document)

    assert first.id == second.id
    assert _count(migrated_session, "documents") == 1


def test_alert_add_is_idempotent_across_units_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        alert = Alert(
            narrative_id=narrative.id,  # type: ignore[arg-type]
            alert_type=AlertType.EMERGING_NARRATIVE,
            trigger_key="event:1234",
            created_at=_T0,
        )
        first = uow.alerts.add(alert)
    with SqlAlchemyUnitOfWork(engine) as uow:
        second = uow.alerts.add(alert)

    assert first.id == second.id
    assert _count(migrated_session, "alerts") == 1


def test_source_add_is_idempotent_inside_one_unit_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    source = SEED_SOURCES[0]
    with SqlAlchemyUnitOfWork(engine) as uow:
        first = uow.sources.add(source)
        second = uow.sources.add(source)
        assert first.key == second.key
    assert _count(migrated_session, "sources") == 1


def test_document_add_on_conflict_do_nothing_inside_one_unit_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    source = Source(
        key="reuters_markets",
        name="Reuters Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Reuters",
    )
    document = Document(
        source_key="reuters_markets",
        source_type="rss",
        url="https://example.com/article-1",
        source_native_id="guid-1",
        published_at=_PUBLISHED,
        collected_at=_COLLECTED,
        title="Fed signals rate path",
        content="Full article body.",
    )
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(source)
        first = uow.documents.add(document)
        second = uow.documents.add(document)
        assert first.id == second.id
    assert _count(migrated_session, "documents") == 1


def test_alert_add_is_idempotent_inside_one_unit_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        alert = Alert(
            narrative_id=narrative.id,  # type: ignore[arg-type]
            alert_type=AlertType.EMERGING_NARRATIVE,
            trigger_key="event:1234",
            created_at=_T0,
        )
        first = uow.alerts.add(alert)
        second = uow.alerts.add(alert)
        assert first.id == second.id
    assert _count(migrated_session, "alerts") == 1


def test_impact_upsert_replaces_across_units_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        narrative_id = narrative.id
        first = uow.instrument_impacts.upsert(
            NarrativeInstrumentImpact(
                narrative_id=narrative_id,  # type: ignore[arg-type]
                instrument=Instrument.NQ,
                relevance=True,
                direction=ImpactDirection.NEUTRAL,
                confidence=0.4,
                horizon=ImpactHorizon.UNKNOWN,
            )
        )
    with SqlAlchemyUnitOfWork(engine) as uow:
        second = uow.instrument_impacts.upsert(
            NarrativeInstrumentImpact(
                narrative_id=narrative_id,  # type: ignore[arg-type]
                instrument=Instrument.NQ,
                relevance=True,
                direction=ImpactDirection.BULLISH,
                confidence=0.8,
                horizon=ImpactHorizon.INTRADAY,
                rationale="Lower discount rate supports higher equity multiples.",
                evidence_refs=(
                    EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4())),
                ),
            )
        )
        fetched = uow.instrument_impacts.get(
            narrative_id, Instrument.NQ  # type: ignore[arg-type]
        )

    assert first.id == second.id
    assert fetched is not None
    assert fetched.direction is ImpactDirection.BULLISH
    assert _count(migrated_session, "narrative_instrument_impacts") == 1


def test_impact_upsert_replaces_inside_one_unit_of_work(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        narrative_id = narrative.id
        first = uow.instrument_impacts.upsert(
            NarrativeInstrumentImpact(
                narrative_id=narrative_id,  # type: ignore[arg-type]
                instrument=Instrument.NQ,
                relevance=True,
                direction=ImpactDirection.NEUTRAL,
                confidence=0.4,
                horizon=ImpactHorizon.UNKNOWN,
            )
        )
        second = uow.instrument_impacts.upsert(
            NarrativeInstrumentImpact(
                narrative_id=narrative_id,  # type: ignore[arg-type]
                instrument=Instrument.NQ,
                relevance=True,
                direction=ImpactDirection.BULLISH,
                confidence=0.8,
                horizon=ImpactHorizon.INTRADAY,
                rationale="Lower discount rate supports higher equity multiples.",
                evidence_refs=(
                    EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4())),
                ),
            )
        )
        assert first.id == second.id
        fetched = uow.instrument_impacts.get(
            narrative_id, Instrument.NQ  # type: ignore[arg-type]
        )
        assert fetched is not None
        assert fetched.direction is ImpactDirection.BULLISH
    assert _count(migrated_session, "narrative_instrument_impacts") == 1


def test_failed_stage_work_rolls_back_and_cycle_run_is_still_terminal(
    migrated_session: Session, engine: Engine
) -> None:
    def _boom(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
        del cycle_run
        uow.events.add(_make_event())
        uow.llm_runs.add(_make_llm_run())
        raise RuntimeError("extract exploded")

    result = run_cycle(
        clock=_FakeClock([_T0, _T0 + timedelta(seconds=1)]),
        unit_of_work=sqlalchemy_unit_of_work_factory(engine),
        stages=[Stage("extract", _boom)],
    )

    assert result is not None
    assert result.status is CycleRunStatus.FAILED
    assert result.status.is_terminal is True
    assert result.failure_reason is not None
    assert "extract" in result.failure_reason
    assert _count(migrated_session, "cycle_runs") == 1
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 0
    status = migrated_session.execute(
        text("SELECT status FROM cycle_runs")
    ).scalar_one()
    assert status == int(CycleRunStatus.FAILED)
