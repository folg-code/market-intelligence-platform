"""Extract stage: turn COLLECTED Documents into Events (S002-T009).

Work queue is Documents at ``processing_status = COLLECTED``, oldest
``collected_at`` first, bounded by a configured per-cycle cap. A cycle
with an empty queue issues no LLM calls (ADR-0015 clause 2).

The monthly budget guard (ADR-0015 clause 4) is consulted **before each
call**. Spend for the UTC calendar month of ``CycleRun.started_at`` is
derived from recorded ``llm_runs.token_usage`` against the rate table.
At or above the ceiling, remaining Documents stay ``COLLECTED`` and the
reason is recorded on the CycleRun; the cycle still succeeds. Between
the soft threshold and the ceiling the approach is recorded and
extraction continues. Below the soft threshold nothing changes.

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

from datetime import datetime
from decimal import Decimal

from moj_projekt.cycle.stages import Stage
from moj_projekt.domain.budget import (
    BUDGET_APPROACHING_KEY,
    BUDGET_CEILING_KEY,
    CEILING_REACHED_REASON,
    BudgetBand,
    BudgetPolicy,
    classify_spend,
    spend_usd,
    utc_month_bounds,
)
from moj_projekt.domain.cycle_run import CycleRun, StageOutcome
from moj_projekt.domain.document import ProcessingStatus
from moj_projekt.domain.repositories import UnitOfWork
from moj_projekt.extraction.service import ExtractionService
from moj_projekt.llm.models import rates_per_million_by_model_id

__all__ = ["make_extract_stage"]


def make_extract_stage(
    *,
    service: ExtractionService,
    document_cap: int,
    budget_policy: BudgetPolicy,
) -> Stage:
    """Build the extract ``Stage`` bound to ``service``, cap, and budget policy.

    ``document_cap`` must be >= 1: a misconfigured cap is a stage-level
    construction error, not a silent empty queue. Ceiling and soft
    threshold come from ``budget_policy`` (configuration, not constants).
    Repositories come from the unit of work the cycle opens around this
    stage. The budget period is the UTC month of ``cycle_run.started_at``.
    """
    if document_cap < 1:
        raise ValueError("extract document_cap must be >= 1")

    def run(cycle_run: CycleRun, uow: UnitOfWork) -> CycleRun:
        documents = uow.documents.list_by_processing_status(
            ProcessingStatus.COLLECTED, limit=document_cap
        )
        approaching_recorded = False
        for document in documents:
            if document.id is None:
                raise RuntimeError(
                    "extract stage received a Document without an id; "
                    "list_by_processing_status must return persisted rows"
                )
            spend = _period_spend(uow, cycle_run.started_at)
            band = classify_spend(spend, budget_policy)
            if band is BudgetBand.AT_CEILING:
                cycle_run = cycle_run.with_source_outcome(
                    BUDGET_CEILING_KEY,
                    StageOutcome(succeeded=False, failure_reason=CEILING_REACHED_REASON),
                )
                break
            if band is BudgetBand.APPROACHING and not approaching_recorded:
                cycle_run = cycle_run.with_source_outcome(
                    BUDGET_APPROACHING_KEY, StageOutcome(succeeded=True)
                )
                approaching_recorded = True
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
            uow.documents.advance_processing_status(document.id, ProcessingStatus.EVENTS_EXTRACTED)
        return cycle_run

    return Stage("extract", run)


def _period_spend(uow: UnitOfWork, started_at: datetime) -> Decimal:
    start, end = utc_month_bounds(started_at)
    return spend_usd(
        uow.llm_runs.list_spend_slices(created_at_from=start, created_at_to=end),
        rates_per_million=rates_per_million_by_model_id(),
    )
