"""Real ``LLMClient`` over Anthropic's structured-output Messages API.

Constructed only when a key is present in typed Settings. Default tests
never reach this class except to assert that a missing key fails clearly.
"""

from __future__ import annotations

import json
import time
from typing import cast

import anthropic
from anthropic.types import Message, Usage
from anthropic.types.output_config_param import OutputConfigParam

from moj_projekt.config.settings import Settings
from moj_projekt.domain.llm_run import reject_floating_model_alias
from moj_projekt.llm.client import InferenceParams, LLMResponse, TokenUsage

__all__ = ["AnthropicClient", "MissingAnthropicAPIKeyError"]

_DEFAULT_TIMEOUT_SECONDS = 30.0


class MissingAnthropicAPIKeyError(ValueError):
    """``AnthropicClient`` was constructed without ``ANTHROPIC_API_KEY``."""


class AnthropicClient:
    """Pinned-model Anthropic adapter. One bounded timeout; no retries."""

    def __init__(
        self,
        settings: Settings,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        api_key = settings.anthropic_api_key
        if api_key is None or not api_key.strip():
            raise MissingAnthropicAPIKeyError(
                "Anthropic API key is missing. Set ANTHROPIC_API_KEY in the "
                "environment (placeholder in .env.example). AnthropicClient "
                "must not be constructed without a key."
            )
        self._client = anthropic.Anthropic(
            api_key=api_key.strip(),
            timeout=timeout_seconds,
        )
        self._timeout_seconds = timeout_seconds

    def complete(self, rendered_prompt: str, params: InferenceParams) -> LLMResponse:
        """Call the provider with structured output; record usage and latency."""
        reject_floating_model_alias(params.model, field_name="model")
        output_config: OutputConfigParam = {
            "format": {
                "type": "json_schema",
                "schema": cast(dict[str, object], dict(params.output_schema)),
            }
        }
        started = time.perf_counter()
        message = self._client.messages.create(
            model=params.model,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
            system=params.system_prompt,
            messages=[{"role": "user", "content": rendered_prompt}],
            output_config=output_config,
            timeout=self._timeout_seconds,
        )
        latency_seconds = time.perf_counter() - started
        return LLMResponse(
            raw_output=_raw_output(message),
            token_usage=_token_usage(message.usage),
            latency_seconds=latency_seconds,
        )


def _raw_output(message: Message) -> str:
    parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            parts.append(block.text)
        elif block.type == "tool_use":
            parts.append(json.dumps(block.input, ensure_ascii=False, separators=(",", ":")))
    return "".join(parts)


def _token_usage(usage: Usage) -> TokenUsage:
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=usage.cache_read_input_tokens or 0,
    )
