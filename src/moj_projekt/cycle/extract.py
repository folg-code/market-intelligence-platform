"""Extract stage: turn COLLECTED Documents into Events (S002-T009).

Work queue is Documents at ``processing_status = COLLECTED``, oldest
``collected_at`` first, bounded by a configured per-cycle cap. A cycle
with an empty queue issues no LLM calls (ADR-0015 clause 2).

Per-document isolation mirrors ingest: an exception from
:class:`~moj_projekt.extraction.service.ExtractionService` (timeout, 5xx,
rate limit, or any other transport-shaped raise) is recorded on
``CycleRun.source_outcomes`` keyed by document id and the Document stays
``COLLECTED``. A terminal verdict (``accepted`` / ``proposed`` /
``rejected``) advances the Document to ``EVENTS_EXTRACTED`` and is never
retried automatically (D-S002-04 clauses 3-5).

Writes go through the unit of work :func:`run_cycle` opens around this
stage - this module does not commit.
"""

from __future__ import annotations

from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.cycle_run import CycleRun, StageOutcome
from moj_projekt.domain.document import ProcessingStatus
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.extraction.service import ExtractionService

__all__ = ["make_extract_stage"]


def make_extract_stage(
    *,
    service: ExtractionService,
    document_cap: int,
) -> Stage:
    """Build the extract ``Stage`` bound to ``service`` and ``document_cap``.

    ``document_cap`` must be >= 1: a misconfigured cap is a stage-level
    construction error, not a silent empty queue. Repositories come from
    the unit of work the cycle opens around this stage.
    """
    if document_cap < 1:
        raise ValueError("extract document_cap must be >= 1")

    def run(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
        documents = uow.documents.list_by_processing_status(
            ProcessingStatus.COLLECTED, limit=document_cap
        )
        for document in documents:
            if document.id is None:
                raise RuntimeError(
                    "extract stage received a Document without an id; "
                    "list_by_processing_status must return persisted rows"
                )
            try:
                service.extract(document, uow)
            except Exception as exc:  # a failing document must not fail the cycle
                cycle_run = cycle_run.with_document_outcome(
                    document.id,
                    StageOutcome(
                        succeeded=False,
                        failure_reason=f"{type(exc).__name__}: {exc}",
                    ),
                )
                continue
            uow.documents.advance_processing_status(
                document.id, ProcessingStatus.EVENTS_EXTRACTED
            )
        return cycle_run

    return Stage("extract", run)
