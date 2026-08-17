# ADR-0006 - Explicit NarrativeInstrumentImpact replaces a generic sentiment score

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The conventional approach in market-news tooling is a scalar sentiment score per
document or per entity, aggregated upward. Vision sections 7 and 18 reject this:
`sentiment_score` is an explicit non-goal, and directional meaning is instead
carried by an explicit narrative-to-instrument relation. Section 5 additionally
requires that instrument relevance never be inferred solely from entity or
keyword presence.

The reason is epistemic: a scalar sentiment score compresses mechanism, evidence
strength, direction, horizon, and uncertainty into one number that cannot be
explained or audited.

## Decision

Directional meaning is expressed **only** as `NarrativeInstrumentImpact`, one
current assessment per (narrative, instrument), with:

- `relevance` - whether this narrative matters to this instrument at all,
- `direction` - `strongly_bearish` | `bearish` | `mixed` | `neutral` |
  `bullish` | `strongly_bullish` | `uncertain`,
- `confidence`,
- `horizon` - `intraday` | `multi_day` | `unknown`,
- `impact_channels` - the concrete transmission routes,
- `rationale` - a human-readable explanation,
- `evidence_refs` - pointers into the EvidencePack.

Binding rules:

- Three states are kept distinct and must not be collapsed: `mixed` (credible
  channels point in opposite directions), `uncertain` (not enough evidence to
  determine direction), `neutral` (reason to believe impact is limited or
  non-directional).
- Relevance is never derived from keyword/entity co-occurrence alone; an
  economic mechanism connecting narrative to instrument must be stated.
- A non-neutral direction requires non-empty `rationale` and `evidence_refs`.
- Direction and relevance are Tier B decisions (ADR-0002); a high-impact,
  high-confidence assessment without evidence is Tier C - never automated.
- No `sentiment_score` field exists anywhere in the model.
- The tracked instrument set is closed in MVP: NQ, BTC, GOLD.

## Consequences

### Positive

- Every directional statement is explainable and traceable - satisfies the
  Vision quality gate "every directional impact has rationale and evidence".
- Separating `mixed` / `uncertain` / `neutral` preserves information a scalar
  would destroy, and makes the system's ignorance visible.
- Horizon makes an intraday reaction distinguishable from a multi-day theme.

### Negative

- More expensive to produce than a sentiment score: needs an explicit
  per-instrument assessment step with evidence.
- Enumerated directions are not aggregatable arithmetically - ranking and
  dashboard aggregation need rules rather than averaging.
- Harder to evaluate quantitatively against returns (deferred to the post-MVP
  Research Platform anyway).

### Neutral / Trade-offs

- Adding an instrument means adding assessments, not just a filter.
- `impact_channels` will need a controlled vocabulary eventually; free text in
  MVP is acceptable.

## Alternatives Considered

### Option A - Per-document sentiment score aggregated to narrative and instrument

- Pros: cheap, standard, easy to chart.
- Cons: unexplainable, unauditable, conflates evidence strength with direction,
  and rewards volume - the exact failure ADR-0003 exists to prevent.
- Reason rejected: explicit non-goal (Vision section 18).

### Option B - Numeric impact score in [-1, 1] instead of an enum

- Pros: sortable, aggregatable.
- Cons: implies false precision; cannot express `mixed` vs `uncertain` (both map
  to ~0 with opposite meanings).
- Reason rejected: the `mixed`/`uncertain`/`neutral` distinction is a stated
  product requirement.

### Option C - Impact modelled at the Event level rather than the Narrative level

- Pros: finer granularity.
- Cons: the narrative is the product object and the unit the user reasons about;
  per-event impact would need aggregation back up, reintroducing the scalar
  problem.
- Reason rejected: conflicts with the Vision's narrative-centric dashboard.

## Follow-up

- Define ranking rules for dashboard/brief ordering over an enum direction plus
  importance.
- Define the controlled vocabulary for `impact_channels`.

## Related

- ADR-0002 (tiering of direction/relevance decisions)
- ADR-0003 (`evidence_refs` point into the EvidencePack)
- `docs/vision/DOMAIN_MODEL.md` (ImpactDirection, ImpactHorizon)
