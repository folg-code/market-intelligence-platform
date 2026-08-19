"""Fixture-driven ``LLMClient`` for every default test and later sprint tasks.

Deterministic: the recorded bytes are returned as-is on every call. No
network, no SDK, no API key.
"""

from __future__ import annotations

from pathlib import Path

from moj_projekt.llm.client import InferenceParams, LLMResponse, TokenUsage

__all__ = ["FakeLLMClient"]

_ZERO_USAGE = TokenUsage(
    input_tokens=0,
    output_tokens=0,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=0,
)


class FakeLLMClient:
    """Replays a recorded response byte-for-byte and counts ``complete`` calls."""

    def __init__(
        self,
        recorded_response: bytes,
        *,
        token_usage: TokenUsage | None = None,
        latency_seconds: float = 0.0,
    ) -> None:
        self._recorded_response = recorded_response
        self._token_usage = token_usage if token_usage is not None else _ZERO_USAGE
        self._latency_seconds = latency_seconds
        self._call_count = 0

    @classmethod
    def from_fixture(cls, path: Path) -> FakeLLMClient:
        """Load the recorded response from a fixture file on disk."""
        return cls(path.read_bytes())

    @property
    def call_count(self) -> int:
        """How many times ``complete`` has been invoked."""
        return self._call_count

    def complete(self, rendered_prompt: str, params: InferenceParams) -> LLMResponse:
        """Return the recorded bytes decoded as UTF-8; ignore prompt and params."""
        del rendered_prompt, params
        self._call_count += 1
        return LLMResponse(
            raw_output=self._recorded_response.decode("utf-8"),
            token_usage=self._token_usage,
            latency_seconds=self._latency_seconds,
        )
