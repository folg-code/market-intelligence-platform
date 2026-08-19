"""One narrow port for calling a model (ADR-0010).

No domain type crosses this port. The Anthropic SDK stays in this package.
See ``src/moj_projekt/llm/CLAUDE.md``.
"""

from __future__ import annotations

from moj_projekt.llm.anthropic_client import AnthropicClient
from moj_projekt.llm.artifacts import (
    ArtifactVersions,
    extraction_artifact_versions,
    load_event_extraction_prompt,
    load_output_schema,
    load_system_prompt,
    render_extraction_prompt,
)
from moj_projekt.llm.client import InferenceParams, LLMClient, LLMResponse, TokenUsage
from moj_projekt.llm.fake import FakeLLMClient
from moj_projekt.llm.models import (
    EVENT_EXTRACTION_TASK_TYPE,
    EXTRACTION_MODEL_ID,
    ModelSpec,
    model_spec_for,
)

__all__ = [
    "EVENT_EXTRACTION_TASK_TYPE",
    "EXTRACTION_MODEL_ID",
    "AnthropicClient",
    "ArtifactVersions",
    "FakeLLMClient",
    "InferenceParams",
    "LLMClient",
    "LLMResponse",
    "ModelSpec",
    "TokenUsage",
    "extraction_artifact_versions",
    "load_event_extraction_prompt",
    "load_output_schema",
    "load_system_prompt",
    "model_spec_for",
    "render_extraction_prompt",
]
