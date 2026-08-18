"""SQLAlchemy implementation of
:class:`~moj_projekt.domain.repositories.LLMRunRepository`.

Append-only (ADR-0007): this class exposes no update or delete method, and
the ``llm_runs_append_only_trigger`` from the migration rejects any UPDATE
or DELETE attempted through a raw SQL statement as well - defense in depth
matching the pattern established for Document/EvidencePack immutability
(S001-T006, S001-T007).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from moj_projekt.domain.enums import CandidateStatus
from moj_projekt.domain.llm_run import LLMRun
from moj_projekt.persistence.models import LLMRunModel

__all__ = ["SqlAlchemyLLMRunRepository"]


def _to_domain(row: LLMRunModel) -> LLMRun:
    return LLMRun(
        id=row.id,
        task_type=row.task_type,
        provider=row.provider,
        model=row.model,
        model_version=row.model_version,
        prompt_version=row.prompt_version,
        system_prompt_version=row.system_prompt_version,
        input_hash=row.input_hash,
        input_reference_ids=tuple(row.input_reference_ids),
        output_schema_version=row.output_schema_version,
        raw_output=row.raw_output,
        parsed_output=dict(row.parsed_output) if row.parsed_output is not None else None,
        validation_status=CandidateStatus(row.validation_status),
        validation_errors=tuple(row.validation_errors),
        temperature=row.temperature,
        inference_parameters=dict(row.inference_parameters),
        token_usage=dict(row.token_usage),
        latency=row.latency,
        created_at=row.created_at,
    )


class SqlAlchemyLLMRunRepository:
    """Persists LLMRuns. No update or delete path - the record is
    append-only (ADR-0007).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, llm_run: LLMRun) -> LLMRun:
        row = LLMRunModel(
            task_type=llm_run.task_type,
            provider=llm_run.provider,
            model=llm_run.model,
            model_version=llm_run.model_version,
            prompt_version=llm_run.prompt_version,
            system_prompt_version=llm_run.system_prompt_version,
            input_hash=llm_run.input_hash,
            input_reference_ids=list(llm_run.input_reference_ids),
            output_schema_version=llm_run.output_schema_version,
            raw_output=llm_run.raw_output,
            parsed_output=dict(llm_run.parsed_output)
            if llm_run.parsed_output is not None
            else None,
            validation_status=llm_run.validation_status.value,
            validation_errors=list(llm_run.validation_errors),
            temperature=llm_run.temperature,
            inference_parameters=dict(llm_run.inference_parameters),
            token_usage=dict(llm_run.token_usage),
            latency=llm_run.latency,
            created_at=llm_run.created_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_domain(row)

    def get(self, llm_run_id: UUID) -> LLMRun | None:
        row = self._session.get(LLMRunModel, llm_run_id)
        return _to_domain(row) if row is not None else None
