# ADR-0015 - Monthly LLM cost ceiling, and spend scales with new documents rather than with cycles

Status: Accepted
Date: 2026-08-19
Owners: architect
Approved by:

## Context

`ARCHITECTURE_FOUNDATIONS.md` section 9 names LLM inference cost as a real
budget constraint, and ADR-0010's follow-up left the actual figure open: *"Set
an explicit monthly cost ceiling and an alert when approaching it - still
**open**, no figure exists in the Vision."* That item has sat in
`CURRENT_STATUS.md` section 8 since Sprint 001 as the decision that "becomes
pressing first, since Phase 3 starts spending."

Sprint 002 opens Roadmap Phase 3 - the first slice that actually spends money.
A ceiling decided after the spending starts is not a constraint, it is a
post-mortem.

Two framings of the spend were considered, and they give wildly different
budgets:

- **Per-cycle framing.** ADR-0004 fixes a 5-minute cadence: ~8,640 cycles per
  month. A $10 ceiling divided by that is ~$0.001 per cycle, which buys nothing
  useful. This framing makes the product look unaffordable.
- **Per-document framing.** Extraction operates on *new* Documents, and most
  cycles from a small source set yield zero new Documents. At ~30 documents/day
  (~900/month), ~2,500 input tokens (article plus prompt) and ~500 output tokens
  per document, verified against current per-1M-token rates (Haiku 4.5 $1 in /
  $5 out; Sonnet 5 $3/$15, $2/$10 introductory through 2026-08-31; Opus 5
  $5/$25):

| Model | Cost / document | Cost / month at ~900 docs |
|---|---|---|
| Haiku 4.5 | ~$0.005 | ~$4.50 |
| Sonnet 5 (introductory) | ~$0.010 | ~$9.00 |
| Sonnet 5 (standard) | ~$0.015 | ~$13.50 |
| Opus 5 | ~$0.025 | ~$22.50 |

The per-document framing is the correct one, and it is only correct if a cycle
with no new documents costs exactly nothing.

## Decision

**1. The monthly LLM cost ceiling is $10/month for the MVP and $50/month for
the eventual product.** $10 is the binding constraint for everything planned
now. The figures are a human decision, recorded here so no later design
re-litigates them.

**2. Spend scales with new-document volume, never with cycle count.** A cycle
that finds no unprocessed Document makes zero LLM calls. There is no
"heartbeat" call, no keep-warm call, and no per-cycle summarisation pass. This
is a binding architectural property of the extract stage, not an optimisation.

**3. Cost is derived from recorded token usage, not estimated.** Per-model
input/output rates live in configuration next to the pinned model IDs; the cost
of a run is computed from `LLMRun.token_usage` and the rate that applied to the
model actually used. No separate cost column is invented - the audit record
(ADR-0007) is already the source of truth.

**4. The ceiling is enforced in code, at two levels:**

- a **soft threshold** (default 80% of the monthly ceiling) which is recorded
  and surfaced but changes no behaviour;
- a **hard ceiling** at which the extract stage stops issuing LLM calls for the
  remainder of the budget period and records that fact on the `CycleRun`. The
  cycle still succeeds, ingestion continues, and Documents queue as
  unprocessed. Running out of budget degrades the product; it never corrupts
  data and never fails the cycle.

A per-cycle cap on the number of Documents sent for extraction bounds the blast
radius of a sudden ingest surge (a backfill, a new adapter) so a single cycle
cannot consume a month's budget before the guard is next evaluated.

**5. The Batch API is not used on the live path.** Its 50% discount comes with
up to 24-hour latency. `PRODUCT_VISION.md` requires intraday alertness and
ADR-0004 fixes a single 5-minute cadence; a document whose events might appear
tomorrow is worthless to a discretionary intraday trader, and adding an
asynchronous result path would be a second, hidden cadence. Batch remains
explicitly *permitted for non-urgent offline work* - bulk backfill of already
collected Documents, and re-extraction replays after a prompt or model version
change (the evaluation use case in ADR-0007). Neither is in Sprint 002's scope.

**6. Prompt caching is not part of the cost plan, and is not silently assumed.**
Three reasons:

- the minimum cacheable prefix on Haiku 4.5 is **4,096 tokens** (1,024 on
  Sonnet 5). A well-written extraction system prompt is far below that, so
  caching would silently never engage: `cache_creation_input_tokens: 0`, no
  error, no warning. Padding a prompt to clear the floor would let a billing
  mechanism dictate prompt design, which is the wrong direction of control;
