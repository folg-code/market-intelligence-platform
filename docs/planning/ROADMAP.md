# Roadmap

Status: Accepted
Approved by:
Approval date:

The status above covers the DIRECTION of the roadmap as a whole and requires
human approval (skill `governance`). The `Status:` on individual phases below
describes execution progress and does not need separate approval.

Note on location: this file lives at `docs/planning/ROADMAP.md` per the
`planning` skill (the roadmap is a planning artifact; `docs/vision/` holds the
durable vision/architecture/domain documents).

## 1. Purpose

Strategic direction for the Market Intelligence Platform: phases, dependencies,
risks, completion criteria. Not a task board, not a schedule, not a promise of
dates.

## 2. Principles

1. Deliver small vertical slices - each phase produces something inspectable.
2. Validate the architecture through implementation.
3. Don't build infrastructure for hypothetical scale (Vision section 18).
4. Update the roadmap as new evidence appears.
5. Don't rewrite the scope of completed sprints.
6. Treat deferred and rejected ideas as a record of learning.

## 3. Capability Tracks

```text
Foundation Track
  Phase 0 - Governance and repository foundation
  Phase 1 - Domain model and storage

Product Track
  Phase 2 - Ingestion: Sources -> Documents
  Phase 3 - Event extraction (first LLM slice)
  Phase 4 - Narrative candidates and identity
  Phase 5 - EvidencePack and trust rules
  Phase 6 - Instrument impact (NQ / BTC / GOLD)
  Phase 7 - Read path: API, dashboard, Morning Brief
  Phase 8 - Alerts
  Phase 9 - Human overrides and audit

Quality / Operations Track
  Phase 10 - Cycle reliability, observability, deployment

Future Track
  Phase 11+ - Post-MVP milestones (Vision section 20)
```

MVP = Phases 0-10.

## 4. Phases

### Phase 0 - Governance and repository foundation

Status: Not started

#### Purpose

Make the repo workable: version control, the open architectural decisions
resolved, and the toolchain fixed - so no later phase is blocked on a stack
question.

#### Expected Capabilities

- Git repository initialized; branch model per the `git-workflow` skill.
- Open decisions from `ARCHITECTURE_FOUNDATIONS.md` section 13 resolved and
  recorded as ADRs: LLM provider/model, scheduler mechanism, frontend
  technology, hosting target.
- Python toolchain fixed (dependency management, lint, type-check, test runner);
  root `CLAUDE.md` written for the chosen stack.
- Local PostgreSQL runnable; migration tooling chosen.
- CI running lint + type-check + tests.

#### Primary Vertical Slice

```text
Fresh clone -> one documented command -> lint + types + tests green
```

#### Completion Criteria

- [ ] Repository under version control with `main` and the branch model in use
- [ ] Four open-decision ADRs written and Accepted
- [ ] `docs/reference/WORKFLOWS.md` and root `CLAUDE.md` exist
- [ ] CI green on an empty-but-real test suite

#### Dependencies

- Human approval of `ARCHITECTURE_FOUNDATIONS.md`, `DOMAIN_MODEL.md`, and
  ADR-0001..0009.

#### Risks

- LLM provider choice has downstream cost/latency consequences for Phase 3
  onward; choosing late blocks work, choosing badly is expensive to reverse.

#### Out of Scope

- Any domain logic.

---

### Phase 1 - Domain model and storage

Status: Not started

#### Purpose

Turn the approved domain model into persisted schema and pure domain types, so
every later phase writes into a stable shape.

#### Expected Capabilities

- Schema for Source, Document, Event, Narrative, NarrativeEpisode,
  NarrativeEvent, NarrativeRelation, EvidencePack, NarrativeInstrumentImpact,
  Alert, LLMRun, AuditEntry.
- Enumerated value objects (validity, lifecycle, direction, horizon, override
  state, candidate status, source tier) as domain types, not loose strings.
- Repository/persistence boundary keeping domain rules infrastructure-free.
- Seeded Source registry with tiers (Fed/FOMC, BLS, SEC, 2-3 news/RSS).

#### Primary Vertical Slice

```text
Migration -> seeded sources -> domain object round-trips through the store -> invariant tests pass
```

#### Completion Criteria

- [ ] All MVP entities persisted with migrations
- [ ] Aggregate invariants from `DOMAIN_MODEL.md` section 5 covered by tests
- [ ] Domain rules unit-testable without a database

#### Dependencies

- Phase 0.

#### Risks

