# ADR-0001 - Narrative identity is a semantic canonical_key, not a cluster hash

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The Narrative is the product's central object and must have continuity over
time: the same market interpretation may re-emerge weeks later, driven by
different documents and different entities. Clustering pipelines conventionally
identify a group by a cluster id or content hash, which changes whenever the
underlying document set changes.

Vision section 6 states the requirement directly: narrative identity is
semantic, not cluster-hash-based, with keys such as
`fed_rate_cut_expectations`, `btc_regulatory_pressure`, `ai_capex_consequences`,
`gold_safe_haven_demand`.

## Decision

A Narrative is identified by `canonical_key`: a stable, human-readable,
semantic identifier assigned once and preserved across time and across episodes.

- Technical clusters may exist and may carry hashes, but a cluster hash never
  defines narrative identity.
- Assigning a new `canonical_key` (i.e. creating a new Narrative) is a Tier B
  decision: an LLM may propose it, a deterministic validator may accept it.
- Changing an existing `canonical_key` is a Tier C decision: never automated,
  and out of scope for MVP (post-MVP "Narrative Governance").
- Recurrence over time is represented with `NarrativeEpisode` under one
  `canonical_key`, not with a new Narrative.

## Consequences

### Positive

- Narrative history, overrides, and audit remain attached across reappearances.
- The key is readable in logs, URLs, briefs, and conversation - it is part of
  the ubiquitous language, not an internal detail.
- Human overrides survive reclustering, which is what makes "manually rejected
  mappings do not silently return" achievable.

### Negative

- Requires a canonical key registry plus a matching step ("is this candidate the
  same narrative as an existing key?"), which is a genuine modelling risk and
  the hardest unsolved part of the pipeline.
- Poorly chosen keys are sticky - too broad and everything collapses into one
  narrative, too narrow and the same interpretation fragments.

### Neutral / Trade-offs

- Key naming becomes a convention that needs a documented style rule
  (`snake_case`, subject-first, mechanism-bearing).
- Merge/split, the natural remedy for bad keys, is deliberately post-MVP - so
  early key quality matters more than it otherwise would.

## Alternatives Considered

### Option A - Cluster hash / cluster id as identity

- Pros: trivially automatic, no matching step, no registry.
- Cons: identity churns whenever documents change; overrides and history do not
  survive; keys are meaningless to a human.
- Reason rejected: directly contradicts Vision section 6 and destroys the audit
  and override guarantees in section 17.

### Option B - Surrogate id only, with the semantic key as a mere label

- Pros: conventional, decouples identity from naming mistakes.
- Cons: nothing then enforces that the same interpretation maps to one object;
  duplicate narratives proliferate silently.
- Reason rejected: a surrogate primary key is fine as a storage detail, but the
  uniqueness and continuity guarantee must live on `canonical_key`.

## Follow-up

- Define the canonical key naming convention and the candidate-to-existing-key
  matching mechanism (open question in `DOMAIN_MODEL.md` section 8).
- Decide whether matching uses embeddings (would imply a vector extension - own
  ADR).

## Related

- `docs/vision/DOMAIN_MODEL.md` (Narrative, NarrativeEpisode)
- ADR-0002 (candidate/validation tiers)
