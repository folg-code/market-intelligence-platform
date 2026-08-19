"""Unit tests for extract-stage isolation, cap, and the empty-queue
zero-call invariant (S002-T009) - no database, no network.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from moj_projekt.cycle.extract import make_extract_stage
from moj_projekt.cycle.ingest import build_production_stages
from moj_projekt.cycle.run_cycle import run_cycle
from moj_projekt.cycle.stages import DEFAULT_STAGES, Stage
from moj_projekt.domain.cycle_run import CycleRun, CycleRunStatus, StageOutcome
from moj_projekt.domain.document import Document, ProcessingStatus
from moj_projekt.domain.event import Event
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.extraction.service import ExtractionService
from moj_projekt.extraction.types import DEFAULT_VALIDATION_CONFIG
from moj_projekt.llm.client import InferenceParams, LLMResponse, TokenUsage
from moj_projekt.llm.fake import FakeLLMClient

_T0 = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 17, 18, 0, tzinfo=UTC)
_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / "extraction_response_v1.json"
_ZERO_USAGE = TokenUsage(
    input_tokens=0,
    output_tokens=0,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=0,
)
_EXTRACT_MODULE = (
    Path(__file__).resolve().parents[2] / "src" / "moj_projekt" / "cycle" / "extract.py"
)


class _FakeClock:
    def __init__(self, times: Sequence[datetime]) -> None:
        self._times: Iterator[datetime] = iter(times)

    def now(self) -> datetime:
        return next(self._times)


class _FixedClock:
    def now(self) -> datetime:
        return _T0


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

    def all_rows(self) -> list[CycleRun]:
        return list(self._rows.values())


class _FakeDocumentRepository:
    def __init__(self, documents: Sequence[Document] | None = None) -> None:
        self.documents: list[Document] = list(documents or [])

    def add(self, document: Document) -> Document:
        stored = document if document.id is not None else replace(document, id=uuid4())
        self.documents.append(stored)
        return stored

    def get(self, document_id: UUID) -> Document | None:
        return next((doc for doc in self.documents if doc.id == document_id), None)

    def list_by_processing_status(
        self, status: ProcessingStatus, *, limit: int
    ) -> list[Document]:
        matching = [doc for doc in self.documents if doc.processing_status is status]
        matching.sort(key=lambda doc: (doc.collected_at, doc.id or UUID(int=0)))
        return matching[:limit]

    def advance_processing_status(
        self, document_id: UUID, new_status: ProcessingStatus
    ) -> Document:
        current = self.get(document_id)
        if current is None:
            raise ValueError(f"Document {document_id} does not exist")
        advanced = current.advance_processing_status(new_status)
        self.documents = [
            advanced if doc.id == document_id else doc for doc in self.documents
        ]
        return advanced


class _RecordingRepo:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, item: object) -> object:
        self.items.append(item)
        return item


class _FakeUnitOfWork:
    def __init__(
        self,
        *,
        cycle_runs: _FakeCycleRunRepository,
        documents: _FakeDocumentRepository,
        events: _RecordingRepo,
        llm_runs: _RecordingRepo,
    ) -> None:
        self.cycle_runs = cycle_runs
        self.documents = documents
        self.events = events
        self.llm_runs = llm_runs

    def __enter__(self) -> _FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None


class _ScriptedLLMClient:
    """Replays bytes or raises, in order, and counts ``complete`` calls."""

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


def _document(
    *,
    suffix: str,
    collected_at: datetime = _T0,
    processing_status: ProcessingStatus = ProcessingStatus.COLLECTED,
) -> Document:
    return Document(
        source_key="bloomberg_markets",
        source_type="rss",
        url=f"https://example.com/article-{suffix}",
        source_native_id=f"guid-{suffix}",
        published_at=_PUBLISHED,
        collected_at=collected_at,
        title=f"Article {suffix}",
        content="The central bank left its policy rate unchanged.",
        processing_status=processing_status,
        id=uuid4(),
    )


def _ok(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
    del uow
    return cycle_run


def _service(client: FakeLLMClient | _ScriptedLLMClient) -> ExtractionService:
    return ExtractionService(
        client=client,
        clock=_FixedClock(),
        validation_config=DEFAULT_VALIDATION_CONFIG,
    )


def _run_extract(
    *,
    documents: Sequence[Document],
    client: FakeLLMClient | _ScriptedLLMClient,
    document_cap: int = 20,
    document_repository: _FakeDocumentRepository | None = None,
) -> tuple[CycleRun, _FakeDocumentRepository, _RecordingRepo, _RecordingRepo]:
    repo = (
        document_repository
        if document_repository is not None
        else _FakeDocumentRepository(documents)
    )
    cycle_runs = _FakeCycleRunRepository()
    events = _RecordingRepo()
    llm_runs = _RecordingRepo()

    def factory() -> UnitOfWork:
        return cast(
            UnitOfWork,
            _FakeUnitOfWork(
                cycle_runs=cycle_runs,
                documents=repo,
                events=events,
                llm_runs=llm_runs,
            ),
        )

    extract = make_extract_stage(service=_service(client), document_cap=document_cap)
    clock = _FakeClock([_T0, _T0 + timedelta(seconds=1)])
    result = run_cycle(
        clock=clock,
        unit_of_work=factory,
        stages=[Stage("ingest", _ok), extract],
    )
    assert result is not None
    return result, repo, events, llm_runs


def test_populated_queue_writes_events_and_llm_runs_and_advances_status() -> None:
    document = _document(suffix="1")
    client = FakeLLMClient(_FIXTURE.read_bytes())
    result, repo, events, llm_runs = _run_extract(documents=[document], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert len(events.items) == 1
    assert len(llm_runs.items) == 1
    stored_event = cast(Event, events.items[0])
    stored_run = cast(LLMRun, llm_runs.items[0])
    assert stored_event.source_ids == (document.id,)
    assert stored_run.input_reference_ids == (str(document.id),)
    assert stored_run.created_at == _T0
    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


def test_empty_work_queue_calls_the_client_zero_times() -> None:
    client = FakeLLMClient(_FIXTURE.read_bytes())
    result, repo, events, llm_runs = _run_extract(documents=[], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 0
    assert events.items == []
    assert llm_runs.items == []
    assert repo.documents == []


def test_already_extracted_documents_are_not_retried() -> None:
    done = _document(
        suffix="done", processing_status=ProcessingStatus.EVENTS_EXTRACTED
    )
    client = FakeLLMClient(_FIXTURE.read_bytes())
    result, repo, events, llm_runs = _run_extract(documents=[done], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 0
    assert events.items == []
    assert llm_runs.items == []
    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_immediate_re_run_extracts_nothing_and_makes_no_further_calls() -> None:
    document = _document(suffix="1")
    client = FakeLLMClient(_FIXTURE.read_bytes())
    repo = _FakeDocumentRepository([document])

    first, repo, _, llm_runs_first = _run_extract(
        documents=[document], client=client, document_repository=repo
    )
    second, repo, _, llm_runs_second = _run_extract(
        documents=[], client=client, document_repository=repo
    )

    assert first.status is CycleRunStatus.SUCCEEDED
    assert second.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert len(llm_runs_first.items) == 1
    assert llm_runs_second.items == []
    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED


def test_per_cycle_cap_processes_exactly_the_oldest_documents() -> None:
    oldest = _document(suffix="oldest", collected_at=_T0 - timedelta(hours=2))
    middle = _document(suffix="middle", collected_at=_T0 - timedelta(hours=1))
    newest = _document(suffix="newest", collected_at=_T0)
    client = FakeLLMClient(_FIXTURE.read_bytes())

    result, repo, events, llm_runs = _run_extract(
        documents=[newest, oldest, middle],
        client=client,
        document_cap=2,
    )

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 2
    assert len(events.items) == 2
    assert len(llm_runs.items) == 2
    by_id = {doc.id: doc for doc in repo.documents}
    assert by_id[oldest.id].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert by_id[middle.id].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert by_id[newest.id].processing_status is ProcessingStatus.COLLECTED


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out calling the model"),
        RuntimeError("HTTP 503 from provider"),
        RuntimeError("rate limit exceeded"),
    ],
)
def test_raising_extraction_leaves_document_collected_and_cycle_succeeded(
    failure: BaseException,
) -> None:
    document = _document(suffix="poison")
    client = _ScriptedLLMClient([failure])
    result, repo, events, llm_runs = _run_extract(documents=[document], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert result.stage_outcomes["extract"].succeeded is True
    assert client.call_count == 1
    assert events.items == []
    assert llm_runs.items == []
    assert repo.documents[0].processing_status is ProcessingStatus.COLLECTED
    outcome = result.source_outcomes[str(document.id)]
    assert outcome == StageOutcome(
        succeeded=False, failure_reason=f"{type(failure).__name__}: {failure}"
    )


def test_one_failing_document_does_not_block_another() -> None:
    failing = _document(suffix="fail", collected_at=_T0 - timedelta(minutes=1))
    ok = _document(suffix="ok", collected_at=_T0)
    client = _ScriptedLLMClient(
        [TimeoutError("timed out calling the model"), _FIXTURE.read_bytes()]
    )

    result, repo, events, llm_runs = _run_extract(
        documents=[failing, ok], client=client
    )

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 2
    assert len(events.items) == 1
    assert len(llm_runs.items) == 1
    by_id = {doc.id: doc for doc in repo.documents}
    assert by_id[failing.id].processing_status is ProcessingStatus.COLLECTED
    assert by_id[ok.id].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes[str(failing.id)].succeeded is False
    assert str(ok.id) not in result.source_outcomes


def _proposed_response() -> bytes:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    payload["events"][0]["confidence"] = 0.4
    return json.dumps(payload).encode("utf-8")


def test_rejected_verdict_still_advances_to_events_extracted() -> None:
    document = _document(suffix="reject")
    client = FakeLLMClient(b"this is not json {")
    result, repo, events, llm_runs = _run_extract(documents=[document], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert events.items == []
    assert len(llm_runs.items) == 1
    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


def test_proposed_verdict_still_advances_to_events_extracted() -> None:
    document = _document(suffix="propose")
    client = FakeLLMClient(_proposed_response())
    result, repo, events, llm_runs = _run_extract(documents=[document], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert events.items == []
    assert len(llm_runs.items) == 1
    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


def test_zero_event_accepted_still_advances_to_events_extracted() -> None:
    document = _document(suffix="empty")
    client = FakeLLMClient(b'{"events": []}')
    result, repo, events, llm_runs = _run_extract(documents=[document], client=client)

    assert result.status is CycleRunStatus.SUCCEEDED
    assert client.call_count == 1
    assert events.items == []
    assert len(llm_runs.items) == 1
    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    assert result.source_outcomes == {}


def test_processing_status_never_regresses() -> None:
    document = _document(suffix="1")
    client = FakeLLMClient(_FIXTURE.read_bytes())
    repo = _FakeDocumentRepository([document])
    _run_extract(documents=[document], client=client, document_repository=repo)
    _run_extract(documents=[], client=client, document_repository=repo)

    assert repo.documents[0].processing_status is ProcessingStatus.EVENTS_EXTRACTED
    with pytest.raises(ValueError, match="cannot regress"):
        repo.advance_processing_status(document.id, ProcessingStatus.COLLECTED)  # type: ignore[arg-type]


def test_stage_level_failure_yields_exactly_one_terminal_cycle_run() -> None:
    class _BoomDocuments(_FakeDocumentRepository):
        def list_by_processing_status(
            self, status: ProcessingStatus, *, limit: int
        ) -> list[Document]:
            raise RuntimeError("repository unavailable")

    cycle_runs = _FakeCycleRunRepository()
    documents = _BoomDocuments()
    events = _RecordingRepo()
    llm_runs = _RecordingRepo()

    def factory() -> UnitOfWork:
        return cast(
            UnitOfWork,
            _FakeUnitOfWork(
                cycle_runs=cycle_runs,
                documents=documents,
                events=events,
                llm_runs=llm_runs,
            ),
        )

    client = FakeLLMClient(_FIXTURE.read_bytes())
    extract = make_extract_stage(service=_service(client), document_cap=20)
    result = run_cycle(
        clock=_FakeClock([_T0, _T0 + timedelta(seconds=1)]),
        unit_of_work=factory,
        stages=[Stage("ingest", _ok), extract],
    )

    assert result is not None
    assert result.status is CycleRunStatus.FAILED
    assert result.status.is_terminal is True
    assert result.failure_reason is not None
    assert "extract" in result.failure_reason
    assert len(cycle_runs.all_rows()) == 1
    assert client.call_count == 0


def test_make_extract_stage_rejects_a_non_positive_cap() -> None:
    client = FakeLLMClient(_FIXTURE.read_bytes())
    with pytest.raises(ValueError, match="document_cap"):
        make_extract_stage(service=_service(client), document_cap=0)


def test_extract_stage_does_not_read_the_wall_clock() -> None:
    tree = ast.parse(_EXTRACT_MODULE.read_text(encoding="utf-8"), filename=str(_EXTRACT_MODULE))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in {"now", "utcnow"}:
            continue
        value = func.value
        if isinstance(value, ast.Name) and value.id == "datetime":
            raise AssertionError(
                f"cycle/extract.py calls datetime.{func.attr}() at line {node.lineno}"
            )
        if isinstance(value, ast.Attribute) and value.attr == "datetime":
            raise AssertionError(
                f"cycle/extract.py calls datetime.{func.attr}() at line {node.lineno}"
            )


def test_build_production_stages_replaces_ingest_and_extract() -> None:
    client = FakeLLMClient(_FIXTURE.read_bytes())
    stages = build_production_stages(
        adapters={},
        extraction_service=_service(client),
        extract_document_cap=20,
    )

    assert [stage.name for stage in stages] == [stage.name for stage in DEFAULT_STAGES]
    assert stages[0].run is not DEFAULT_STAGES[0].run
    assert stages[1].run is not DEFAULT_STAGES[1].run
    assert stages[2].run is DEFAULT_STAGES[2].run