- Over-modelling ahead of use; keep JSONB where the shape is still uncertain
  (ADR-0005).

#### Out of Scope

- Claim/Fact tables (ADR-0008); automated episode lifecycle.

---

### Phase 2 - Ingestion: Sources -> Documents

Status: Not started

#### Purpose

Get real, immutable, deduplicated source data into the system on a schedule.

#### Expected Capabilities

- Adapters for the MVP sources; normalization into Documents.
- Deduplication; immutability of collected Documents.
- Per-source failure isolation (a failing feed does not fail the run).
- The 5-minute cycle skeleton (ADR-0004): idempotent, non-overlapping,
  change-scoped, with a per-cycle run record.
- Publisher/independence metadata captured at ingest for later use in Phase 5.

#### Primary Vertical Slice

```text
Scheduled tick -> fetch all sources -> normalize -> dedupe -> Documents in PostgreSQL -> cycle run record
```

#### Completion Criteria

- [ ] Documents flowing automatically from all MVP sources
- [ ] Re-running a cycle produces no duplicates
- [ ] One source failing leaves the others unaffected and visible in the run
      record

#### Dependencies

- Phases 0, 1.

#### Risks

- Third-party format drift and rate limits; SEC/BLS access patterns.

#### Out of Scope

- Social sources; company IR; exchange announcements.

---

### Phase 3 - Event extraction (first LLM slice)

Status: Not started

#### Purpose

The first LLM-in-the-loop slice, with the candidate/validation and audit
machinery in place from the very first call.

#### Expected Capabilities

- Event extraction producing separated `extracted_facts` and `source_claims`
  (ADR-0008).
- Versioned prompts and versioned output schemas.
- The deterministic validation layer (ADR-0002) with `accepted` / `proposed` /
  `rejected`.
- `LLMRun` recording on every material call, with input references (ADR-0007).

#### Primary Vertical Slice

```text
Document -> prompt(v) -> LLM -> candidate -> validator -> Event persisted + LLMRun recorded
```

#### Completion Criteria

- [ ] Events extracted automatically inside the cycle
- [ ] Every Event traces to at least one Document and to its LLMRun
- [ ] Malformed/failed LLM output produces a rejected candidate, never a
      corrupt Event
- [ ] "Why was this Event created?" answerable from stored data alone

#### Dependencies

- Phases 1, 2; LLM provider ADR from Phase 0.

#### Risks

- Extraction quality and cost per document; over- or under-extraction.
- Validator strictness silently suppressing good results - monitor rejection
  rate.

#### Out of Scope

- Narrative assignment.

---

### Phase 4 - Narrative candidates and identity

Status: Not started

#### Purpose

The hardest and most product-defining phase: stable semantic narrative identity
and disciplined event-to-narrative assignment.

#### Expected Capabilities

- Canonical key registry and naming convention (ADR-0001).
- Candidate matching: does this event belong to an existing `canonical_key`, or
  does it justify a new narrative?
- Three-condition assignment rule enforced (same mechanism, similar
  instruments/exposures, same interpretation updated).
- Narrative fields: mechanism, interpretation, validity, lifecycle,
  uncertainty reasons, contradiction signals.
- Dynamics: attention_score, strength, velocity, momentum with defined windows.
- NarrativeEpisode present in schema, manual-only.

#### Primary Vertical Slice

```text
New Events -> narrative candidate proposals -> validator -> assignment or new canonical_key -> narrative state recalculated
```

#### Completion Criteria

- [ ] Narratives created and updated automatically across cycles
- [ ] The same interpretation recurring later maps to the same `canonical_key`
- [ ] Every assignment carries rationale, confidence, and an LLMRun reference
- [ ] `validity_status = confirmed` is unreachable by any automated path

#### Dependencies

- Phase 3.

#### Risks

- **Highest-risk phase.** Key granularity (over-merging vs fragmentation);
  matching mechanism undecided (possible embedding/vector dependency, which
  would need its own ADR).

#### Out of Scope

- Automatic merge/split; automated episode lifecycle; relation editing.

---

### Phase 5 - EvidencePack and trust rules

Status: Not started

#### Purpose

Make the product's central promise real: no material conclusion without
traceable, independence-aware evidence.

#### Expected Capabilities

- EvidencePack generation and versioning for every material narrative
  (ADR-0003).
- Independent-source counting distinct from raw source count; syndication
  detection.
- Evidence partitioned official / media / social / market; explicit
  `missing_evidence` and `evidence_gaps`.
