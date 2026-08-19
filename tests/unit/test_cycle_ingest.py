"""Unit tests for ingest-stage isolation and CycleRun source_outcomes
(S001-T012) - no database, no network.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest

from moj_projekt.cycle.ingest import make_ingest_stage
from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus, StageOutcome
from moj_projekt.domain.document import Document
from moj_projekt.domain.enums import SourceTier
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.domain.source import Source
from moj_projekt.ingestion.adapter import SourceFetchError

_T0 = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)


class _FakeClock:
    def __init__(self, times: Sequence[datetime]) -> None:
        self._times: Iterator[datetime] = iter(times)

    def now(self) -> datetime:
        return next(self._times)


class _FakeCycleRunRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, CycleRun] = {}

    def add(self, cycle_run: CycleRun) -> CycleRun:
        stored = replace(cycle_run, id=uuid4())
        self._rows[stored.id] = stored  # type: ignore[index]
        return stored

    def update(self, cycle_run: CycleRun) -> CycleRun:
        self._rows[cycle_run.id] = cycle_run  # type: ignore[index]
        return cycle_run

    def get(self, cycle_run_id: UUID) -> CycleRun | None:
        return self._rows.get(cycle_run_id)

    def get_running(self) -> CycleRun | None:
        for row in self._rows.values():
            if row.status is CycleRunStatus.RUNNING:
                return row
        return None


class _FakeSourceRepository:
    def __init__(self, sources: Sequence[Source]) -> None:
        self._sources = list(sources)

    def add(self, source: Source) -> Source:
        self._sources.append(source)
        return source

    def get(self, key: str) -> Source | None:
        return next((source for source in self._sources if source.key == key), None)

    def list_active(self) -> list[Source]:
        return [source for source in self._sources if source.active]


class _FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: list[Document] = []

    def add(self, document: Document) -> Document:
        for existing in self.documents:
            if existing.dedupe_key == document.dedupe_key:
                return existing
        stored = replace(document, id=uuid4())
        self.documents.append(stored)
        return stored

    def get(self, document_id: UUID) -> Document | None:
        return next((doc for doc in self.documents if doc.id == document_id), None)


class _FakeUnitOfWork:
    def __init__(
        self,
        *,
        cycle_runs: _FakeCycleRunRepository,
        sources: _FakeSourceRepository,
        documents: _FakeDocumentRepository,
    ) -> None:
        self.cycle_runs = cycle_runs
        self.sources = sources
        self.documents = documents

    def __enter__(self) -> _FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None


class _StaticAdapter:
    def __init__(self, documents: Sequence[Document]) -> None:
        self._documents = list(documents)
        self.calls: list[str] = []

    def fetch_documents(self, source: Source) -> list[Document]:
        self.calls.append(source.key)
        return list(self._documents)


class _FailingAdapter:
    def __init__(self, exc: SourceFetchError) -> None:
        self._exc = exc

    def fetch_documents(self, source: Source) -> list[Document]:
        raise self._exc


def _rss_source(key: str = "bloomberg_markets") -> Source:
    return Source(
        key=key,
        name=key,
        source_type="rss",
        tier=SourceTier.PROFESSIONAL,
        publisher=key,
        endpoint_config={"feed_url": "https://example.com/feed.xml"},
    )


def _document(source_key: str = "bloomberg_markets") -> Document:
    return Document(
        source_key=source_key,
        source_type="rss",
        url="https://example.com/markets/article-rate-hold",
        source_native_id="fixture-guid-rate-hold",
        published_at=_PUBLISHED,
        collected_at=_T0,
        title="Central bank holds policy rate",
        content="The central bank left its policy rate unchanged.",
    )


def _ok(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
    del uow
    return cycle_run


def _run_ingest(
    *,
    sources: Sequence[Source],
    adapters: dict[str, _StaticAdapter | _FailingAdapter],
    documents: _FakeDocumentRepository | None = None,
) -> tuple[CycleRun, _FakeDocumentRepository]:
    document_repository = documents if documents is not None else _FakeDocumentRepository()
    cycle_runs = _FakeCycleRunRepository()
    source_repository = _FakeSourceRepository(sources)

    def factory() -> UnitOfWork:
        return cast(
            UnitOfWork,
            _FakeUnitOfWork(
                cycle_runs=cycle_runs,
                sources=source_repository,
                documents=document_repository,
            ),
        )

    ingest = make_ingest_stage(adapters=adapters)
    clock = _FakeClock([_T0, _T0 + timedelta(seconds=1)])
    result = run_cycle(
        clock=clock,
        unit_of_work=factory,
        stages=[ingest, Stage("extract", _ok)],
    )
    assert result is not None
    return result, document_repository


def test_successful_ingest_records_source_ok_and_persists_documents() -> None:
    adapter = _StaticAdapter([_document()])
    result, repo = _run_ingest(sources=[_rss_source()], adapters={"rss": adapter})

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.source_outcomes == {
        "bloomberg_markets": StageOutcome(succeeded=True),
    }
    assert len(repo.documents) == 1
    stored = repo.documents[0]
    assert stored.url == "https://example.com/markets/article-rate-hold"
    assert stored.title == "Central bank holds policy rate"
    assert stored.content
    assert stored.published_at == _PUBLISHED
    assert stored.collected_at == _T0
    assert stored.source_key == "bloomberg_markets"


@pytest.mark.parametrize(
    "failure",
    [
        SourceFetchError("timeout fetching bloomberg_markets"),
        SourceFetchError("HTTP 503 fetching bloomberg_markets"),
        SourceFetchError("malformed feed for bloomberg_markets"),
    ],
)
def test_fetch_failure_leaves_cycle_succeeded_source_failed_and_no_documents(
    failure: SourceFetchError,
) -> None:
    result, repo = _run_ingest(
        sources=[_rss_source()],
        adapters={"rss": _FailingAdapter(failure)},
    )

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.stage_outcomes["ingest"].succeeded is True
    outcome = result.source_outcomes["bloomberg_markets"]
    assert outcome.succeeded is False
    assert outcome.failure_reason == str(failure)
    assert repo.documents == []


def test_one_failing_source_does_not_block_another() -> None:
    ok_source = _rss_source("bloomberg_markets")
    failing_source = _rss_source("ap_news")
    adapter = _StaticAdapter([_document()])

    class _MixedAdapter:
        def fetch_documents(self, source: Source) -> list[Document]:
            if source.key == "ap_news":
                raise SourceFetchError("HTTP 404 fetching ap_news")
            return adapter.fetch_documents(source)

    result, repo = _run_ingest(
        sources=[failing_source, ok_source],
        adapters={"rss": _MixedAdapter()},
    )

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.source_outcomes["ap_news"].succeeded is False
    assert result.source_outcomes["bloomberg_markets"].succeeded is True
    assert len(repo.documents) == 1


def test_immediate_re_run_creates_zero_new_documents() -> None:
    adapter = _StaticAdapter([_document()])
    document_repository = _FakeDocumentRepository()
    sources = [_rss_source()]
    adapters: dict[str, _StaticAdapter | _FailingAdapter] = {"rss": adapter}

    first, _ = _run_ingest(
        sources=sources, adapters=adapters, documents=document_repository
    )
    second, repo = _run_ingest(
        sources=sources, adapters=adapters, documents=document_repository
    )

    assert first.status is CycleRunStatus.SUCCEEDED
    assert second.status is CycleRunStatus.SUCCEEDED
    assert len(repo.documents) == 1


def test_sources_without_an_adapter_are_skipped() -> None:
    fed = Source(
        key="fed_fomc",
        name="Federal Reserve / FOMC",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="Federal Reserve",
        endpoint_config={"base_url": "https://www.federalreserve.gov"},
    )
    result, repo = _run_ingest(sources=[fed], adapters={"rss": _StaticAdapter([])})

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.source_outcomes == {}
    assert repo.documents == []


def test_second_adapter_is_invoked_when_registered_against_source_type() -> None:
    fed = Source(
        key="fed_fomc",
        name="Federal Reserve / FOMC",
        source_type="official_api",
        tier=SourceTier.PRIMARY,
        publisher="Federal Reserve",
    )
    official = _StaticAdapter(
        [
            Document(
                source_key="fed_fomc",
                source_type="official_api",
                url="https://www.federalreserve.gov/item",
                published_at=_PUBLISHED,
                collected_at=_T0,
                title="FOMC statement",
                content="The Committee decided to hold the rate.",
            )
        ]
    )
    result, repo = _run_ingest(
        sources=[fed],
        adapters={"official_api": official},
    )

    assert official.calls == ["fed_fomc"]
    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.source_outcomes["fed_fomc"].succeeded is True
    assert len(repo.documents) == 1