- the default cache TTL is 5 minutes - exactly the cycle cadence - so an entry
  written in one cycle may expire immediately before the next. The 1-hour TTL
  costs 2x on writes and needs at least three reads to pay off, which a
  low-volume, bursty document flow cannot be relied on to deliver;
- at ~$4.50/month against a $10 ceiling there is no economic pressure to take
  on that complexity.

To keep the decision revisitable on evidence rather than on argument,
`cache_creation_input_tokens` and `cache_read_input_tokens` are recorded in
`LLMRun.token_usage` from the first call, even though both will read zero.

**7. If real measured spend contradicts the ~900 docs/month assumption, the
response is narrower scoping, not a silent budget overrun** - fewer active
sources, a lower per-cycle cap, or a cheaper model for the task. Raising the
ceiling is a human decision and a new ADR.

## Consequences

### Positive

- The most expensive design mistake available here - an LLM call per cycle
  regardless of new data - is now ruled out by an explicit, testable rule.
- Cost becomes an observable property of stored data (`llm_runs.token_usage`)
  rather than a monthly surprise on a provider dashboard.
- The batch and caching questions are answered *before* someone builds around an
  assumption about them; the caching trap (a prefix under the minimum, cached
  never, reported nowhere) is documented rather than discovered.
- The ceiling can be enforced in the MVP with a small deterministic guard,
  without waiting for Phase 10 observability.

### Negative

- The hard ceiling introduces a state where the system silently under-delivers:
  documents are collected but not extracted. This must be visible, or it is
  worse than an error.
- Deriving cost from a rate table means the table is a maintenance surface -
  provider price changes make historical cost figures wrong unless rates are
  themselves versioned by effective date. MVP accepts a flat current table;
  the recorded token counts remain correct regardless.
- Declining prompt caching leaves money on the table if document volume grows
  by an order of magnitude.

### Neutral / Trade-offs

- $10/month is small enough that the *engineering* effort to save money would
  cost more than the money saved. That is deliberate: the ceiling exists to
  prevent a runaway, not to optimise a bill.
- The $50/month product figure is recorded as direction only; nothing in the
  MVP design depends on it.

## Alternatives Considered

### Option A - No explicit ceiling; watch the provider dashboard

- Pros: zero code.
- Cons: a defect (an accidental per-cycle call, an ingest surge, a retry loop on
  a poison document) is discovered by a bill, days later.
- Reason rejected: the failure mode is unbounded and the fix is cheap.

### Option B - Ceiling as a documented convention only

- Pros: no guard code, no new failure state.
- Cons: a convention that nothing enforces is a wish; the sprint's own retro
  vocabulary calls this a "poisoned signal".
- Reason rejected: the human made the figure binding, so it needs a mechanism.

### Option C - Use the Batch API everywhere and accept the latency

- Pros: halves the bill; comfortably fits $10 even on Sonnet.
- Cons: destroys the product's intraday premise and introduces an asynchronous
  result path that contradicts ADR-0004's single cadence.
- Reason rejected: the product requirement outranks the discount. Kept for
  offline backfill/replay only.

### Option D - Design the extraction prompt to clear the 4,096-token cache floor

- Pros: ~0.1x on repeated input tokens.
- Cons: inflates the uncached cost of every first call, makes prompt quality
  subordinate to a billing threshold, and depends on a 5-minute TTL that matches
  the cadence exactly.
- Reason rejected: premature optimisation against a budget that is already met
  with room to spare. Revisit only with recorded evidence of cache-eligible
  volume.

## Follow-up

- Phase 10 observability: surface monthly spend, rejection rate, and per-task
  cost in the operator view; today they are queryable from `llm_runs` only.
- Revisit batch for the backfill/replay path when a prompt or model version
  change first forces a re-extraction pass.
- Revisit caching only if measured monthly document volume exceeds ~5,000, or if
  the input prompt grows past the 4,096-token floor for reasons of its own.
- Rate-table versioning by effective date, if historical cost accuracy ever
  matters.

## Related

- ADR-0010 (provider and tiered model selection; this ADR closes its open
  cost-ceiling follow-up)
- ADR-0016 (Haiku 4.5 as the default extraction model - the direct consequence
  of this ceiling)
- ADR-0004 (single 5-minute cadence - the reason batch is off the live path)
- ADR-0007 (`LLMRun.token_usage` is the cost source of truth)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` section 9
