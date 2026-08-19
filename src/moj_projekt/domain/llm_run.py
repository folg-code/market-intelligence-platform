"""``LLMRun`` - the append-only audit record of one material model
invocation (DOMAIN_MODEL.md section 3, "Governance & Audit";
ARCHITECTURE_FOUNDATIONS.md section 7; ADR-0007, ADR-0010).

Pure domain representation: no persistence concern, no infrastructure
import. Nothing in this sprint's scope writes a real LLMRun (S001 excludes
any LLM call) - this type exists so the append-only record has a stable
shape to write into starting Sprint 002/003 (Phase 3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from moj_projekt.domain.enums import CandidateStatus

__all__ = ["FLOATING_MODEL_ALIASES", "LLMRun", "reject_floating_model_alias"]

FLOATING_MODEL_ALIASES: frozenset[str] = frozenset({"latest"})


def reject_floating_model_alias(value: str, *, field_name: str) -> None:
    """Reject a floating model alias such as ``latest`` (ADR-0010).

    Shared by :class:`LLMRun` and the ``llm/`` rate table so a dated pin is
    checked by one rule, not two copies.
    """
    if value.strip().lower() in FLOATING_MODEL_ALIASES:
        raise ValueError(
            f"{field_name} must be a pinned model identifier, never a "
            "floating alias such as 'latest' (ADR-0010)"
        )


@dataclass(frozen=True, slots=True)
class LLMRun:
    """The reproducibility record of one material LLM invocation.

    ``input_hash`` alone is never sufficient for reproducibility -
    ``input_reference_ids`` (or a snapshot) must also be present (ADR-0007),
    so both are mandatory here. ``model`` and ``model_version`` must be
    pinned identifiers, never a floating "latest" alias (ADR-0010,
    root ``CLAUDE.md``).
    """

    task_type: str
    provider: str
    model: str
    model_version: str
    prompt_version: str
    system_prompt_version: str
    input_hash: str
    input_reference_ids: Sequence[str]
    output_schema_version: str
    raw_output: str
    validation_status: CandidateStatus
    created_at: datetime
    parsed_output: Mapping[str, Any] | None = None
    validation_errors: Sequence[str] = field(default_factory=tuple)
    temperature: float = 0.0
    inference_parameters: Mapping[str, Any] = field(default_factory=dict)
    token_usage: Mapping[str, Any] = field(default_factory=dict)
    latency: float = 0.0
    id: UUID | None = None

    def __post_init__(self) -> None:
        for attr_name in (
            "task_type",
            "provider",
            "model",
            "model_version",
            "prompt_version",
            "system_prompt_version",
            "input_hash",
            "output_schema_version",
        ):
            value = getattr(self, attr_name)
            if not value.strip():
                raise ValueError(f"LLMRun.{attr_name} must not be empty")
        if len(self.input_reference_ids) == 0:
            raise ValueError(
                "LLMRun.input_reference_ids must not be empty - input_hash "
                "alone is not sufficient for reproducibility (ADR-0007)"
            )
        reject_floating_model_alias(self.model, field_name="LLMRun.model")
        reject_floating_model_alias(self.model_version, field_name="LLMRun.model_version")
        if self.temperature < 0.0:
            raise ValueError("LLMRun.temperature must not be negative")
        if self.latency < 0.0:
            raise ValueError("LLMRun.latency must not be negative")
