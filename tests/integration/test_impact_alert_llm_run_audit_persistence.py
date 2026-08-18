"""Integration tests for Impact/Alert/LLMRun/AuditEntry persistence (S001-T009).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria: one current impact assessment per
(narrative, instrument), a non-neutral direction without rationale/evidence
is rejected at the database level too, Alerts are unique per (narrative,
type, trigger), and LLMRun/AuditEntry reject both UPDATE and DELETE.
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
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.domain.alert import Alert
from moj_projekt.domain.audit_entry import AuditEntry
from moj_projekt.domain.enums import (
    AlertType,
    CandidateStatus,
    EvidenceRefKind,
    ImpactDirection,
    ImpactHorizon,
    Instrument,
)
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.instrument_impact import NarrativeInstrumentImpact
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.domain.narrative import Narrative
from moj_projekt.persistence.alert_repository import SqlAlchemyAlertRepository
from moj_projekt.persistence.audit_entry_repository import SqlAlchemyAuditEntryRepository
from moj_projekt.persistence.instrument_impact_repository import (
    SqlAlchemyNarrativeInstrumentImpactRepository,
)
from moj_projekt.persistence.llm_run_repository import SqlAlchemyLLMRunRepository
from moj_projekt.persistence.narrative_repository import SqlAlchemyNarrativeRepository

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIRST_SEEN = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_LAST_SEEN = _FIRST_SEEN + timedelta(hours=1)
_CREATED_AT = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)


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


def _make_narrative(**overrides: object) -> Narrative:
    defaults: dict[str, object] = dict(
        canonical_key=f"narrative_{uuid4().hex[:8]}",
        display_title="Fed rate cut expectations",
        economic_mechanism="Lower policy rate reduces the discount rate.",
        market_interpretation="Bullish for risk assets.",
        category="monetary_policy",
        first_seen=_FIRST_SEEN,
        last_seen=_LAST_SEEN,
        updated_at=_LAST_SEEN,
    )
    defaults.update(overrides)
    return Narrative(**defaults)  # type: ignore[arg-type]


def _make_llm_run(**overrides: object) -> LLMRun:
    defaults: dict[str, object] = dict(
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
        created_at=_CREATED_AT,
    )
    defaults.update(overrides)
    return LLMRun(**defaults)  # type: ignore[arg-type]


def test_upgrade_to_head_and_back_round_trips_new_tables(
    alembic_config: Config, engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        }
    assert {
        "narrative_instrument_impacts",
        "alerts",
        "llm_runs",
        "audit_entries",
    } <= tables

    command.downgrade(alembic_config, "base")
    with engine.connect() as connection:
        tables_after_downgrade = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        }
    assert "llm_runs" not in tables_after_downgrade


def test_one_current_impact_assessment_per_narrative_instrument(
    migrated_session: Session,
) -> None:
    narrative = SqlAlchemyNarrativeRepository(migrated_session).add(_make_narrative())
    repo = SqlAlchemyNarrativeInstrumentImpactRepository(migrated_session)

    first = repo.upsert(
        NarrativeInstrumentImpact(
            narrative_id=narrative.id,  # type: ignore[arg-type]
            instrument=Instrument.NQ,
            relevance=True,
            direction=ImpactDirection.NEUTRAL,
            confidence=0.4,
            horizon=ImpactHorizon.UNKNOWN,
        )
    )
    second = repo.upsert(
        NarrativeInstrumentImpact(
            narrative_id=narrative.id,  # type: ignore[arg-type]
            instrument=Instrument.NQ,
            relevance=True,
            direction=ImpactDirection.BULLISH,
            confidence=0.8,
            horizon=ImpactHorizon.INTRADAY,
            rationale="Lower discount rate supports higher equity multiples.",
            evidence_refs=(EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4())),),
        )
    )

    assert first.id == second.id
    fetched = repo.get(narrative.id, Instrument.NQ)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.direction is ImpactDirection.BULLISH
    assert fetched.confidence == 0.8


def test_non_neutral_direction_without_evidence_is_rejected_at_the_database(
    migrated_session: Session,
) -> None:
    narrative = SqlAlchemyNarrativeRepository(migrated_session).add(_make_narrative())

    # The domain constructor already rejects this
    # (NarrativeInstrumentImpact.__post_init__), so exercising the CHECK
    # constraint requires bypassing it with a raw INSERT.
    with pytest.raises(
        IntegrityError,
        match="ck_narrative_instrument_impacts_non_neutral_requires_evidence",
    ):
        migrated_session.execute(
            text(
                "INSERT INTO narrative_instrument_impacts "
                "(narrative_id, instrument, relevance, direction, confidence, "
                "horizon, rationale, evidence_refs) "
                "VALUES (:nid, 'NQ', true, 'bullish', 0.5, 'unknown', '', '[]'::jsonb)"
            ),
            {"nid": narrative.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_alerts_are_unique_per_narrative_type_trigger(migrated_session: Session) -> None:
    narrative = SqlAlchemyNarrativeRepository(migrated_session).add(_make_narrative())
    repo = SqlAlchemyAlertRepository(migrated_session)
    alert = Alert(
        narrative_id=narrative.id,  # type: ignore[arg-type]
        alert_type=AlertType.EMERGING_NARRATIVE,
        trigger_key="event:1234",
        created_at=_CREATED_AT,
    )

    first = repo.add(alert)
    second = repo.add(alert)

    assert first.id == second.id


def test_llm_runs_reject_update(migrated_session: Session) -> None:
    stored = SqlAlchemyLLMRunRepository(migrated_session).add(_make_llm_run())

    with pytest.raises(DBAPIError, match="llm_runs: rows are append-only"):
        migrated_session.execute(
            text("UPDATE llm_runs SET task_type = 'changed' WHERE id = :id"),
            {"id": stored.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_llm_runs_reject_delete(migrated_session: Session) -> None:
    stored = SqlAlchemyLLMRunRepository(migrated_session).add(_make_llm_run())

    with pytest.raises(DBAPIError, match="llm_runs: rows are append-only"):
        migrated_session.execute(
            text("DELETE FROM llm_runs WHERE id = :id"), {"id": stored.id}
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_audit_entries_reject_update(migrated_session: Session) -> None:
    stored = SqlAlchemyAuditEntryRepository(migrated_session).add(
        AuditEntry(
            actor="trader",
            action="reject_event_assignment",
            target_id="narrative_event:1234",
            timestamp=_CREATED_AT,
            reason="Not the same economic mechanism.",
        )
    )

    with pytest.raises(DBAPIError, match="audit_entries: rows are append-only"):
        migrated_session.execute(
            text("UPDATE audit_entries SET reason = 'changed' WHERE id = :id"),
            {"id": stored.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_audit_entries_reject_delete(migrated_session: Session) -> None:
    stored = SqlAlchemyAuditEntryRepository(migrated_session).add(
        AuditEntry(
            actor="trader",
            action="reject_event_assignment",
            target_id="narrative_event:1234",
            timestamp=_CREATED_AT,
            reason="Not the same economic mechanism.",
        )
    )

    with pytest.raises(DBAPIError, match="audit_entries: rows are append-only"):
        migrated_session.execute(
            text("DELETE FROM audit_entries WHERE id = :id"), {"id": stored.id}
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_llm_run_carries_reproducibility_fields(migrated_session: Session) -> None:
    stored = SqlAlchemyLLMRunRepository(migrated_session).add(_make_llm_run())
    fetched = SqlAlchemyLLMRunRepository(migrated_session).get(stored.id)  # type: ignore[arg-type]

    assert fetched is not None
    assert fetched.provider == "anthropic"
    assert fetched.model == "claude-sonnet-4-5-20250929"
    assert fetched.model_version == "20250929"
    assert fetched.prompt_version == "v1"
    assert fetched.input_reference_ids == ("event:1234",)
