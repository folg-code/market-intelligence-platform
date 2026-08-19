"""Live-database tests for the monthly LLM budget guard (S002-T010).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration
"""

from __future__ import annotations

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
from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.budget import (
    BUDGET_APPROACHING_KEY,
    BUDGET_CEILING_KEY,
    CEILING_REACHED_REASON,
    BudgetPolicy,
)
from moj_projekt.domain.clock import Clock
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus
from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.domain.enums import CandidateStatus, SourceTier
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.domain.source import Source
from moj_projekt.extraction.service import ExtractionService
from moj_projekt.extraction.types import DEFAULT_VALIDATION_CONFIG
from moj_projekt.llm.client import TokenUsage
from moj_projekt.llm.fake import FakeLLMClient
from moj_projekt.llm.models import EVENT_EXTRACTION_TASK_TYPE, model_spec_for
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
_SEPTEMBER = datetime(2026, 9, 1, tzinfo=UTC)


class _FixedClock:
    def __init__(self, at: datetime = _T0) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at


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


def _priced_run(
    *,
    input_tokens: int,
    created_at: datetime = _T0,
) -> LLMRun:
    spec = model_spec_for(EVENT_EXTRACTION_TASK_TYPE)
    return LLMRun(
        task_type=EVENT_EXTRACTION_TASK_TYPE,
        provider="anthropic",
        model=spec.model_id,
        model_version=spec.model_version,
        prompt_version="v1",
        system_prompt_version="v1",
        input_hash="abc123",
        input_reference_ids=("document:prior",),
        output_schema_version="v1",
        raw_output="{}",
        validation_status=CandidateStatus.ACCEPTED,
        created_at=created_at,
        token_usage={
            "input_tokens": input_tokens,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    )


def _persist_documents(engine: Engine, documents: Sequence[Document]) -> list[Document]:
    stored: list[Document] = []
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.sources.add(_source())
        for document in documents:
            stored.append(uow.documents.add(document))
    return stored


def _persist_run(engine: Engine, run: LLMRun) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.llm_runs.add(run)


def _ok(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
    del uow
    return cycle_run


def _run_extract_cycle(
    engine: Engine,
    *,
    client: FakeLLMClient,
    document_cap: int = 20,
    clock: Clock | None = None,
    budget_policy: BudgetPolicy = _POLICY,
) -> CycleRun:
    used_clock: Clock = _FixedClock() if clock is None else clock
    service = ExtractionService(
        client=client,
        clock=used_clock,
        validation_config=DEFAULT_VALIDATION_CONFIG,
    )
    extract = make_extract_stage(
        service=service, document_cap=document_cap, budget_policy=budget_policy
    )
    result = run_cycle(
        clock=used_clock,
        unit_of_work=sqlalchemy_unit_of_work_factory(engine),
        stages=[Stage("ingest", _ok), extract],
    )
    assert result is not None
    return result


def _reload_cycle_run(engine: Engine, cycle_run_id: UUID) -> CycleRun:
    with SqlAlchemyUnitOfWork(engine) as uow:
        persisted = uow.cycle_runs.get(cycle_run_id)
    assert persisted is not None
    return persisted


def test_recorded_spend_at_ceiling_makes_zero_calls_and_cycle_succeeds(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="queued")])
    _persist_run(engine, _priced_run(input_tokens=10_000_000))
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = _run_extract_cycle(engine, client=client)
    persisted = _reload_cycle_run(engine, cast(UUID, result.id))

    assert result.status is CycleRunStatus.SUCCEEDED
    assert persisted.status is CycleRunStatus.SUCCEEDED
    assert persisted.failure_reason is None
    assert client.call_count == 0
    assert _count(migrated_session, "events") == 0
    assert _count(migrated_session, "llm_runs") == 1
    assert persisted.source_outcomes[BUDGET_CEILING_KEY].succeeded is False
    assert persisted.source_outcomes[BUDGET_CEILING_KEY].failure_reason == (CEILING_REACHED_REASON)
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(cast(UUID, stored[0].id))
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.COLLECTED


