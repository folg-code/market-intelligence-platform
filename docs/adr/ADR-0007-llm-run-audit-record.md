# ADR-0007 - Every material LLM run is persisted as an append-only audit record with input references

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

Vision section 10 requires the system to be able to answer, later: *"Why did the
system assign this event to this narrative on a given date?"* - and to return
input, prompt version, model, raw output, parsed result, and validator result.
It also states explicitly that `input_hash` alone is not sufficient for
reproducibility; input references or snapshots are needed.

This is the mechanism that makes the whole traceability promise real. It is
hard to retrofit: if runs are not recorded from the first LLM call, the history
is unrecoverable.

## Decision

Every **material** LLM invocation (any run whose output can influence domain
state - i.e. all Tier A/B tasks from ADR-0002) writes an append-only `LLMRun`
record containing:

`id`, `task_type`, `provider`, `model`, `model_version`, `prompt_version`,
`system_prompt_version`, `input_hash`, `input_reference_ids`,
`output_schema_version`, `raw_output`, `parsed_output`, `validation_status`,
`validation_errors`, `temperature`, `inference_parameters`, `token_usage`,
`latency`, `created_at`.

Binding rules:

- **Both `input_hash` and `input_reference_ids` are required.** The hash detects
  identity; the references reconstruct content. Where inputs are not durable
  (e.g. derived text), a snapshot is stored instead.
- **Prompts and system prompts are versioned artifacts** in the repository, and
  the version is recorded per run - a prompt change is a traceable change.
- **Output schemas are versioned** and recorded per run.
- **Records are append-only**; failed and rejected runs are recorded too - they
  are the evaluation dataset, not noise.
- **Every material domain decision produced with LLM assistance references its
  `LLMRun`** (notably NarrativeEvent assignments, narrative creation,
  NarrativeInstrumentImpact, NarrativeRelation).

## Consequences

### Positive

- Makes the Vision's audit question answerable by query rather than by
  archaeology.
- Enables offline evaluation and regression testing when a model or prompt
  changes: replay recorded inputs against a new version.
- Cost and latency accounting comes for free from `token_usage` / `latency`.

### Negative

- Meaningful storage growth: raw outputs are verbose and every cycle produces
  runs. Needs a retention policy.
- Every LLM call site must go through a wrapper that records - a discipline
  constraint on the code, enforceable in review.
- Raw outputs may contain source text; retention interacts with source terms of
  use.

### Neutral / Trade-offs

- The record is provider-shaped (`provider`, `model`, `inference_parameters`),
  which is fine and intentional - it must reflect what actually ran.
- "Material" excludes trivial helper calls; the boundary needs to be stated
  explicitly so it is not used as an excuse to skip recording.

## Alternatives Considered

### Option A - Log LLM calls to application logs only

- Pros: nearly free.
- Cons: not queryable, not joinable to domain objects, subject to log rotation.
- Reason rejected: audit is a product feature here, not an operational
  nice-to-have.

### Option B - Store `input_hash` only, without references or snapshots

- Pros: compact.
- Cons: a hash proves sameness but cannot reconstruct the input; replay becomes
  impossible.
- Reason rejected: Vision section 10 rejects this explicitly.

### Option C - Record only accepted runs

- Pros: less storage.
- Cons: destroys the ability to analyse rejection rates and validator
  over-strictness - the main quality signal for ADR-0002.
- Reason rejected: rejections are the most informative records.

## Follow-up

- Define what counts as "material" per task type.
- Define a retention/archival policy for `raw_output` and large inputs.
- Define the prompt-versioning convention and where prompts live in the repo.

## Related

- ADR-0002 (candidate/validation layer whose result is recorded here)
- ADR-0009 (human-side audit trail - the complementary record)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` section 7
