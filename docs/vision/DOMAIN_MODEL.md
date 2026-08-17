# Domain Model

Status: Accepted
Approved by:
Approval date:

Derived from `docs/MVP_Vision_Architecture_Decisions.md` sections 5-7 and 17.
This is a conceptual model - not a database schema and not an API contract.

## 1. Purpose

The shared, durable model of the Market Intelligence Platform's concepts. Code,
documents, and conversation use these names identically. Field lists below are
indicative of *meaning*, not of column layout.

## 2. Bounded Contexts

| Context | Responsible for | Boundary (what it does NOT cover) |
|---|---|---|
| **Ingestion** | Source registry and tiering, fetching, normalizing, deduplicating, and persisting Documents | Does not interpret content; does not extract events; does not judge evidential strength |
| **Event Extraction** | Turning Documents into Events, with embedded `extracted_facts` and `source_claims` | Does not decide narrative membership; does not assess instruments |
| **Narrative Intelligence** | Narrative identity, lifecycle, validity, dynamics, event assignment, relations, episodes | Does not fetch sources; does not render UI; does not deliver alerts |
| **Evidence & Trust** | EvidencePack construction, independent-source counting, evidence gaps, epistemic classification, language permissioning | Does not decide narrative lifecycle; does not call sources |
| **Instrument Impact** | Explicit, auditable Narrative-to-Instrument impact assessments for NQ/BTC/GOLD | Does not price anything, does not predict, does not produce trading signals |
| **Delivery** | Morning Brief, dashboard read models, alert feed | Does not create or modify domain state |
| **Governance & Audit** | Human overrides, override states, audit trail, LLM run records | Does not itself make domain decisions - it records and constrains them |

Language note: **"Event"** means *a real-world development extracted from
documents* in Event Extraction and Narrative Intelligence. It never means a
software/domain event in the messaging sense - use "processing cycle step" for
that. **"Confidence"** means model/validator confidence in Narrative
Intelligence and Instrument Impact, and is never a probability of a market
outcome.

## 3. Core Entities

### Ingestion

#### Source
- **Identity:** stable source key (e.g. `fed_fomc`, `bls`, `sec_edgar`).
- **Key attributes:** name, source_type, `tier` (1 primary/official, 2
  professional reporting, 3 specialist/research, 4 social), publisher/owner,
  endpoint config, active flag.
- **Invariants:**
  - Every Source has exactly one tier.
  - Tier and source independence are inputs to evidence quality; a Source
    cannot be used as evidence without a tier.
  - Sources sharing an originating publisher are not independent of each other.

#### Document
- **Identity:** system id; natural key is (source, source-native id or URL +
  published timestamp) for deduplication.
- **Key attributes:** source, source_type, published_at, collected_at, title,
  body or content reference, url, language, raw_metadata, processing_status.
- **Invariants:**
  - **Immutable after collection.** Re-fetching a changed page creates a new
    Document, it does not overwrite the old one.
  - `collected_at >= published_at` is expected; a violation is a data-quality
    flag, not a silent correction.
  - A Document always belongs to exactly one Source.
  - `processing_status` advances monotonically through the pipeline; a document
    cannot silently regress to unprocessed.

### Event Extraction

#### Event
- **Identity:** system id. An Event is *not* identified by its source Document -
  one Event may be supported by several Documents, and one Document may yield
  several Events.
- **Key attributes:** type, title, occurred_at, entities, topics,
  `extracted_facts`, `source_claims`, source_ids, confidence.
- **Invariants:**
  - At least one source Document (`source_ids` is never empty).
  - `extracted_facts` and `source_claims` are kept **separate** - a claim is
    never promoted to a fact by the extractor (ADR-0008).
  - Every Event traces back to text in a stored Document.

### Narrative Intelligence

#### Narrative (primary product object)
- **Identity:** `canonical_key` - a **semantic, human-readable, stable**
  identifier (`fed_rate_cut_expectations`, `btc_regulatory_pressure`,
  `ai_capex_consequences`, `gold_safe_haven_demand`). Not a cluster hash
  (ADR-0001) and **not** an embedding.
