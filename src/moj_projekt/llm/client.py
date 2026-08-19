"""``LLMClient`` protocol: rendered prompt + inference params -> raw response.

No domain type crosses this port (S002-T006). Token usage includes the
cache counters ADR-0015 clause 6 requires, even when both read zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

__all__ = ["InferenceParams", "LLMClient", "LLMResponse", "TokenUsage"]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Provider token counts for one call, including unused cache counters."""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


@dataclass(frozen=True, slots=True)
class InferenceParams:
    """Call-site knobs for one model invocation.

    ``output_schema`` is the provider-side structured-output schema (a
    convenience, not the trust boundary - ADR-0010).
    """

    model: str
    temperature: float
    max_tokens: int
    system_prompt: str
    output_schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Raw model output plus the accounting fields an ``LLMRun`` will store."""

    raw_output: str
    token_usage: TokenUsage
    latency_seconds: float


class LLMClient(Protocol):
    """Exactly one way to call a model."""

    def complete(self, rendered_prompt: str, params: InferenceParams) -> LLMResponse:
        """Return the raw response for ``rendered_prompt`` under ``params``."""
        ...
