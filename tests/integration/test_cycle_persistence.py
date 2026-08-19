"""Integration tests for the CycleRun record and cycle orchestration
(S001-T011, S002-T004).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria: two consecutive calls to the
direct entrypoint each produce exactly one terminal CycleRun row (no
overlap artifacts); a second UPDATE of a terminal row is rejected by a
database trigger (PRB-004); and the database-level "at most one RUNNING
row" constraint (and the CHECK constraints mirroring CycleRun's own
invariants) reject rows a raw INSERT tries to sneak past the domain
constructor - mirroring the S001-T009 pattern of testing DB-level
backstops directly with `text(...)` SQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.cycle.run_once import run_once
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STARTED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
_TERMINAL_IMMUTABILITY_TRIGGER = "cycle_runs_reject_terminal_update_trigger"
_TERMINAL_IMMUTABILITY_FUNCTION = "cycle_runs_reject_terminal_update"


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


def test_upgrade_to_head_and_back_round_trips_cycle_runs_table(
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
    assert "cycle_runs" in tables

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
    assert "cycle_runs" not in tables_after_downgrade


def test_two_consecutive_cycles_each_produce_one_terminal_cycle_run(
    migrated_session: Session,
    engine: Engine,
) -> None:
    first = run_once(engine)
    second = run_once(engine)

    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert first.status is CycleRunStatus.SUCCEEDED
    assert second.status is CycleRunStatus.SUCCEEDED
    assert first.started_at is not None
    assert first.ended_at is not None
    assert second.started_at is not None
    assert second.ended_at is not None

    row_count = migrated_session.execute(
        text("SELECT count(*) FROM cycle_runs")
    ).scalar_one()
    assert row_count == 2

    running_count = migrated_session.execute(
        text("SELECT count(*) FROM cycle_runs WHERE status = 1")
    ).scalar_one()
    assert running_count == 0


def test_repository_add_get_running_and_update_round_trip(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        created = uow.cycle_runs.add(CycleRun(started_at=_STARTED_AT))
        assert created.id is not None
        running = uow.cycle_runs.get_running()
        assert running is not None
        assert running.id == created.id

    ended_at = _STARTED_AT + timedelta(seconds=5)
    finished = created.finish(status=CycleRunStatus.SUCCEEDED, ended_at=ended_at)
    with SqlAlchemyUnitOfWork(engine) as uow:
        updated = uow.cycle_runs.update(finished)

        assert updated.status is CycleRunStatus.SUCCEEDED
        assert uow.cycle_runs.get_running() is None

        fetched = uow.cycle_runs.get(created.id)
        assert fetched is not None
        assert fetched.ended_at == ended_at
        assert fetched.status is CycleRunStatus.SUCCEEDED


def _terminal_immutability_trigger_exists(db_engine: Engine) -> bool:
    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT 1 FROM pg_trigger WHERE tgname = :name AND NOT tgisinternal"),
            {"name": _TERMINAL_IMMUTABILITY_TRIGGER},
        ).first()
    return row is not None


def _terminal_immutability_function_exists(db_engine: Engine) -> bool:
    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT 1 FROM pg_proc WHERE proname = :name"),
            {"name": _TERMINAL_IMMUTABILITY_FUNCTION},
        ).first()
    return row is not None


def test_second_update_of_a_terminal_cycle_run_is_rejected_at_the_database(
    migrated_session: Session,
) -> None:
    repository = SqlAlchemyCycleRunRepository(migrated_session)
    created = repository.add(CycleRun(started_at=_STARTED_AT))
    ended_at = _STARTED_AT + timedelta(seconds=5)
    finished = created.finish(status=CycleRunStatus.SUCCEEDED, ended_at=ended_at)
    updated = repository.update(finished)

    with pytest.raises(DBAPIError, match="cycle_runs: terminal rows cannot be updated"):
        repository.update(updated)
    migrated_session.rollback()

    # Raw SQL too: the rejection is the trigger, not Python-side finish().
    with pytest.raises(DBAPIError, match="cycle_runs: terminal rows cannot be updated"):
        migrated_session.execute(
            text("UPDATE cycle_runs SET stage_outcomes = '{}'::jsonb WHERE id = :id"),
            {"id": updated.id},
        )
        migrated_session.commit()
    migrated_session.rollback()

    fetched = repository.get(created.id)
    assert fetched is not None
    assert fetched.status is CycleRunStatus.SUCCEEDED
    assert fetched.ended_at == ended_at


def test_failed_terminal_cycle_run_is_also_immutable_at_the_database(
    migrated_session: Session,
) -> None:
    migrated_session.execute(
        text(
            "INSERT INTO cycle_runs (started_at, ended_at, status, failure_reason) "
            "VALUES (now(), now(), 3, 'stage raised')"
        )
    )
    migrated_session.commit()

    with pytest.raises(DBAPIError, match="cycle_runs: terminal rows cannot be updated"):
        migrated_session.execute(
            text("UPDATE cycle_runs SET failure_reason = 'changed' WHERE status = 3")
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_terminal_immutability_trigger_round_trips_upgrade_downgrade_upgrade(
    alembic_config: Config, engine: Engine
) -> None:
    try:
        command.upgrade(alembic_config, "head")
        assert _terminal_immutability_trigger_exists(engine)
        assert _terminal_immutability_function_exists(engine)

        command.downgrade(alembic_config, "0006")
        assert not _terminal_immutability_trigger_exists(engine)
        assert not _terminal_immutability_function_exists(engine)
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
        assert "cycle_runs" in tables

        command.upgrade(alembic_config, "head")
        assert _terminal_immutability_trigger_exists(engine)
        assert _terminal_immutability_function_exists(engine)
    finally:
        command.downgrade(alembic_config, "base")


def test_second_running_row_is_rejected_by_the_database(
    migrated_session: Session,
) -> None:
    migrated_session.execute(
        text("INSERT INTO cycle_runs (started_at, status) VALUES (now(), 1)")
    )
    migrated_session.commit()

    with pytest.raises(IntegrityError, match="uq_cycle_runs_single_running"):
        migrated_session.execute(
            text("INSERT INTO cycle_runs (started_at, status) VALUES (now(), 1)")
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_running_status_with_an_ended_at_is_rejected_by_the_database(
    migrated_session: Session,
) -> None:
    with pytest.raises(IntegrityError, match="ck_cycle_runs_ended_at_matches_status"):
        migrated_session.execute(
            text(
                "INSERT INTO cycle_runs (started_at, ended_at, status) "
                "VALUES (now(), now(), 1)"
            )
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_failed_status_without_a_failure_reason_is_rejected_by_the_database(
    migrated_session: Session,
) -> None:
    with pytest.raises(
        IntegrityError, match="ck_cycle_runs_failure_reason_matches_status"
    ):
        migrated_session.execute(
            text(
                "INSERT INTO cycle_runs (started_at, ended_at, status) "
                "VALUES (now(), now(), 3)"
            )
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_unknown_status_value_is_rejected_by_the_database(
    migrated_session: Session,
) -> None:
    # ended_at is set (satisfying ck_cycle_runs_ended_at_matches_status for
    # any non-RUNNING status) and failure_reason is left NULL (satisfying
    # ck_cycle_runs_failure_reason_matches_status for any non-FAILED
    # status), so status=99 is the only constraint this row can still
    # violate.
    with pytest.raises(IntegrityError, match="ck_cycle_runs_status_valid"):
        migrated_session.execute(
            text(
                "INSERT INTO cycle_runs (started_at, ended_at, status) "
                "VALUES (now(), now(), 99)"
            )
        )
        migrated_session.commit()
    migrated_session.rollback()
