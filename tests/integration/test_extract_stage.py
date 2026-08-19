"""Live-database tests for the cycle extract stage (S002-T009).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.cycle.extract import make_extract_stage
from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.cycle.run_once import run_once
from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.budget import BudgetPolicy
from moj_projekt.domain.clock import Clock
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus
from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.domain.enums import CandidateStatus, SourceTier
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.domain.source import Source
from moj_projekt.extraction.service import ExtractionService
from moj_projekt.extraction.types import DEFAULT_VALIDATION_CONFIG
from moj_projekt.llm.client import InferenceParams, LLMResponse, TokenUsage
from moj_projekt.llm.fake import FakeLLMClient
from moj_projekt.persistence.document_repository import SqlAlchemyDocumentRepository
from moj_projekt.persistence.unit_of_work import (
    SqlAlchemyUnitOfWork,
    sqlalchemy_unit_of_work_factory,
)

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "llm" / "extraction_response_v1.json"
_T0 = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 17, 18, 0, tzinfo=UTC)
_POLICY = BudgetPolicy(ceiling_usd=Decimal("10"), soft_threshold_ratio=Decimal("0.80"))
_ZERO_USAGE = TokenUsage(
    input_tokens=0,
    output_tokens=0,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=0,
)


class _FixedClock:
    def now(self) -> datetime:
        return _T0


class _ScriptedLLMClient:
    def __init__(self, actions: Sequence[bytes | BaseException]) -> None:
        self._actions = list(actions)
        self.call_count = 0

    def complete(self, rendered_prompt: str, params: InferenceParams) -> LLMResponse:
        del rendered_prompt, params
        self.call_count += 1
        action = self._actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return LLMResponse(
            raw_output=action.decode("utf-8"),
            token_usage=_ZERO_USAGE,
            latency_seconds=0.0,
        )


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


def _document(*, suffix: str, collected_at: datetime = _T0) -> Document:
    return Document(
        source_key="bloomberg_markets",
        source_type="rss",
        url=f"https://example.com/article-{suffix}",
        source_native_id=f"guid-{suffix}",
        published_at=_PUBLISHED,
        collected_at=collected_at,
        title=f"Article {suffix}",
        content="The Federal Reserve left the policy rate unchanged.",
    )


def _persist_documents(engine: Engine, documents: Sequence[Document]) -> list[Document]:
    stored: list[Document] = []
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(_source())
        for document in documents:
            stored.append(uow.documents.add(document))
    return stored


def _ok(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
    del uow
    return cycle_run


def _run_extract_cycle(
    engine: Engine,
    *,
    client: FakeLLMClient | _ScriptedLLMClient,
    document_cap: int,
    clock: Clock | None = None,
) -> CycleRun:
    used_clock: Clock = _FixedClock() if clock is None else clock
    service = ExtractionService(
        client=client,
        clock=used_clock,
        validation_config=DEFAULT_VALIDATION_CONFIG,
    )
    extract = make_extract_stage(service=service, document_cap=document_cap, budget_policy=_POLICY)
    result = run_cycle(
        clock=used_clock,
        unit_of_work=sqlalchemy_unit_of_work_factory(engine),
        stages=[Stage("ingest", _ok), extract],
    )
    assert result is not None
    return result


def test_populated_queue_writes_events_and_llm_runs_and_advances_exactly_those_documents(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="1"), _document(suffix="2")])
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 2
    assert _count(migrated_session, "events") == 2
    assert _count(migrated_session, "llm_runs") == 2
    with SqlAlchemyUnitOfWork(engine) as uow:
        for document in stored:
            fetched = uow.documents.get(cast(UUID, document.id))
            assert fetched is not None
            assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED
            run_id = migrated_session.execute(
                text("SELECT id FROM llm_runs WHERE input_reference_ids->>0 = :doc_id"),
                {"doc_id": str(document.id)},
            ).scalar_one()
            assert run_id is not None


def test_empty_work_queue_calls_the_client_zero_times(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(_source())
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 0
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 0


def test_re_run_extracts_nothing_and_makes_no_further_calls(
    migrated_session: Session, engine: Engine
) -> None:
    _persist_documents(engine, [_document(suffix="1")])
    client = FakeLLMClient(_FIXTURE.read_bytes())

    first = _run_extract_cycle(engine, client=client, document_cap=20)
    second = _run_extract_cycle(engine, client=client, document_cap=20)

    assert first.status is CycleRunStatus.SUCCEEDED
    assert second.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 1


def test_per_cycle_cap_leaves_the_rest_for_the_next_cycle(
    migrated_session: Session, engine: Engine
) -> None:
    oldest = _document(suffix="oldest", collected_at=_T0 - timedelta(hours=2))
    middle = _document(suffix="middle", collected_at=_T0 - timedelta(hours=1))
    newest = _document(suffix="newest", collected_at=_T0)
    stored = _persist_documents(engine, [newest, oldest, middle])
    by_native = {document.source_native_id: document for document in stored}
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = _run_extract_cycle(engine, client=client, document_cap=2)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 2
    assert _count(migrated_session, "llm_runs") == 2
    with SqlAlchemyUnitOfWork(engine) as uow:
        oldest_row = uow.documents.get(cast(UUID, by_native["guid-oldest"].id))
        middle_row = uow.documents.get(cast(UUID, by_native["guid-middle"].id))
        newest_row = uow.documents.get(cast(UUID, by_native["guid-newest"].id))
    assert oldest_row is not None
    assert middle_row is not None
    assert newest_row is not None
    assert oldest_row.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert middle_row.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert newest_row.processing_status is ProcessingStatus.COLLECTED


def test_raising_extraction_is_isolated_per_document(
    migrated_session: Session, engine: Engine
) -> None:
    failing = _document(suffix="fail", collected_at=_T0 - timedelta(minutes=1))
    ok = _document(suffix="ok", collected_at=_T0)
    stored = _persist_documents(engine, [failing, ok])
    by_native = {document.source_native_id: document for document in stored}
    client = _ScriptedLLMClient(
        [TimeoutError("timed out calling the model"), _FIXTURE.read_bytes()]
    )

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.stage_outcomes["extract"].succeeded is True
    assert client.call_count == 2
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 1
    failing_id = cast(UUID, by_native["guid-fail"].id)
    ok_id = cast(UUID, by_native["guid-ok"].id)
    assert result.source_outcomes[str(failing_id)].succeeded is False
    assert "TimeoutError" in (result.source_outcomes[str(failing_id)].failure_reason or "")
    with SqlAlchemyUnitOfWork(engine) as uow:
        failing_row = uow.documents.get(failing_id)
        ok_row = uow.documents.get(ok_id)
    assert failing_row is not None
    assert ok_row is not None
    assert failing_row.processing_status is ProcessingStatus.COLLECTED
    assert ok_row.processing_status is ProcessingStatus.EVENTS_EXTRACTED


def _proposed_response() -> bytes:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    payload["events"][0]["confidence"] = 0.4
    return json.dumps(payload).encode("utf-8")


def _stored_validation_status(session: Session, document_id: UUID) -> str:
    return str(
        session.execute(
            text("SELECT validation_status FROM llm_runs WHERE input_reference_ids->>0 = :doc_id"),
            {"doc_id": str(document_id)},
        ).scalar_one()
    )


def test_rejected_verdict_advances_without_an_event(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="reject")])
    client = FakeLLMClient(b"this is not json {")

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1
    document_id = cast(UUID, stored[0].id)
    assert _stored_validation_status(migrated_session, document_id) == CandidateStatus.REJECTED
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(document_id)
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


def test_proposed_verdict_advances_without_an_event(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="propose")])
    client = FakeLLMClient(_proposed_response())

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1
    document_id = cast(UUID, stored[0].id)
    assert _stored_validation_status(migrated_session, document_id) == CandidateStatus.PROPOSED
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(document_id)
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


def test_zero_event_accepted_advances_without_an_event(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="empty")])
    client = FakeLLMClient(b'{"events": []}')

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1
    document_id = cast(UUID, stored[0].id)
    assert _stored_validation_status(migrated_session, document_id) == CandidateStatus.ACCEPTED
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(document_id)
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out calling the model"),
        RuntimeError("HTTP 503 from provider"),
        RuntimeError("rate limit exceeded"),
    ],
)
def test_transport_failure_leaves_document_collected(
    migrated_session: Session, engine: Engine, failure: BaseException
) -> None:
    stored = _persist_documents(engine, [_document(suffix="transport")])
    client = _ScriptedLLMClient([failure])

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.stage_outcomes["extract"].succeeded is True
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 0
    document_id = cast(UUID, stored[0].id)
    assert result.source_outcomes[str(document_id)].succeeded is False
    assert type(failure).__name__ in (result.source_outcomes[str(document_id)].failure_reason or "")
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(document_id)
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.COLLECTED


def test_stage_level_failure_yields_exactly_one_terminal_cycle_run(
    migrated_session: Session, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored = _persist_documents(engine, [_document(suffix="queued")])
    client = FakeLLMClient(_FIXTURE.read_bytes())

    def _boom(
        self: SqlAlchemyDocumentRepository, status: ProcessingStatus, *, limit: int
    ) -> list[Document]:
        del self, status, limit
        raise RuntimeError("repository unavailable")

    monkeypatch.setattr(SqlAlchemyDocumentRepository, "list_by_processing_status", _boom)

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.FAILED
    assert result.status.is_terminal is True
    assert result.failure_reason is not None
    assert "extract" in result.failure_reason
    assert _count(migrated_session, "cycle_runs") == 1
    assert client.call_count == 0
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 0
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(cast(UUID, stored[0].id))
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.COLLECTED


def test_processing_status_does_not_regress_after_extract(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="1")])
    client = FakeLLMClient(_FIXTURE.read_bytes())
    document_id = cast(UUID, stored[0].id)

    result = _run_extract_cycle(engine, client=client, document_cap=20)

    assert result.status is CycleRunStatus.SUCCEEDED
    with pytest.raises(ValueError, match="cannot regress"), SqlAlchemyUnitOfWork(engine) as uow:
        uow.documents.advance_processing_status(document_id, ProcessingStatus.COLLECTED)
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(document_id)
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_run_once_extracts_through_production_stages(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="wired")])
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = run_once(
        engine,
        clock=_FixedClock(),
        adapters={},
        llm_client=client,
        extract_document_cap=20,
    )

    assert result is not None
    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 1
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(cast(UUID, stored[0].id))
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED
