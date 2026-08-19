"""Load versioned prompt and schema artifacts for recording on an ``LLMRun``.

Versions live in ``prompts/manifest.json``, not as Python string literals
(D-S002-04 clause 7). A prompt edit without a version bump is a defect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, cast

__all__ = [
    "DOCUMENT_TEXT_PLACEHOLDER",
    "ArtifactVersions",
    "extraction_artifact_versions",
    "load_event_extraction_prompt",
    "load_output_schema",
    "load_system_prompt",
    "render_extraction_prompt",
]

DOCUMENT_TEXT_PLACEHOLDER = "{{document_text}}"

_PROMPTS = files("moj_projekt.llm.prompts")
_MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class ArtifactVersions:
    """The three version strings ADR-0007 records on every ``LLMRun``."""

    prompt_version: str
    system_prompt_version: str
    output_schema_version: str


def extraction_artifact_versions() -> ArtifactVersions:
    """Return prompt/schema versions for ``LLMRun`` recording."""
    manifest = _load_manifest()
    return ArtifactVersions(
        prompt_version=str(manifest["prompt_version"]),
        system_prompt_version=str(manifest["system_prompt_version"]),
        output_schema_version=str(manifest["output_schema_version"]),
    )


def load_system_prompt() -> str:
    """Return the versioned system prompt text."""
    return _read_text(_load_manifest()["system_prompt_file"])


def load_event_extraction_prompt() -> str:
    """Return the versioned event-extraction prompt template."""
    return _read_text(_load_manifest()["prompt_file"])


def load_output_schema() -> dict[str, Any]:
    """Return output schema ``v1`` as a JSON object."""
    name = str(_load_manifest()["output_schema_file"])
    raw = _PROMPTS.joinpath(name).read_text(encoding="utf-8")
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError(f"output schema {name} must be a JSON object")
    return cast(dict[str, Any], loaded)


def render_extraction_prompt(document_text: str) -> str:
    """Substitute the document into the versioned extraction prompt template."""
    template = load_event_extraction_prompt()
    if DOCUMENT_TEXT_PLACEHOLDER not in template:
        raise ValueError(
            f"extraction prompt is missing {DOCUMENT_TEXT_PLACEHOLDER} "
            "(bump the prompt version if the placeholder was removed)"
        )
    return template.replace(DOCUMENT_TEXT_PLACEHOLDER, document_text)


def _load_manifest() -> dict[str, str]:
    raw = _PROMPTS.joinpath(_MANIFEST_NAME).read_text(encoding="utf-8")
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("prompts/manifest.json must be a JSON object")
    return {str(key): str(value) for key, value in loaded.items()}


def _read_text(name: str) -> str:
    return _PROMPTS.joinpath(name).read_text(encoding="utf-8")
