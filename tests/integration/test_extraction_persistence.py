"""Live-database tests for the extraction service (S002-T008).

Each verdict is persisted through one unit of work. Failure injection
between the two writes leaves neither row.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.domain.document import Document
from moj_projekt.domain.enums import CandidateStatus, SourceTier
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.domain.source import Source
from moj_projekt.extraction.service import ExtractionService
from moj_projekt.extraction.types import ValidationConfig
from moj_projekt.llm.client import TokenUsage
from moj_projekt.llm.fake import FakeLLMClient
from moj_projekt.llm.models import EXTRACTION_MODEL_ID
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "llm" / "extraction_response_v1.json"
_T0 = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 17, 18, 0, tzinfo=UTC)
_CONFIG = ValidationConfig(
    auto_accept_min_confidence=0.7,
    occurred_at_max_before=timedelta(days=365),
    occurred_at_max_after=timedelta(days=2),
)


class _FixedClock:
    def now(self) -> datetime:
        return _T0


class _CountingAdd:
    def __init__(self, inner: Any, counter: list[int], fail_at: int) -> None:
        self._inner = inner
        self._counter = counter
        self._fail_at = fail_at

    def add(self, item: Any) -> Any:
        self._counter[0] += 1
        if self._counter[0] >= self._fail_at:
            raise RuntimeError("injected failure between writes")
        return self._inner.add(item)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _FailOnSecondWrite:
    """Fails the second of ``events.add`` / ``llm_runs.add``, regardless of order."""

    def __init__(self, inner: UnitOfWork) -> None:
        self._inner = inner
        self._counter = [0]
        self.events = _CountingAdd(inner.events, self._counter, fail_at=2)
        self.llm_runs = _CountingAdd(inner.llm_runs, self._counter, fail_at=2)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


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


def _count(session: Session, table: str) -> int:
    return int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


def _source() -> Source:
    return Source(
        key="bloomberg_markets",
        name="Bloomberg Markets",
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher="Bloomberg L.P.",
    )


def _document() -> Document:
    return Document(
        source_key="bloomberg_markets",
        source_type="rss",
        url="https://example.com/article-1",
        source_native_id="guid-1",
        published_at=_PUBLISHED,
        collected_at=_PUBLISHED + timedelta(minutes=5),
        title="Fed holds policy rate",
        content="The Federal Reserve left the policy rate unchanged.",
    )


def _persist_document(engine: Engine) -> Document:
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(_source())
        return uow.documents.add(_document())


def _service(raw: str, *, usage: TokenUsage | None = None) -> ExtractionService:
    client = FakeLLMClient(
        raw.encode("utf-8"),
        token_usage=usage,
        latency_seconds=0.42,
    )
    return ExtractionService(
        client=client,
        clock=_FixedClock(),
        validation_config=_CONFIG,
    )


def _accepted_event(**overrides: object) -> dict[str, object]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    event = payload["events"][0]
    event.update(overrides)
    return event  # type: ignore[no-any-return]


def test_accepted_yields_event_and_one_llm_run_after_commit(
    migrated_session: Session, engine: Engine
) -> None:
    document = _persist_document(engine)
    usage = TokenUsage(
        input_tokens=10,
        output_tokens=20,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    raw = _FIXTURE.read_text(encoding="utf-8")
    service = _service(raw, usage=usage)

    with SqlAlchemyUnitOfWork(engine) as uow:
        outcome = service.extract(document, uow)

    assert outcome.verdict is CandidateStatus.ACCEPTED
    assert len(outcome.events) == 1
    assert outcome.llm_run.id is not None
    event_id = outcome.events[0].id
    run_id = outcome.llm_run.id

    with SqlAlchemyUnitOfWork(engine) as uow:
        stored_event = uow.events.get(event_id)  # type: ignore[arg-type]
        stored_run = uow.llm_runs.get(run_id)
        referenced = uow.documents.get(UUID(stored_run.input_reference_ids[0]))  # type: ignore[union-attr]

    assert stored_event is not None
    assert stored_event.source_ids == (document.id,)
    assert stored_run is not None
    assert stored_run.raw_output == raw
    assert stored_run.validation_status is CandidateStatus.ACCEPTED
    assert stored_run.model == EXTRACTION_MODEL_ID
    assert "latest" not in stored_run.model.lower()
    assert stored_run.input_hash
    assert referenced is not None
    assert referenced.id == document.id
    assert stored_run.token_usage["input_tokens"] == 10
    assert stored_run.token_usage["cache_read_input_tokens"] == 0
    assert stored_run.latency == 0.42
    assert stored_run.created_at == _T0
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 1


def test_proposed_yields_llm_run_and_zero_events(
    migrated_session: Session, engine: Engine
) -> None:
    document = _persist_document(engine)
    raw = json.dumps({"events": [_accepted_event(confidence=0.4)]})
    service = _service(raw)

    with SqlAlchemyUnitOfWork(engine) as uow:
        outcome = service.extract(document, uow)

    assert outcome.verdict is CandidateStatus.PROPOSED
    assert outcome.events == ()
    run_id = outcome.llm_run.id

    with SqlAlchemyUnitOfWork(engine) as uow:
        stored_run = uow.llm_runs.get(run_id)  # type: ignore[arg-type]

    assert stored_run is not None
    assert stored_run.validation_status is CandidateStatus.PROPOSED
    assert stored_run.raw_output == raw
    assert stored_run.validation_errors
    assert stored_run.input_reference_ids == (str(document.id),)
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1


def test_rejected_yields_llm_run_with_verbatim_raw_output_and_zero_events(
    migrated_session: Session, engine: Engine
) -> None:
    document = _persist_document(engine)
    raw = "this is not json {"
    service = _service(raw)

    with SqlAlchemyUnitOfWork(engine) as uow:
        outcome = service.extract(document, uow)

    assert outcome.verdict is CandidateStatus.REJECTED
    assert outcome.events == ()
    run_id = outcome.llm_run.id

    with SqlAlchemyUnitOfWork(engine) as uow:
        stored_run = uow.llm_runs.get(run_id)  # type: ignore[arg-type]

    assert stored_run is not None
    assert stored_run.raw_output == raw
    assert stored_run.parsed_output is None
    assert stored_run.validation_errors
    assert stored_run.validation_status is CandidateStatus.REJECTED
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1


def test_zero_event_accepted_response_writes_llm_run_only(
    migrated_session: Session, engine: Engine
) -> None:
    document = _persist_document(engine)
    raw = json.dumps({"events": []})
    service = _service(raw)

    with SqlAlchemyUnitOfWork(engine) as uow:
        outcome = service.extract(document, uow)

    assert outcome.verdict is CandidateStatus.ACCEPTED
    assert outcome.events == ()
    assert outcome.llm_run.validation_status is CandidateStatus.ACCEPTED
    assert outcome.llm_run.validation_errors == ()
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1


def test_failure_between_writes_leaves_neither_row(
    migrated_session: Session, engine: Engine
) -> None:
    document = _persist_document(engine)
    service = _service(_FIXTURE.read_text(encoding="utf-8"))

    with (
        pytest.raises(RuntimeError, match="injected failure between writes"),
        SqlAlchemyUnitOfWork(engine) as uow,
    ):
        service.extract(document, _FailOnSecondWrite(uow))  # type: ignore[arg-type]

    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 0
    assert _count(migrated_session, "documents") == 1