def test_soft_threshold_is_recorded_without_stopping_extraction(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="1")])
    _persist_run(engine, _priced_run(input_tokens=8_000_000))
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = _run_extract_cycle(engine, client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 2
    assert result.source_outcomes[BUDGET_APPROACHING_KEY].succeeded is True
    assert BUDGET_CEILING_KEY not in result.source_outcomes
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(cast(UUID, stored[0].id))
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_skipped_documents_resume_when_the_budget_period_rolls_over(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(engine, [_document(suffix="queued")])
    _persist_run(engine, _priced_run(input_tokens=10_000_000, created_at=_T0))
    client = FakeLLMClient(_FIXTURE.read_bytes())

    blocked = _run_extract_cycle(engine, client=client, clock=_FixedClock(_T0))
    resumed = _run_extract_cycle(engine, client=client, clock=_FixedClock(_SEPTEMBER))

    assert blocked.status is CycleRunStatus.SUCCEEDED
    assert blocked.source_outcomes[BUDGET_CEILING_KEY].succeeded is False
    assert resumed.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 2
    assert BUDGET_CEILING_KEY not in resumed.source_outcomes
    with SqlAlchemyUnitOfWork(engine) as uow:
        fetched = uow.documents.get(cast(UUID, stored[0].id))
    assert fetched is not None
    assert fetched.processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_in_cycle_spend_stops_later_documents_before_the_next_call(
    migrated_session: Session, engine: Engine
) -> None:
    """Guard is consulted before each call; flushed in-cycle LLMRun rows count."""
    first = _document(suffix="first", collected_at=_T0 - timedelta(minutes=1))
    second = _document(suffix="second", collected_at=_T0)
    stored = _persist_documents(engine, [first, second])
    client = FakeLLMClient(
        _FIXTURE.read_bytes(),
        token_usage=TokenUsage(
            input_tokens=10_000_000,
            output_tokens=0,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
    )

    result = _run_extract_cycle(engine, client=client)
    persisted = _reload_cycle_run(engine, cast(UUID, result.id))

    assert persisted.status is CycleRunStatus.SUCCEEDED
    assert persisted.failure_reason is None
    assert client.call_count == 1
    assert _count(migrated_session, "events") == 1
    assert _count(migrated_session, "llm_runs") == 1
    assert persisted.source_outcomes[BUDGET_CEILING_KEY].failure_reason == (CEILING_REACHED_REASON)
    with SqlAlchemyUnitOfWork(engine) as uow:
        extracted = uow.documents.get(cast(UUID, stored[0].id))
        queued = uow.documents.get(cast(UUID, stored[1].id))
    assert extracted is not None
    assert queued is not None
    assert extracted.processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert queued.processing_status is ProcessingStatus.COLLECTED


def test_configured_ceiling_and_cap_are_not_hard_coded(
    migrated_session: Session, engine: Engine
) -> None:
    stored = _persist_documents(
        engine,
        [
            _document(suffix="queued-a", collected_at=_T0 - timedelta(minutes=1)),
            _document(suffix="queued-b", collected_at=_T0),
        ],
    )
    # 20_000 input @ $1/M = $0.02, above a $0.01 ceiling.
    _persist_run(engine, _priced_run(input_tokens=20_000))
    tight = BudgetPolicy(ceiling_usd=Decimal("0.01"), soft_threshold_ratio=Decimal("0.50"))
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result = _run_extract_cycle(engine, client=client, document_cap=1, budget_policy=tight)
    persisted = _reload_cycle_run(engine, cast(UUID, result.id))

    assert persisted.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 0
    assert _count(migrated_session, "events") == 0
    assert BUDGET_CEILING_KEY in persisted.source_outcomes
    with SqlAlchemyUnitOfWork(engine) as uow:
        first_doc = uow.documents.get(cast(UUID, stored[0].id))
        second_doc = uow.documents.get(cast(UUID, stored[1].id))
    assert first_doc is not None and second_doc is not None
    assert first_doc.processing_status is ProcessingStatus.COLLECTED
    assert second_doc.processing_status is ProcessingStatus.COLLECTED
