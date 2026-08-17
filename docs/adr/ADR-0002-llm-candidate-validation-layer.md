# ADR-0002 - LLM outputs are candidates behind a deterministic validation layer

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The system's promise is traceability and epistemic discipline, not prediction.
LLMs are needed for semantic work (extraction, mechanism/interpretation
phrasing, assignment proposals), but their output is non-deterministic and
occasionally confidently wrong. Vision section 8 defines three explicit tiers of
what an LLM may do, propose, and never finalize.

The design choice is architectural rather than tactical: it decides where truth
is established in the system, and it is expensive to retrofit once LLM output
writes directly to domain tables.

## Decision

No LLM output ever writes directly to domain state. Every material LLM result
flows:

```text
LLM output -> candidate -> deterministic validation layer -> accepted / proposed / rejected
```

Tiers (binding):

- **Tier A - LLM may perform independently:** entity extraction, topic
  classification, candidate event extraction, candidate economic mechanism,
  candidate market interpretation, relation candidate generation, uncertainty
  reason generation, summary generation.
- **Tier B - LLM may propose, not finalize:** event-to-narrative assignment,
  new narrative creation, instrument relevance, instrument direction, narrative
  relations, canonical mapping changes. A deterministic rule may **auto-accept**
  when confidence and evidence requirements are met; otherwise the result is
  persisted as `proposed` and surfaced to the user.
- **Tier C - LLM must never finalize:** `validity_status = confirmed`, merge,
  split, any change to a `user_locked` decision, high-confidence/high-impact
  instrument impact without evidence, any durable change to semantic narrative
  identity.

The validation layer is deterministic code (schema validation + evidence and
threshold rules), not another LLM call. Most Tier B decisions are expected to
be auto-accepted - the tiering governs *who may finalize*, not how much manual
work exists.

## Consequences

### Positive

- A single, testable choke point for correctness; validators are unit-testable
  without a model.
- `accepted` / `proposed` / `rejected` becomes a first-class domain state,
  which is what makes the "proposals, not silent changes" override semantics
  possible.
- Prompt or model regressions degrade into rejected candidates rather than
  corrupted domain state.

### Negative

- Every LLM-touching feature costs twice: the prompt plus the validator.
- Requires strict output schemas and versioning of them.
- A too-strict validator silently suppresses correct results - rejection rates
  need monitoring.

### Neutral / Trade-offs

- Rejected candidates must be persisted (they are the evaluation dataset), which
  adds storage.
- The auto-accept thresholds become tunable product knobs, not constants.

## Alternatives Considered

### Option A - Trust structured LLM output directly

- Pros: fastest to build; fewer moving parts.
- Cons: no place to enforce evidence rules; a hallucinated instrument impact
  becomes indistinguishable from a supported one.
- Reason rejected: contradicts Vision sections 8 and 9 and the product's core
  promise.

### Option B - Human review of every LLM decision

- Pros: maximum safety.
- Cons: unusable at a 5-minute cadence for a single user; the product would
  become a labelling tool.
- Reason rejected: Vision section 8 explicitly says many decisions do not
  require a human and may be auto-accepted by deterministic rules.

### Option C - LLM-as-judge validating LLM output

- Pros: catches semantic errors a rule cannot express.
- Cons: non-deterministic validation of non-deterministic output; unauditable;
  doubles cost.
- Reason rejected: fails the reproducibility requirement (ADR-0007). May return
  post-MVP as a *supplementary* signal, never as the gate.

## Follow-up

- Define output schema versioning and the validator rule set per task type.
- Define auto-accept thresholds per Tier B decision (open question).
- Define retention for rejected candidates.

## Related

- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` section 5
- ADR-0003 (evidence requirements the validator enforces)
- ADR-0007 (LLM run audit record)
- ADR-0009 (`user_locked` interaction)
