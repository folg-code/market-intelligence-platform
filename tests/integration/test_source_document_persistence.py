"""Integration tests for Source/Document persistence (S001-T006).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria: a Document round-trips unchanged,
inserting the same Document twice yields one row (no error path), an update
attempt on collected content is rejected at the database level, and a
`collected_at < published_at` document is stored with the anomaly flagged
rather than corrected.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PUBLISHED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_COLLECTED = _PUBLISHED + timedelta(minutes=5)


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


def _seed_source(engine: Engine) -> Source:
    source = Source(
        key="reuters_markets",
        name="Reuters Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Reuters",
    )
    with SqlAlchemyUnitOfWork(engine) as uow:
        return uow.sources.add(source)


def _make_document(**overrides: object) -> Document:
    defaults: dict[str, object] = dict(
        source_key="reuters_markets",
        source_type="rss",
        url="https://example.com/article-1",
        source_native_id="guid-1",
        published_at=_PUBLISHED,
        collected_at=_COLLECTED,
        title="Fed signals rate path",
        content="Full article body.",
    )
    defaults.update(overrides)
    return Document(**defaults)  # type: ignore[arg-type]


def test_document_round_trips_unchanged(
    migrated_session: Session, engine: Engine
) -> None:
    _seed_source(engine)
    document = _make_document()
    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(document)
        fetched = uow.documents.get(stored.id)  # type: ignore[arg-type]

    assert fetched is not None
    assert fetched.source_key == document.source_key
    assert fetched.url == document.url
    assert fetched.title == document.title
    assert fetched.content == document.content
    assert fetched.published_at == document.published_at
    assert fetched.collected_at == document.collected_at
    assert fetched.processing_status is ProcessingStatus.COLLECTED


def test_inserting_the_same_document_twice_yields_one_row(
    migrated_session: Session,
    engine: Engine,
) -> None:
    _seed_source(engine)
    document = _make_document()
    with SqlAlchemyUnitOfWork(engine) as uow:
        first = uow.documents.add(document)
    with SqlAlchemyUnitOfWork(engine) as uow:
        second = uow.documents.add(document)

    assert first.id == second.id
    count = migrated_session.execute(
        text("SELECT count(*) FROM documents")
    ).scalar_one()
    assert count == 1


def test_update_attempt_on_collected_content_is_rejected(
    migrated_session: Session,
    engine: Engine,
) -> None:
    _seed_source(engine)
    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(_make_document())

    with pytest.raises(DBAPIError, match="immutable"):
        migrated_session.execute(
            text("UPDATE documents SET title = :title WHERE id = :id"),
            {"title": "a different title", "id": stored.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_id_mutation_is_rejected_at_the_database(
    migrated_session: Session, engine: Engine
) -> None:
    _seed_source(engine)
    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(_make_document())

    with pytest.raises(DBAPIError, match="immutable"):
        migrated_session.execute(
            text("UPDATE documents SET id = gen_random_uuid() WHERE id = :id"),
            {"id": stored.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_processing_status_regression_is_rejected_at_the_database(
    migrated_session: Session,
    engine: Engine,
) -> None:
    _seed_source(engine)
    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(_make_document())
        uow.documents.advance_processing_status(
            stored.id, ProcessingStatus.PROCESSED  # type: ignore[arg-type]
        )

    with pytest.raises(DBAPIError, match="cannot regress"):
        migrated_session.execute(
            text(
                "UPDATE documents SET processing_status = :status WHERE id = :id"
            ),
            {"status": int(ProcessingStatus.COLLECTED), "id": stored.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_advance_processing_status_moves_forward(
    migrated_session: Session, engine: Engine
) -> None:
    _seed_source(engine)
    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(_make_document())
        advanced = uow.documents.advance_processing_status(
            stored.id,  # type: ignore[arg-type]
            ProcessingStatus.EVENTS_EXTRACTED,
        )

    assert advanced.processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_advance_processing_status_rejects_regression(
    migrated_session: Session,
    engine: Engine,
) -> None:
    _seed_source(engine)
    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(_make_document())
        uow.documents.advance_processing_status(
            stored.id, ProcessingStatus.PROCESSED  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="cannot regress"), SqlAlchemyUnitOfWork(
        engine
    ) as uow:
        uow.documents.advance_processing_status(
            stored.id,  # type: ignore[arg-type]
            ProcessingStatus.COLLECTED,
        )


def test_collected_before_published_is_flagged_not_corrected(
    migrated_session: Session,
    engine: Engine,
) -> None:
    _seed_source(engine)
    anomalous_collected_at = _PUBLISHED - timedelta(minutes=1)
    document = _make_document(collected_at=anomalous_collected_at)

    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.documents.add(document)

    assert stored.collected_at == anomalous_collected_at
    assert stored.has_collection_timestamp_anomaly is True