- **Key attributes:** display_title, validity_status, lifecycle_status,
  economic_mechanism, market_interpretation, category, entities, topics,
  attention_score, strength, velocity, momentum, confidence, first_seen,
  last_seen, updated_at, uncertainty_reasons, contradiction_signals,
  override_state, **identity_embedding** (see IdentityEmbedding below).
- **Invariants:**
  - `canonical_key` is unique and durable; changing it is a Tier C decision
    (post-MVP, human-only).
  - A Narrative always has an `economic_mechanism` and a
    `market_interpretation` - a bare topic/cluster is not a Narrative.
  - A Narrative considered *material* must have a current EvidencePack.
  - `validity_status = confirmed` is never set by an LLM (ADR-0002).
  - While `override_state = user_locked`, automated changes to the protected
    decision become proposals, never silent writes (ADR-0009).
  - `first_seen <= last_seen`; `last_seen` is derived from assigned
    NarrativeEvents, not written arbitrarily.
  - **`identity_embedding` is derived, recomputable, and never authoritative.**
    It is written in the same transaction as the identity text it is derived
    from; if it is missing or stale, the Narrative is still valid - only
    retrieval degrades (ADR-0014).

#### NarrativeEpisode
- **Identity:** system id, scoped to one Narrative; ordered by activity period.
- **Key attributes:** narrative_id, started_at, ended_at, notes.
- **Invariants:**
  - Episodes of one Narrative do not overlap in time.
  - **MVP:** exists in the model but is not automatically managed - manual or
    trivial-case creation only. No automatic peak/end/reactivation detection.

#### NarrativeEvent (assignment)
- **Identity:** the (narrative, event) pair.
- **Key attributes:** assignment rationale, assignment confidence, assignment
  status (`accepted` / `proposed` / `rejected`), source LLM run reference,
  candidate shortlist reference (the retrieved candidates and their similarity
  scores that were considered).
- **Invariants:**
  - An Event may be assigned to an existing Narrative only when **all three**
    hold: same economic mechanism; similar affected instruments/exposures; it
    strengthens, weakens, or updates the same market interpretation.
  - **Similarity may narrow or block, never decide.** Embedding retrieval
    produces the shortlist; the three-condition rule plus the validation layer
    produce the assignment (ADR-0014, ADR-0002).
  - A human-rejected assignment must not silently return - a later automated
    re-assignment appears as a proposal (Vision quality gate).
  - An assignment always references the LLM run that produced it (ADR-0007).

#### NarrativeRelation
- **Identity:** (source narrative, target narrative, relation type).
- **Relation types:** `related_to`, `causes`, `contributes_to`, `contradicts`,
  `parent_of`, `merged_into`.
- **Invariants:**
  - No self-relations.
  - `causes`, `contributes_to`, `parent_of`, `merged_into` are directional;
    `related_to` and `contradicts` are symmetric in meaning.
  - Relations exist so that Narratives are **not prematurely merged**;
    automatic merge/split is out of scope for MVP.

### Evidence & Trust

#### EvidencePack
- **Identity:** (narrative_id, evidence_version) - a **snapshot**, superseded
  rather than edited.
- **Key attributes:** supporting_evidence, contradicting_evidence,
  top_supporting_events, key_facts, source_count, source_diversity,
  `independent_source_count`, strongest_sources, dissenting_sources,
  official_evidence, media_evidence, social_evidence, market_evidence,
  missing_evidence, evidence_gaps, generated_at, evidence_version.
- **Invariants:**
  - Every material Narrative has exactly one current EvidencePack (ADR-0003).
  - `independent_source_count <= source_count`; syndicated repetition of one
    originating report contributes **one** independent source.
  - Every evidence item traces to a Document or an Event that traces to a
    Document.
  - `market_evidence` is empty in MVP (no market data feed) - and empty
    `market_evidence` forbids market-pricing language downstream.
  - An EvidencePack is never mutated in place; a rebuild produces a new
    `evidence_version`.

