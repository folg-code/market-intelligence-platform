# ADR-0016 - Haiku 4.5 is the default extraction model; Sonnet is an escalation, not the workhorse (amends ADR-0010)

Status: Proposed
Date: 2026-08-19
Owners: architect
Approved by:

## Context

ADR-0010 designates **Sonnet as the default workhorse** - "everything else,
including all Tier B proposal tasks: candidate event extraction, economic
mechanism, market interpretation, ..." - with Haiku reserved for "low-risk,
high-volume Tier A tasks: entity extraction, topic classification."

ADR-0015 now fixes a **$10/month ceiling** for the MVP. Against the verified
per-document cost model in that ADR (~2,500 input / ~500 output tokens,
~900 documents per month):

| Model | Cost / month | Against a $10 ceiling |
|---|---|---|
| Haiku 4.5 | ~$4.50 | fits, with headroom for retries and later phases |
| Sonnet 5 (introductory, through 2026-08-31) | ~$9.00 | exactly at the ceiling, with zero headroom |
| Sonnet 5 (standard) | ~$13.50 | over budget |

ADR-0010's mapping is therefore not merely expensive - it is arithmetically
incompatible with the approved ceiling the moment introductory pricing ends, and
it leaves no budget at all for Phases 4-6, which add *more* LLM tasks per
narrative on top of extraction. Planning Sprint 002 around a contradiction
without naming it would be exactly the kind of silent drift this project's
governance exists to prevent.

Two facts limit how far this ADR should go:

- ADR-0010's *classification* is sound: extraction is a Tier A task
  (`ARCHITECTURE_FOUNDATIONS.md` section 5 lists "candidate event extraction"
  under Tier A - the LLM may perform it independently). ADR-0010's own model
  mapping is what pulled it onto Sonnet, not its decision-tier reasoning.
- Model tier and decision tier are already declared independent: "a cheaper
  model never grants a task more authority" (Foundations section 5). Moving
  extraction to Haiku changes what runs it, not what it is allowed to finalize -
  everything still passes the deterministic validator (ADR-0002).

## Decision

This ADR **amends the model-tier mapping in ADR-0010**. Everything else in
ADR-0010 - Anthropic as the single provider, tiering as configuration, pinned
model identifiers, mandatory reproducibility fields, provider-side schema
enforcement not being the trust boundary - stands unchanged. ADR-0010's text is
deliberately left untouched, per the `adr` skill.

**1. Haiku 4.5 is the default model for event extraction**, the highest-volume
task in the system, and remains the model for the other Tier A mechanical tasks
ADR-0010 already assigned to it.

**2. Sonnet is an escalation path, not the default.** It is used where a task is
measurably degraded on Haiku, and enabling it for a task remains a configuration
change (ADR-0010), not a code change. No task starts on Sonnet by default in the
MVP. Opus remains unused, as in ADR-0010.

**3. Escalation is evidence-driven, not preference-driven.** A task moves to
Sonnet only when there is recorded evidence from `llm_runs` - a materially
elevated validator rejection rate, or a documented review of accepted-but-wrong
extractions - and only when the resulting monthly cost still fits the ADR-0015
ceiling. The `LLMRun` record stores the model actually used, so past runs keep
their audit meaning across any remapping.

**4. The pinned model identifier for extraction is
`claude-haiku-4-5-20251001`.** The undated alias `claude-haiku-4-5` also
resolves to this model and is **forbidden**: it is a floating alias, exactly the
class of identifier ADR-0010 rules out and the `ck_llm_runs_no_latest_alias`
CHECK constraint (migration `0005`) exists to catch. The engineer verifies the
dated identifier against the provider's model list before first use; a
correction is a configuration change, not a code change.

**5. The task-type to model mapping is one declarative configuration table**,
holding for each task type: the pinned model id, the model version recorded on
the run, and the input/output token rates ADR-0015 derives cost from. Adding a
task type is adding a row.

## Consequences

### Positive

- Monthly spend lands at roughly 45% of the ceiling instead of 90-135%, leaving
  genuine headroom for Phases 4-6 (narrative matching, evidence, impact), which
  add per-narrative LLM work on top of per-document extraction.
- Extraction latency drops, which matters directly: extraction runs inside the
  5-minute cycle budget (ADR-0004).
- The contradiction between ADR-0010 and the approved ceiling is resolved in the
  open, with the arithmetic recorded, rather than being worked around in a
  sprint plan.

### Negative

- **Extraction quality risk is real and is accepted deliberately.** A smaller
  model may over-extract (spurious events from commentary), under-extract (miss
  a development stated obliquely), or blur the facts/claims separation ADR-0008
  depends on. The mitigation is not optimism: the deterministic validator
  (ADR-0002) is the gate, and rejection rate is the monitored signal.
- If Haiku proves inadequate, the fix costs a sprint of prompt work or a budget
  conversation - not a code change, but not free either.
- Extraction quality on the cheapest tier is now a first-class risk to watch
  from the first cycle, rather than something Sonnet was implicitly insuring
  against.

### Neutral / Trade-offs

- This makes ADR-0010's "Tier A / Tier B" split and the Haiku/Sonnet split less
  aligned than originally written: extraction is Tier A but was mapped to
  Sonnet. The alignment is now restored in the cheaper direction, which is a
  clarification as much as a change.
- The escalation path costs nothing to keep open, because the mapping was
  already designed as configuration.

## Alternatives Considered

### Option A - Keep Sonnet as the default and raise the ceiling

- Pros: no quality risk; ADR-0010 unchanged.
- Cons: the ceiling was just set by the human at $10 as a binding constraint;
  raising it immediately to accommodate a default nobody has evidence for
  inverts the decision.
- Reason rejected: no evidence yet that Haiku is insufficient. Escalate on data,
  not on caution.

### Option B - Keep Sonnet, cut document volume to fit

- Pros: preserves the stronger model.
- Cons: fewer documents means less evidence, and independent-source counting
  (ADR-0003) degrades directly with source breadth. It buys model quality with
  product quality.
- Reason rejected: the product's promise is evidence coverage; that is the wrong
  thing to trade away.

### Option C - Route per document (Haiku for short items, Sonnet for long or
Tier 1 official ones)

- Pros: spends the money where it plausibly matters most.
- Cons: introduces a routing heuristic with no evidence behind it, doubles the
  prompt-validation surface, and makes cost non-obvious - all before a single
  extraction has ever run.
- Reason rejected: YAGNI (Foundations principle 4). Revisit once rejection-rate
  data exists per source tier; the configuration table makes it a small change.

### Option D - Supersede ADR-0010 entirely with a rewritten model policy

- Pros: one document to read.
- Cons: ADR-0010's provider choice, pinned-ID rule, and reproducibility
  requirements are all unchanged and already implemented (including a DB CHECK);
  superseding would discard a still-correct decision to fix one table.
- Reason rejected: an amendment is the honest scope, following the ADR-0014
  amends ADR-0005 precedent already established in this repo.

## Follow-up

- Record the validator rejection rate per task type from the first cycle;
  it is the escalation trigger, so it must exist before anyone argues about
  model quality.
- Revisit this mapping once ~1,000 extractions have run, or immediately if the
  rejection rate is materially higher than the rate observed against fixtures.
- Resolve the pinned dated identifier for the Sonnet escalation model only when
  a task is first escalated - not before, since an unused pinned ID would rot.

## Related

- ADR-0010 (amended by this ADR - model tier mapping only)
- ADR-0015 (the cost ceiling that forces this decision)
- ADR-0002 (the deterministic validator that makes a cheaper model safe)
- ADR-0007 (`LLMRun` records the model actually used, per run)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` section 5
