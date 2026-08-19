"""Ingest stage: fetch each active Source through its adapter and persist
Documents (S001-T012).

Per-source failure isolation lives here, not in :func:`run_cycle`: a
:class:`~moj_projekt.ingestion.adapter.SourceFetchError` (timeout, HTTP
error, malformed feed) is recorded on ``CycleRun.source_outcomes`` and the
stage continues. The cycle as a whole still ``SUCCEEDED`` unless this
stage itself raises (orchestration/persistence failure). Adapters return
an in-memory sequence before any row is written, so a fetch failure
leaves zero Documents for that source.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from moj_projekt.cycle.stages import DEFAULT_STAGES, Stage
from moj_projekt.domain.cycle_run import CycleRun, StageOutcome
from moj_projekt.domain.repositories import DocumentRepository, SourceRepository
from moj_projekt.ingestion.adapter import SourceAdapter, SourceFetchError

__all__ = ["build_production_stages", "make_ingest_stage"]


def make_ingest_stage(
    *,
    source_repository: SourceRepository,
    document_repository: DocumentRepository,
    adapters: Mapping[str, SourceAdapter],
) -> Stage:
    """Build the ingest ``Stage`` bound to repositories and adapters.

    Sources whose ``source_type`` has no registered adapter are skipped
    (Tier 1 official sources have no adapter this sprint). A later adapter
    is registered in the same map; this loop does not change.
    """

    def run(cycle_run: CycleRun) -> CycleRun:
        for source in source_repository.list_active():
            adapter = adapters.get(source.source_type)
            if adapter is None:
                continue
            try:
                documents = adapter.fetch_documents(source)
            except SourceFetchError as exc:
                cycle_run = cycle_run.with_source_outcome(
                    source.key,
                    StageOutcome(succeeded=False, failure_reason=str(exc)),
                )
                continue
            for document in documents:
                document_repository.add(document)
            cycle_run = cycle_run.with_source_outcome(
                source.key, StageOutcome(succeeded=True)
            )
        return cycle_run

    return Stage("ingest", run)


def build_production_stages(
    *,
    source_repository: SourceRepository,
    document_repository: DocumentRepository,
    adapters: Mapping[str, SourceAdapter],
) -> Sequence[Stage]:
    """The six ordered stages with real ingest and the rest still passthrough."""
    ingest = make_ingest_stage(
        source_repository=source_repository,
        document_repository=document_repository,
        adapters=adapters,
    )
    return tuple(
        ingest if stage.name == "ingest" else stage for stage in DEFAULT_STAGES
    )