### Instrument Impact

#### NarrativeInstrumentImpact
- **Identity:** (narrative_id, instrument) - one current assessment per pair.
- **Key attributes:** relevance, direction, confidence, horizon,
  impact_channels, rationale, evidence_refs.
- **Invariants:**
  - Instrument relevance is **never** inferred solely from entity or keyword
    presence (ADR-0006), and never from embedding similarity alone (ADR-0014).
  - `rationale` and non-empty `evidence_refs` are mandatory for any non-neutral
    direction.
  - A high-confidence, high-impact assessment is never finalized by an LLM
    without evidence (Tier C).
  - `instrument` is one of the tracked set: NQ, BTC, GOLD.

### Delivery

#### Alert
- **Identity:** system id; deduplicated per (narrative, alert_type, triggering
  change) so a repeated cycle does not re-fire.
- **Types:** `emerging_narrative`, `confirmed_narrative`,
  `narrative_acceleration`, `high_impact_event_added_to_narrative`,
  `conflicting_information`, `unconfirmed_social_hype` (the last is modelled but
  inert until social sources exist).
- **Invariants:** every Alert references the Narrative and the change that
  triggered it; alerts are generated inside the 5-minute cycle (ADR-0004);
  in-app delivery only (ADR-0005).

#### Brief (Morning Market Brief)
- **Identity:** generation timestamp (+ on-demand vs scheduled).
- **Structure:** Macro / Cross-Market, NQ, BTC, GOLD, Watch Today.
- **Invariants:** a Brief is an immutable snapshot of the state it was
  generated from; every statement is traceable to a Narrative and its
  EvidencePack; instrument sections contain only Narratives material to that
  instrument; ranking is by importance, not only directional impact.

### Governance & Audit

#### LLMRun
- **Identity:** system id.
- **Key attributes:** task_type, provider, model, model_version,
  prompt_version, system_prompt_version, input_hash, input_reference_ids,
  output_schema_version, raw_output, parsed_output, validation_status,
  validation_errors, temperature, inference_parameters, token_usage, latency,
  created_at.
- **Invariants:** append-only; `input_hash` alone is insufficient -
  `input_reference_ids` (or a snapshot) must be present; every material domain
  decision produced by an LLM references its LLMRun (ADR-0007). Where retrieval
  preceded the call, the candidate shortlist and scores are part of the
  recorded input (ADR-0014).

#### AuditEntry
- **Identity:** system id.
- **Key attributes:** actor, action, target_id, previous_value, new_value,
  timestamp, reason.
- **Invariants:** append-only; every human correction produces exactly one
  entry; `previous_value` is the state actually replaced, not a reconstruction.

## 4. Value Objects

