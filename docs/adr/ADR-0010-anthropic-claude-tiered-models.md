# ADR-0010 - Anthropic Claude as the LLM provider, with tiered model selection

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

`ARCHITECTURE_FOUNDATIONS.md` section 13 listed the LLM provider as the first
blocking open decision. The Vision constrains LLM *behaviour* (sections 8, 10)
but never names a provider.

Requirements that constrain the choice:

- **Structured output.** Every material call returns a schema-shaped candidate
  that a deterministic validator parses (ADR-0002). Free-form prose is unusable.
- **Reproducibility.** `provider`, `model`, `model_version`, `prompt_version`
  must be recordable and stable enough to reconstruct a decision later
  (ADR-0007, Foundations section 7).
- **Cost.** LLM inference is a real budget constraint (Foundations section 9);
  the pipeline runs every 5 minutes over a growing document set.
- **Task heterogeneity.** Tier A tasks (entity extraction, topic classification)
  are low-risk, high-volume mechanical transformations. Tier B tasks
  (event-to-narrative assignment, new-narrative justification, instrument
  relevance/direction) carry the product's actual reasoning weight (ADR-0002).

## Decision

- **Anthropic Claude is the single LLM provider for the MVP.** One provider, one
  SDK, one auth mechanism, one cost dashboard.
- **Model selection is tiered, and the tier is a property of the task type**,
  not of the calling module:
  - **Haiku tier** - low-risk, high-volume Tier A tasks: entity extraction,
    topic classification.
  - **Sonnet tier (default workhorse)** - everything else, including all Tier B
    proposal tasks: candidate event extraction, economic mechanism, market
    interpretation, event-to-narrative assignment, instrument relevance and
    direction, uncertainty reasons, summaries.
  - **Opus tier** - permitted but not used at MVP start; reserved for Tier B
    tasks that measurably underperform on Sonnet. Enabling it for a task is a
    configuration change, not a code change.
- **Task type -> model tier mapping is configuration**, resolved at call time and
  recorded on the `LLMRun`. Changing the mapping never changes the audit meaning
  of past runs, because every run stores the model it actually used.
- **Every material call records the reproducibility fields already specified in
  Foundations section 7** - `provider`, `model`, `model_version`,
  `prompt_version` are mandatory, not best-effort.
- **Model identifiers are pinned explicitly** (dated model IDs, never a floating
  "latest" alias), so a provider-side model rotation cannot silently change
  system behaviour mid-cycle.
- Structured output uses the provider's tool/JSON-schema mechanism; the response
  is still validated against our own schema at the boundary (Foundations
  principle 2) - provider-side schema enforcement is a convenience, not the
  trust boundary.

## Consequences

### Positive

- One integration to build, test, mock, and budget for.
- Cost control without a quality cliff: the highest-volume, lowest-risk work
  runs on the cheapest tier while reasoning-heavy work keeps headroom.
- Pinned model IDs plus per-run recording make "why did the system say this in
  March?" answerable even after the provider retires a model.
- A future quality problem in one task type is addressable by moving that task's
  tier, with no architectural change.

### Negative

- **Provider lock-in for the MVP.** Prompts, structured-output mechanics, and
  token accounting are tuned to one vendor; a migration would mean re-validating
  every prompt.
- Model deprecation is an external clock we do not control - a pinned model ID
  will eventually stop being served, forcing a re-validation pass.
- Tiering adds a small amount of routing configuration and a real risk of
  quality drift if a task is silently on the wrong tier.

### Neutral / Trade-offs

- No local/self-hosted model in MVP; cost is per-token operating expense rather
  than fixed infrastructure.
- Rate limits and provider availability become a cycle-reliability concern
  (Phase 10), handled by per-source-style failure isolation rather than a
  fallback provider.
- Embeddings for narrative candidate matching are a separate concern with a
  separate provider decision (ADR-0014).

## Alternatives Considered

### Option A - OpenAI models

- Pros: comparable structured-output support; large ecosystem.
- Cons: no decisive advantage for this workload; a second-provider evaluation
  costs sprint time now for optionality we do not currently need.
- Reason rejected: the human owner's choice; no requirement in the Vision
  distinguishes the two for this use case.

### Option B - Multi-provider abstraction from day one

- Pros: no lock-in; per-task best-of-breed routing.
- Cons: prompts stop being portable in practice anyway (they are tuned per
  model family); doubles the prompt-validation surface; violates YAGNI
  (Foundations principle 4) for a single-user MVP.
- Reason rejected: abstraction before the second concrete use case.

### Option C - Local/open-weight models

- Pros: no per-token cost; full data control.
- Cons: hardware requirement, weaker structured-output reliability, and quality
  risk exactly where the product is most fragile (Tier B narrative reasoning).
- Reason rejected: the product's core promise is epistemic discipline; buying
  reasoning quality is the right trade at MVP scale.

### Option D - One single model for every task

- Pros: simplest possible configuration.
- Cons: either pays reasoning-tier prices for entity extraction, or runs
  narrative assignment on a model that is too weak for it.
- Reason rejected: cost and quality pull in opposite directions across the task
  set; the tiering is cheap to express.

## Follow-up

- Define the concrete task-type -> tier mapping table alongside the first prompt
  versions (Phase 3).
- Record token usage and cost per task type from the very first LLM slice, so
  tier decisions are made against data (Phase 10 observability).
- Set an explicit monthly cost ceiling and an alert when approaching it - still
  **open**, no figure exists in the Vision.

## Related

- ADR-0002 (LLM outputs are candidates behind a deterministic validator)
- ADR-0007 (LLM run audit record)
- ADR-0014 (pgvector and embeddings for narrative candidate matching)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` sections 2, 5, 7, 9
