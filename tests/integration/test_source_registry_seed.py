"""Integration tests for the MVP Source registry seed (S001-T010).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria: running the seed twice leaves the
registry unchanged (no duplicates, no error), every seeded Source has
exactly one tier and a non-empty publisher, and both Tier 1 and Tier 2
sources are present.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.domain.enums import SourceTier
from moj_projekt.persistence.seed_data.sources import SEED_SOURCES
from moj_projekt.persistence.seed_sources import seed_sources
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_seeding_twice_leaves_the_registry_unchanged(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        first_run = seed_sources(uow.sources)
    with SqlAlchemyUnitOfWork(engine) as uow:
        second_run = seed_sources(uow.sources)

    assert {source.key for source in first_run} == {
        source.key for source in second_run
    }
    count = migrated_session.execute(text("SELECT count(*) FROM sources")).scalar_one()
    assert count == len(SEED_SOURCES)


def test_every_seeded_source_has_one_tier_and_a_publisher(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        seeded = seed_sources(uow.sources)

    assert len(seeded) == len(SEED_SOURCES)
    for source in seeded:
        assert isinstance(source.tier, SourceTier)
        assert source.publisher.strip() != ""


def test_registry_includes_tier_1_and_tier_2_sources(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        seeded = seed_sources(uow.sources)

    tiers = {source.tier for source in seeded}
    assert SourceTier.PRIMARY in tiers
    assert SourceTier.PROFESSIONAL in tiers


def test_seeded_sources_are_persisted_and_retrievable_individually(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        seed_sources(uow.sources)

    row = migrated_session.execute(
        text("SELECT tier, publisher FROM sources WHERE key = :key"),
        {"key": "fed_fomc"},
    ).one()

    assert row.tier == int(SourceTier.PRIMARY)
    assert row.publisher == "Federal Reserve"