| Value object | Attributes / values | Used by |
|---|---|---|
| SourceTier | 1 primary/official, 2 professional reporting, 3 specialist/research, 4 social | Source, EvidencePack |
| ValidityStatus | `candidate`, `supported`, `confirmed`, `disputed`, `invalid`, `rejected` | Narrative |
| LifecycleStatus | `emerging`, `active`, `fading`, `dormant`, `resolved` (deliberately excludes `accelerating`, `dominant`, `recurring` - those are other dimensions) | Narrative |
| NarrativeDynamics | `attention_score` (current attention: source count, events, recency, source quality), `strength` (how strongly evidence supports the interpretation), `velocity` (rate of new evidence/events/mentions - a first derivative), `momentum` (persistence and direction of change across multiple windows, not one window-over-window diff) | Narrative |
| IdentityEmbedding | vector of the narrative's identity text, plus `embedding_model` and `embedding_version`. Derived, recomputable, non-authoritative - used for retrieval only (ADR-0014) | Narrative |
| ImpactDirection | `strongly_bearish`, `bearish`, `mixed`, `neutral`, `bullish`, `strongly_bullish`, `uncertain`. `mixed` = credible channels point opposite ways; `uncertain` = not enough evidence to determine direction; `neutral` = reason to believe impact is limited/non-directional | NarrativeInstrumentImpact |
| ImpactHorizon | `intraday` (current session or next several hours), `multi_day` (beyond one session), `unknown` (insufficient evidence) | NarrativeInstrumentImpact |
| OverrideState | `none`, `user_preferred`, `user_locked` | Narrative, NarrativeEvent |
| CandidateStatus | `accepted`, `proposed`, `rejected` (output of the validation layer) | NarrativeEvent, NarrativeRelation, NarrativeInstrumentImpact, Narrative creation |
| EpistemicCategory | `observed_fact`, `source_claim`, `model_inference`, `system_metric`, `market_evidence` | EvidencePack, Brief, Event |
| EvidenceRef | pointer to Document / Event / fact within an extraction result | EvidencePack, NarrativeInstrumentImpact |
| Instrument | `NQ`, `BTC`, `GOLD` (closed set in MVP) | NarrativeInstrumentImpact, Brief, Dashboard |
| RelationType | `related_to`, `causes`, `contributes_to`, `contradicts`, `parent_of`, `merged_into` | NarrativeRelation |

## 5. Aggregates

| Aggregate | Aggregate root | Includes | Invariants guarded at the boundary |
|---|---|---|---|
| Source Feed | Source | fetch config, tier | one tier per source; independence grouping by originating publisher |
| Document | Document | raw metadata, content ref, processing status | immutability after collection; deduplication against the same source |
| Event | Event | extracted_facts, source_claims, source_ids | at least one source document; facts and claims stay separate |
| Narrative | Narrative | NarrativeEpisode(s), NarrativeEvent assignments, override_state, identity embedding | unique `canonical_key`; mechanism + interpretation present; three-condition assignment rule; `confirmed` never LLM-set; `user_locked` protection; embedding written with its source text and never treated as identity |
| EvidencePack | EvidencePack | evidence items, counts, gaps, version | immutable snapshot; `independent_source_count <= source_count`; full traceability; empty `market_evidence` blocks market language |
| Instrument Impact | NarrativeInstrumentImpact | channels, rationale, evidence_refs | one current assessment per (narrative, instrument); rationale + evidence mandatory; no keyword-only relevance |
| Alert | Alert | trigger reference, type | deduplicated per (narrative, type, trigger); generated only inside the cycle |
| Brief | Brief | instrument sections, watch list | immutable snapshot; every statement traceable |
| LLM Run | LLMRun | prompt/model/parameter versions, raw and parsed output, validation result | append-only; input references present |
| Audit Trail | AuditEntry | actor, action, before/after, reason | append-only; one entry per human correction |

