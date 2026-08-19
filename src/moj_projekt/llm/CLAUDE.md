# llm/

This module is the **only** place allowed to talk to the Anthropic SDK.
Nothing outside `llm/` may import `anthropic` (enforced by a unit test).

## Prompt-version bump

Prompts and output schemas under `prompts/` are versioned artifacts
(ADR-0007, D-S002-04 clause 7). Editing a prompt or schema without bumping
its version is a review-blocking defect: every `LLMRun` records
`prompt_version`, `system_prompt_version`, and `output_schema_version`, and
a silent edit would make past runs lie about what actually ran.

Bump by changing the explicit version fields in `prompts/manifest.json` and
the corresponding filename (`*_v1` -> `*_v2`). Do not edit an already-shipped
version in place.

## Never commit secrets

The API key is read through typed `Settings` (`ANTHROPIC_API_KEY`). A
placeholder lives in `.env.example` only. Never commit `.env` or a real key.
`AnthropicClient` must not be constructed without a key; default tests use
`FakeLLMClient`.

## Pinned model IDs

Every model identifier is a dated pin (ADR-0010, ADR-0016). Never `latest`,
never an undated alias such as `claude-haiku-4-5`. Extraction uses
`claude-haiku-4-5-20251001`. The mapping lives in `models.py`; adding a task
type is adding a row.
