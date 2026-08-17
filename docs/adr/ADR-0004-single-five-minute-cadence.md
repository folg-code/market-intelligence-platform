# ADR-0004 - One 5-minute processing cycle; no multi-cadence scheduling in MVP

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The pipeline has stages with genuinely different natural cadences: official
source releases are latency-sensitive, news feeds are steady, narrative state
recomputation is expensive, and the Morning Brief is a once-a-day artifact. The
tempting design is a staggered scheduler with per-stage cadences.

Vision section 13 rejects that for MVP, and section 18 lists both "complex
multi-cadence scheduling" and "low-latency event-driven official-source
processing" as explicit non-goals.

## Decision

One processing cycle runs every 5 minutes and performs, in order:

1. ingest new documents,
2. extract events,
3. update narrative candidates,
4. rebuild affected EvidencePacks,
5. recalculate narrative state,
6. evaluate alert rules.

Additional binding properties:

- **Alerts are generated inside this cycle** - there is no separate alerting
  loop.
- **The Morning Brief is the only separate job**: on demand plus a configurable
  schedule.
- **The cycle is idempotent and resumable.** A failed or partial run must be
  safe to re-run without duplicating Documents, Events, assignments, evidence
  versions, or Alerts.
- **A single failing source must not fail the cycle** - ingestion degrades
  per-source.
- **Work is change-scoped:** only narratives touched by new events are
  recomputed.
- Overlapping runs are prevented (a run still in progress at the next tick is
  not started concurrently).

## Consequences

### Positive

- One schedule to reason about, one place for failure handling, one place for
  observability.
- Deterministic ordering between stages removes a whole class of race
  conditions.
- Makes end-to-end testing feasible: run one cycle against fixtures, assert the
  resulting state.

### Negative

- Worst-case latency from publication to dashboard is ~5 minutes plus cycle
  duration - an FOMC release is not surfaced instantly.
- The cycle must complete well inside 5 minutes; LLM latency is the risk, and
  event extraction volume is the variable.
- Coupling: a slow stage delays every later stage.

### Neutral / Trade-offs

- If cycle duration approaches the interval, the response is to scope work
  harder or lengthen the interval - not to introduce a second cadence, which
  would require a superseding ADR.
- The interval itself should be configuration, so tuning does not require a code
  change.

## Alternatives Considered

### Option A - Per-stage staggered cadences

- Pros: cheaper recomputation, tighter latency where it matters.
- Cons: multiple schedules, cross-stage staleness, much harder to test and
  debug.
- Reason rejected: explicit non-goal (Vision section 18); premature for a
  single-user MVP with a handful of sources.

### Option B - Event-driven / push processing on source publication

- Pros: near-real-time for official releases.
- Cons: requires per-source push mechanisms (most are pull-only anyway) and a
  broker or queue.
- Reason rejected: explicit non-goal; also conflicts with ADR-0005 (no broker).

### Option C - Continuous loop with no fixed interval

- Pros: naturally adaptive.
- Cons: unpredictable LLM cost, harder to reason about "what changed since last
  cycle", no natural boundary for the end-of-cycle invariant check.
- Reason rejected: the cycle boundary is where the "every material narrative has
  a current EvidencePack" invariant is enforced.

## Follow-up

- Choose the scheduler mechanism (**open** - see
  `ARCHITECTURE_FOUNDATIONS.md` section 13); this ADR fixes the cadence, not the
  technology.
- Define the run record for a cycle (start, end, stages, per-source failures)
  for observability.

## Related

- ADR-0005 (in-process alerting, no broker)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` section 4
