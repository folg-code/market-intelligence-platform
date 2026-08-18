"""Integration test for the Alembic baseline migration.

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria from S001-T004: upgrading an empty
database to head enables the `vector` extension, is repeatable (upgrading
again from head is a no-op, not an error), and the baseline's downgrade is
defined and reverses the extension.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from moj_projekt.config.settings import Settings

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


def _pgvector_enabled(db_engine: Engine) -> bool:
    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).first()
    return row is not None


def test_upgrade_to_head_enables_pgvector_and_is_repeatable(
    alembic_config: Config, engine: Engine
) -> None:
    try:
        command.upgrade(alembic_config, "head")
        assert _pgvector_enabled(engine)

        # Repeatable: re-running upgrade to head from head is a no-op.
        command.upgrade(alembic_config, "head")
        assert _pgvector_enabled(engine)
    finally:
        command.downgrade(alembic_config, "base")


def test_baseline_downgrade_disables_pgvector(alembic_config: Config, engine: Engine) -> None:
    command.upgrade(alembic_config, "head")

    command.downgrade(alembic_config, "base")

    assert not _pgvector_enabled(engine)
