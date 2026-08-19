"""Integration tests for RSS ingest into Documents (S001-T012).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

The live-feed test is additionally marked ``network`` so default pytest and
CI (`pytest -o addopts="" -m "not network"`) exclude it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.cycle.run_once import run_once
from moj_projekt.domain.clock import Clock
from moj_projekt.domain.cycle_run import CycleRunStatus
from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.source import Source
from moj_projekt.ingestion.rss import RSS_SOURCE_TYPE, RssFeedAdapter
from moj_projekt.persistence.seed_data.sources import SEED_SOURCES
from moj_projekt.persistence.seed_sources import seed_sources
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "rss"
_COLLECTED = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
_BLOOMBERG_FEED_URL = next(
    source.endpoint_config["feed_url"]
    for source in SEED_SOURCES
    if source.key == "bloomberg_markets"
)


class _FixedClock:
    def now(self) -> datetime:
        return _COLLECTED


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


def _document_count(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM documents")).scalar_one())


def _rss_source(key: str, feed_url: str) -> Source:
    return Source(
        key=key,
        name=key,
        source_type=RSS_SOURCE_TYPE,
        tier=SourceTier.PROFESSIONAL,
        publisher=key,
        endpoint_config={"feed_url": feed_url},
    )


def _adapter(clock: Clock, handler: httpx.MockTransport) -> RssFeedAdapter:
    client = httpx.Client(transport=handler, timeout=15.0)
    return RssFeedAdapter(clock=clock, client=client)


def test_fixture_feed_creates_documents_and_re_run_inserts_none(
    migrated_session: Session,
    engine: Engine,
) -> None:
    payload = (_FIXTURES / "sample_feed.xml").read_bytes()
    feed_url = "https://example.com/markets/feed.xml"
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(_rss_source("bloomberg_markets", feed_url))

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == feed_url
        return httpx.Response(200, content=payload)

    clock = _FixedClock()
    adapter = _adapter(clock, httpx.MockTransport(handler))
    try:
        first = run_once(
            engine,
            clock=clock,
            adapters={RSS_SOURCE_TYPE: adapter},
        )
        count_after_first = _document_count(migrated_session)
        second = run_once(
            engine,
            clock=clock,
            adapters={RSS_SOURCE_TYPE: adapter},
        )
        count_after_second = _document_count(migrated_session)
    finally:
        adapter.close()

    assert first is not None
    assert second is not None
    assert first.status is CycleRunStatus.SUCCEEDED
    assert second.status is CycleRunStatus.SUCCEEDED
    assert first.source_outcomes["bloomberg_markets"].succeeded is True
    assert count_after_first == 2
    assert count_after_second == count_after_first

    row = migrated_session.execute(
        text(
            "SELECT source_key, url, published_at, collected_at, title, content "
            "FROM documents ORDER BY url"
        )
    ).first()
    assert row is not None
    assert row.source_key == "bloomberg_markets"
    assert row.url.startswith("https://example.com/markets/")
    assert row.published_at is not None
    assert row.collected_at == _COLLECTED
    assert row.title
    assert row.content


@pytest.mark.parametrize(
    ("status_code", "body", "reason"),
    [
        (None, None, "timeout"),
        (503, b"unavailable", "HTTP 503"),
        (200, (_FIXTURES / "malformed_feed.html").read_bytes(), "malformed feed"),
    ],
)
def test_simulated_fetch_failure_leaves_cycle_ok_source_failed_and_no_documents(
    migrated_session: Session,
    engine: Engine,
    status_code: int | None,
    body: bytes | None,
    reason: str,
) -> None:
    feed_url = "https://example.com/markets/feed.xml"
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(_rss_source("bloomberg_markets", feed_url))

    def handler(_request: httpx.Request) -> httpx.Response:
        if status_code is None:
            raise httpx.TimeoutException("timed out")
        return httpx.Response(status_code, content=body or b"")

    adapter = _adapter(_FixedClock(), httpx.MockTransport(handler))
    try:
        result = run_once(
            engine,
            clock=_FixedClock(),
            adapters={RSS_SOURCE_TYPE: adapter},
        )
    finally:
        adapter.close()

    assert result is not None
    assert result.status is CycleRunStatus.SUCCEEDED
    outcome = result.source_outcomes["bloomberg_markets"]
    assert outcome.succeeded is False
    assert outcome.failure_reason is not None
    assert reason in outcome.failure_reason
    assert _document_count(migrated_session) == 0


@pytest.mark.network
def test_live_bloomberg_feed_creates_documents(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        seed_sources(uow.sources)

    first = run_once(engine)
    count_after_first = _document_count(migrated_session)
    second = run_once(engine)
    count_after_second = _document_count(migrated_session)

    assert first is not None
    assert second is not None
    assert first.status is CycleRunStatus.SUCCEEDED
    assert second.status is CycleRunStatus.SUCCEEDED
    bloomberg = first.source_outcomes["bloomberg_markets"]
    assert bloomberg.succeeded is True, bloomberg.failure_reason
    assert count_after_first > 0
    assert count_after_second == count_after_first

    row = migrated_session.execute(
        text(
            "SELECT source_key, url, published_at, collected_at, title, content "
            "FROM documents WHERE source_key = 'bloomberg_markets' LIMIT 1"
        )
    ).first()
    assert row is not None
    assert row.source_key == "bloomberg_markets"
    assert row.url
    assert row.published_at is not None
    assert row.collected_at is not None
    assert row.title
    assert row.content
    assert _BLOOMBERG_FEED_URL.startswith("https://")