- Deterministic language permissioning: market-pricing phrasing blocked while
  `market_evidence` is empty.
- Definition of "material narrative" settled.

#### Primary Vertical Slice

```text
Narrative state change -> rebuild EvidencePack (new version) -> independence-aware counts -> narrative gated on evidence
```

#### Completion Criteria

- [ ] Every material narrative has a current EvidencePack at end of cycle
- [ ] Ten syndicated copies of one report yield an independent source count of 1
- [ ] Forbidden market-language phrasing is rejected by an automated check
- [ ] Every evidence item resolves to a Document

#### Dependencies

- Phase 4.

#### Risks

- Independence detection accuracy; rebuild cost within the 5-minute budget.

#### Out of Scope

- Market data ingestion of any kind.

---

### Phase 6 - Instrument impact (NQ / BTC / GOLD)

Status: Not started

#### Purpose

Deliver the directional layer the trader actually acts on - explicitly and
auditably.

#### Expected Capabilities

- NarrativeInstrumentImpact per (narrative, instrument): relevance, direction,
  confidence, horizon, impact_channels, rationale, evidence_refs (ADR-0006).
- Enforcement that relevance is never keyword/entity-only.
- Tier B/C rules: no high-impact, high-confidence assessment without evidence.

#### Primary Vertical Slice

```text
Validated narrative + EvidencePack -> impact assessment per instrument -> validator -> stored with rationale and evidence refs
```

#### Completion Criteria

- [ ] Every non-neutral direction has non-empty rationale and evidence_refs
- [ ] `mixed`, `uncertain`, and `neutral` are produced distinctly and correctly
- [ ] No `sentiment_score` exists anywhere in the codebase

#### Dependencies

- Phase 5 (evidence must exist before impact may be claimed).

#### Risks

- Weak `impact_channels` reasoning producing plausible-sounding but unsupported
  directions.

#### Out of Scope

- Market-data confirmation of impact; any predictive claim.

---

### Phase 7 - Read path: API, dashboard, Morning Brief

Status: Not started

#### Purpose

First moment the product is usable by its actual user.

#### Expected Capabilities

- FastAPI read endpoints for brief, active narratives, instrument exposure,
  narrative detail (evidence, events, uncertainty, impact).
- Dashboard sections: Current Brief, Active Narratives, NQ/BTC/GOLD Exposure,
  Material Changes (feed shell, populated in Phase 8).
- Morning Brief job: on demand plus configurable schedule; sections Macro, NQ,
  BTC, GOLD, Watch Today; ranked by importance, not only directional impact.
- Navigation from any brief statement down to the source Document.

#### Primary Vertical Slice

```text
Stored state -> API -> dashboard -> user opens a narrative -> evidence -> source document
```

#### Completion Criteria

- [ ] A trader can answer the five Vision success questions from the dashboard
- [ ] Brief -> narrative -> evidence -> source document navigation works
      end-to-end
- [ ] Briefs are immutable snapshots

#### Dependencies

- Phase 6; frontend ADR from Phase 0.

#### Risks

- UI scope creep - charts, heatmaps, settings UI are explicit non-goals.

#### Out of Scope

- Candlestick charts, orderflow, heatmaps, settings UI, economic calendar UI.

---

### Phase 8 - Alerts

Status: Not started

#### Purpose

Support intraday alertness without a second delivery mechanism.

#### Expected Capabilities

- Alert rule evaluation inside the same 5-minute cycle (ADR-0004).
- Types: emerging_narrative, confirmed_narrative, narrative_acceleration,
  high_impact_event_added_to_narrative, conflicting_information,
  unconfirmed_social_hype (modelled but inert).
- Simple default thresholds; deduplication per (narrative, type, trigger).
- Alert written atomically with the state change that caused it (ADR-0005);
  in-app feed only, polled.

#### Primary Vertical Slice

```text
Cycle state change -> alert rule evaluation -> Alert row -> dashboard alert feed
```

#### Completion Criteria

- [ ] Alerts appear in the feed within one cycle of the triggering change
- [ ] Re-running a cycle does not duplicate alerts
- [ ] Every alert links to its narrative and triggering change

#### Dependencies

- Phase 7.

#### Risks

- Threshold tuning: alert fatigue vs missed material changes.

#### Out of Scope

- Telegram, email, webhooks; configurable-threshold UI.

---

### Phase 9 - Human overrides and audit

Status: Not started

#### Purpose

Make the user's corrections durable and the system's history reconstructible.

#### Expected Capabilities