**Cross-aggregate rule:** Narrative and EvidencePack are separate aggregates and
are consistent only *eventually* - a Narrative may briefly reference a stale
EvidencePack during a cycle. The materiality invariant ("every material
narrative has a current EvidencePack") is enforced at the **end of the
processing cycle** and at read time in Delivery, not inside a single
transaction.

## 6. Human Override Model

MVP controls: `watch`, `mute`, `rename display title`, `mark irrelevant`,
`mark invalid`, `reject event assignment`, `restore / undo override`.

Post-MVP: merge narratives, split narrative, edit relations, change
`canonical_key`, episode management.

Semantics:

- `none` - the system may change the decision automatically.
- `user_preferred` - the user's value is preferred; automated changes need a
  stronger justification and are surfaced.
- `user_locked` - the system **must not** automatically change the protected
  domain decision.
- **Override never means "stop observing the world."** The system keeps
  detecting and alerting on new evidence; protected mappings simply become
  proposals rather than silent changes.
- Every human correction writes an AuditEntry (ADR-0009).

## 7. Ubiquitous Language

| Term | Definition | Context |
|---|---|---|
| Source | An external data origin with an explicit trust tier | Ingestion, Evidence |
| Document | Normalized, immutable raw input from a Source | Ingestion |
| Event | A real-world development extracted from one or more Documents | Event Extraction, Narrative Intelligence |
| Extracted fact | Something the document states as observed fact | Event Extraction, Evidence |
| Source claim | Something a source asserts or interprets, not an observed fact | Event Extraction, Evidence |
| Narrative | A market interpretation with an economic mechanism, exposures, evidence, lifecycle, validity, and durable identity | Narrative Intelligence (product core) |
| Canonical key | Stable semantic identifier of a Narrative over time | Narrative Intelligence |
| Identity embedding | The derived vector of a Narrative's identity text, used to retrieve match candidates - never the identity itself | Narrative Intelligence |
| Candidate shortlist | The small set of existing Narratives returned by embedding retrieval for a given incoming candidate, with scores | Narrative Intelligence, Governance |
| Narrative episode | A distinct period of activity of a recurring Narrative | Narrative Intelligence |
| Economic mechanism | The causal channel by which the narrative would affect markets | Narrative Intelligence, Instrument Impact |
| Market interpretation | What the narrative means for markets, as read from evidence | Narrative Intelligence |
| Attention score / Strength / Velocity / Momentum | See NarrativeDynamics above - four distinct dimensions, never collapsed into one "score" | Narrative Intelligence |
| EvidencePack | Standardized, versioned snapshot of evidence supporting/contradicting a Narrative | Evidence & Trust |
| Independent source | A source whose reporting does not derive from another counted source's originating report | Evidence & Trust |
| Material narrative | A Narrative significant enough to appear in Brief/Dashboard - and therefore required to carry an EvidencePack | Evidence, Delivery |
| Instrument impact | An explicit, auditable relation between a Narrative and NQ/BTC/GOLD with direction, horizon, rationale, evidence | Instrument Impact |
| Impact channel | The concrete transmission route from narrative to instrument (e.g. rates -> discount rate -> NQ multiples) | Instrument Impact |
| Candidate | An LLM output not yet through the validation layer | All LLM-touching contexts |
| Validation layer | Deterministic rules turning a candidate into accepted / proposed / rejected | Governance |
| Override state | Degree of human protection over a domain decision | Governance |
| LLM run | The audit record of one material model invocation | Governance |
| Brief | The Morning Market Brief snapshot | Delivery |
| Alert | An in-app notification of a material change | Delivery |

Deliberately **absent** from the language: `sentiment_score`, "prediction",
"signal", "forecast". Their appearance in code or docs is a model drift and
should be logged in `docs/planning/TECHNICAL_DEBT.md`.

## 8. Open Modeling Questions

- **Materiality threshold** - "material narrative" gates the EvidencePack
  requirement, but no definition (attention/strength threshold? instrument
  relevance? human flag?) exists in the source document.
- **Independence determination** - the rule ("syndication doesn't count twice")
  is fixed, but the mechanism (publisher graph, byline/wire detection, text
  similarity) is not decided.
- **Narrative candidate matching** - *mechanism resolved* (ADR-0014: embedding
  retrieval shortlist + LLM judgement + deterministic validation). Still open,
  and settled in Phase 4 rather than Phase 1: exactly which text is embedded
  for a Narrative's identity and for an incoming candidate, the top-k and
  similarity floor, and the embedding model source (the last requires a human
  decision - it may be a paid dependency).
- **Attention/strength/velocity/momentum formulas** - semantics are fixed,
  computation windows and weights are not.
- **Contradiction detection** - `contradicts` relations and
  `contradiction_signals` exist, but the detection trigger is undefined.

## 9. Related ADRs

ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0008, ADR-0009,
ADR-0010, ADR-0014 - see `docs/adr/README.md`.

## 10. Review Rules

Update when a new bounded context or aggregate appears, or when the model stops
reflecting the reality of the code. A bounded-context split or aggregate change
deserves its own ADR.