- Controls: watch, mute, rename display title, mark irrelevant, mark invalid,
  reject event assignment, restore/undo.
- Override states `none` / `user_preferred` / `user_locked` with the ADR-0009
  semantics - protection changes the write path, never stops observation or
  alerting.
- A single choke point through which automated writes consult override state.
- Append-only AuditEntry on every human correction; proposal review surface.

#### Primary Vertical Slice

```text
User rejects an assignment -> AuditEntry written -> later cycles surface a re-assignment as a proposal, never silently
```

#### Completion Criteria

- [ ] A rejected mapping never silently returns
- [ ] `user_locked` decisions are unchanged by automation, while alerts on new
      evidence still fire
- [ ] Every human correction is reconstructible from the audit trail
- [ ] Undo/restore is itself audited

#### Dependencies

- Phase 7 (needs a UI); interacts with Phases 4 and 8.

#### Risks

- Missed override checks in a new automated write path - mitigated by the single
  choke point.

#### Out of Scope

- Merge/split, relation editing, `canonical_key` editing, episode management.

---

### Phase 10 - Cycle reliability, observability, deployment

Status: Not started

#### Purpose

Make the MVP something the user can actually run every morning.

#### Expected Capabilities

- Cycle run records, per-stage timing, per-source health, LLM cost and rejection
  rate visibility.
- Failure handling and resumability under real conditions; retention policy for
  `raw_output` and document bodies.
- Deployment to the chosen target with backups and secrets handling.
- MVP quality-gate verification pass against all seven gates in
  `PRODUCT_VISION.md` section 7.

#### Primary Vertical Slice

```text
Deployed system runs unattended for a week -> operator can see what ran, what failed, and what it cost
```

#### Completion Criteria

- [ ] Runs unattended across multiple sessions without manual intervention
- [ ] Cycle consistently completes inside the 5-minute window
- [ ] All seven Vision quality gates verified
- [ ] Backup and restore exercised at least once

#### Dependencies

- Phases 2-9; hosting ADR from Phase 0.

#### Risks

- Cycle duration approaching the interval - the response is narrower scoping,
  not a second cadence (would supersede ADR-0004).

#### Out of Scope

- Horizontal scale, HA, multi-user.

---

## 5. Post-MVP Track (Vision section 20)

Direction only - not sequenced or committed. Each becomes a phase after
evidence from the MVP.

1. **Social Intelligence** - X adapter, Reddit adapter, social source quality,
   social velocity, SocialSentiment as an input signal (activates the dormant
   `unconfirmed_social_hype` alert and Tier 4 sources).
2. **Narrative Governance** - merge/split UI, relation editing, `canonical_key`
   editing, stronger audit workflows (the remedy for Phase 4 key-quality
   mistakes).
3. **Narrative Episodes** - automatic reactivation detection, peak detection,
   episode comparison.
4. **Market Data Confirmation** - OHLCV, rates/yields, market-derived evidence,
   market-language permissioning (unlocks the phrasing forbidden in Phase 5).
5. **Research Platform** - sentiment/impact vs returns, narrative episodes vs
   volatility, mention velocity vs market behaviour.
6. **Delivery Channels** - Telegram, email, webhooks.
7. **Advanced Infrastructure** - distributed processing and Kafka, only when
   real throughput or decoupling requirements justify it (would supersede
   ADR-0005).

## 6. Deferred Capabilities

Deliberately not built, with the reason (see `PRODUCT_VISION.md` section 6):
generic sentiment scoring, market prediction, trading signals, custom ML models,
full Claim/Fact graph, automatic merge/split, automated episode lifecycle,
multi-cadence scheduling, event-driven low-latency source processing, external
delivery channels, charting and settings UI.

## 7. Roadmap Review Rules

Review after each phase completes, after a significant architectural decision,
when evidence contradicts an assumption, and before planning the next phase.

## 8. Sequencing Notes and Risks

- **Phase 4 is the make-or-break phase.** Consider a spike inside Phase 3 or a
  dedicated research wave before committing to a candidate-matching mechanism.
- **Phases 5 and 6 are strictly ordered.** Impact may not be claimed before
  evidence exists - reversing them would violate ADR-0003.
- **Phase 9 could be pulled earlier** if the trader wants correction ability
  before alerts; the current order optimizes for having something worth
  correcting first.
- **Phases 0-2 could be one sprint** (foundation + first real data), which is
  the natural candidate for Sprint 001 once the roadmap and the four open ADRs
  are approved.
