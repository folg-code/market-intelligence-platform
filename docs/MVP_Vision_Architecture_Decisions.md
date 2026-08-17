# Market Intelligence Platform - MVP Vision & Architecture Decisions

## 1. Product Vision

The MVP is not a sentiment-analysis system.

It is an evidence-backed market narrative intelligence system that detects material market narratives, explains why they matter, and estimates narrative-specific impact on selected instruments.

The system should help a discretionary/research trader answer, faster than manual source reading:

- what important market narratives are active,
- what changed recently,
- which narratives may matter for NQ, BTC, and GOLD,
- what evidence supports each conclusion,
- and where the system is uncertain.

The product must prioritize traceability, epistemic discipline, and decision support over prediction.

## 2. MVP User

The target user is a discretionary/research trader.

The MVP should support:

- morning market preparation,
- intraday alertness,
- narrative awareness,
- fast review of material source-driven changes,
- and auditability of system conclusions.

## 3. MVP Problem

The MVP should prove one thing:

Can the system detect a material narrative for NQ, BTC, or GOLD from reliable sources and present a short, auditable intelligence view faster than manual source reading?

The first value moments are:

- "I can see what is really moving the market today."
- "I can see which narratives are emerging before they become obvious."

## 4. Core User Flow

1. The user opens the dashboard.
2. The dashboard shows the current market brief.
3. The user reviews active narratives.
4. The user checks NQ, BTC, and GOLD narrative exposure.
5. The user reviews material changes and alerts.
6. The user opens a narrative to inspect evidence, events, uncertainty, and instrument impact.
7. The user can correct the system by watching, muting, renaming, marking invalid/irrelevant, or rejecting event assignments.

The user should be able to understand why the system reached a conclusion without rereading every source document.

## 5. Domain Model

### Source

Represents an external data origin.

Sources should have explicit tiers:

- Tier 1: primary / official sources.
- Tier 2: professional reporting.
- Tier 3: specialist / research sources.
- Tier 4: social sources.

Source tier and source independence must feed into evidence quality.

### Document

Represents normalized raw input from a source.

Documents preserve:

- source,
- source type,
- published timestamp,
- collected timestamp,
- title,
- body or content reference,
- URL,
- language,
- raw metadata,
- processing status.

Raw source data should remain immutable whenever possible.

### Event

Represents a real-world development extracted from one or more documents.

For MVP, facts and claims remain embedded in the event extraction result rather than becoming full standalone tables.

Suggested fields:

- id
- type
- title
- occurred_at
- entities
- topics
- extracted_facts
- source_claims
- source_ids
- confidence

This preserves epistemic separation without overbuilding a full claim graph.

### Narrative

The main product object.

A narrative is not merely a topic or cluster. It is a market interpretation with continuity over time:

- economic mechanism,
- related exposures/instruments,
- market interpretation,
- evidence,
- lifecycle,
- validity,
- and identity.

Suggested fields:

- id
- canonical_key
- display_title
- validity_status
- lifecycle_status
- economic_mechanism
- market_interpretation
- category
- entities
- topics
- attention_score
- strength
- velocity
- momentum
- confidence
- first_seen
- last_seen
- updated_at
- uncertainty_reasons
- contradiction_signals
- override_state

### NarrativeEpisode

NarrativeEpisode should exist in the schema from the beginning, but it should not be an active automated MVP feature.

It allows recurring narratives to share one canonical identity while having separate periods of activity.

MVP behavior:

- optional,
- manually created or created only in simple cases,
- no automatic peak/end/reactivation detection.

Post-MVP behavior:

- automatic episode lifecycle,
- reactivation detection,
- peak detection,
- comparison with previous episodes.

### NarrativeEvent

Associates events with narratives.

An event should be assigned to an existing narrative only when all three conditions hold:

- it shares the same economic mechanism,
- it affects a similar set of instruments or exposures,
- it strengthens, weakens, or updates the same market interpretation.

### NarrativeRelation

Narratives should support relationships rather than forcing premature merges.

Required relation types:

- related_to
- causes
- contributes_to
- contradicts
- parent_of
- merged_into

Merge/split UI is not part of MVP.

### EvidencePack

Every material narrative must have an EvidencePack.

EvidencePack is a standardized snapshot of the evidence used to assess a narrative.

Suggested fields:

- supporting_evidence
- contradicting_evidence
- top_supporting_events
- key_facts
- source_count
- source_diversity
- independent_source_count
- strongest_sources
- dissenting_sources
- official_evidence
- media_evidence
- social_evidence
- market_evidence
- missing_evidence
- evidence_gaps
- generated_at
- evidence_version

Independent source count is critical. Ten articles repeating one originating report must not count as ten independent confirmations.

### NarrativeInstrumentImpact

Replaces generic sentiment as the MVP's main directional concept.

Suggested fields:

- narrative_id
- instrument
- relevance
- direction
- confidence
- horizon
- impact_channels
- rationale
- evidence_refs

Instrument relevance must never be inferred solely from entity or keyword presence.

Every material instrument association should be represented as an explicit, auditable relation between a narrative and an instrument.

## 6. Narrative Model

### Identity

Narrative identity is semantic, not cluster-hash-based.

`canonical_key` should be a stable semantic identifier, such as:

- fed_rate_cut_expectations
- btc_regulatory_pressure
- ai_capex_consequences
- gold_safe_haven_demand

Cluster hashes may identify technical clusters, but they do not define narrative identity over time.

### Validity

Validity answers: how well supported is this narrative as a market interpretation?

MVP enum:

- candidate
- supported
- confirmed
- disputed
- invalid
- rejected

For MVP, `disputed` can be an enum value. Later, the model may split this into separate `support_level` and `conflict_level`.

### Lifecycle

Lifecycle answers: where is this narrative in its life cycle?

Recommended MVP enum:

- emerging
- active
- fading
- dormant
- resolved

Do not include `accelerating`, `dominant`, or `recurring` as lifecycle statuses in MVP. Those describe other dimensions.

### Dynamics

Recommended metric semantics:

- `attention_score`: how much current attention the narrative receives, including source count, events, recency, and source quality.
- `strength`: how strongly available evidence supports the narrative as a coherent market interpretation.
- `velocity`: rate at which new evidence, events, or mentions appear.
- `momentum`: persistence and direction of metric changes across multiple windows.

`velocity` is a first derivative. `momentum` is persistence of change, not just one window-over-window difference.

## 7. Instrument Impact Direction

MVP should not use generic sentiment score as a primary concept.

Instead, use instrument impact direction.

Direction enum:

- strongly_bearish
- bearish
- mixed
- neutral
- bullish
- strongly_bullish
- uncertain

Semantics:

- `mixed`: credible impact channels point in opposing directions.
- `uncertain`: the system lacks enough evidence to determine direction.
- `neutral`: the system has reason to believe impact is limited or non-directional.

Horizon enum for MVP:

- intraday
- multi_day
- unknown

Definitions:

- `intraday`: expected relevance within the current session or the next several hours.
- `multi_day`: expected relevance beyond one session.
- `unknown`: insufficient evidence to estimate horizon.

## 8. LLM Decision Boundaries

LLMs are analytical components, not sources of truth.

The MVP pipeline should follow:

```text
LLM output
-> candidate
-> validation layer
-> accepted / proposed / rejected
```

LLMs may independently perform low-risk semantic transformations:

- entity extraction,
- topic classification,
- candidate event extraction,
- candidate economic mechanism,
- candidate market interpretation,
- relation candidate generation,
- uncertainty reason generation,
- summary generation.

LLMs may propose, but not automatically finalize:

- event-to-narrative assignment,
- creation of a new narrative,
- instrument relevance,
- instrument direction,
- narrative relations,
- canonical mapping changes.

LLMs must not automatically finalize:

- validity_status = confirmed,
- merge,
- split,
- changes to user_locked decisions,
- high-confidence/high-impact instrument impact without evidence,
- durable changes to semantic narrative identity.

Many decisions do not require a human. They may be automatically accepted by deterministic validation rules when confidence and evidence requirements are satisfied.

## 9. Evidence & Trust Rules

Core rules:

- No material conclusion without an EvidencePack.
- No EvidencePack without source traceability.
- No market claim without evidence from the corresponding market data domain.

The system must distinguish:

- observed facts,
- source claims,
- model inference,
- system-derived metrics,
- market-derived evidence.

Generated language must never imply a stronger level of evidence than the underlying data supports.

Without market data, the system must not write:

- "Markets are pricing in..."
- "Market pricing suggests..."
- "Options pricing reflects..."

When only news/social/source commentary is available, use language such as:

- "Financial commentary increasingly expects..."
- "Monitored sources increasingly frame this as..."
- "Discussion is shifting toward..."
- "The dominant interpretation among monitored sources is..."

Market-pricing language is allowed only when supported by market data.

## 10. LLM Run Reproducibility

Every material LLM run should store metadata sufficient for later audit and evaluation.

Suggested model:

- id
- task_type
- provider
- model
- model_version
- prompt_version
- system_prompt_version
- input_hash
- input_reference_ids
- output_schema_version
- raw_output
- parsed_output
- validation_status
- validation_errors
- temperature
- inference_parameters
- token_usage
- latency
- created_at

`input_hash` is not enough for reproducibility. The system also needs input references or input snapshots.

The system should be able to answer:

Why did the system assign this event to this narrative on a given date?

And retrieve:

- input,
- prompt version,
- model,
- raw output,
- parsed result,
- validator result.

## 11. MVP Pipeline

MVP pipeline:

```text
Sources
-> Documents
-> Event Extraction
   - extracted_facts
   - source_claims
-> Events
-> Narrative Candidates
-> EvidencePack
-> Validated Narratives
-> Instrument Impact
-> Brief / Alerts / Dashboard
```

The MVP should not build full standalone Claim and Fact models.

## 12. Data Sources

Tracked instruments:

- NQ
- BTC
- GOLD

MVP sources:

- Federal Reserve / FOMC
- BLS
- SEC
- two or three selected news/RSS sources

Potential later additions:

- selected company IR for large NQ components,
- crypto exchange announcements,
- specialist research sources,
- X,
- Reddit.

Social intelligence is post-MVP.

## 13. Processing Cadence

Use one simple processing cycle for MVP.

Every 5 minutes:

1. ingest new documents,
2. extract events,
3. update narrative candidates,
4. rebuild affected EvidencePacks,
5. recalculate narrative state,
6. evaluate alert rules.

Alerts are generated during the same processing cycle.

Morning brief is a separate job:

- generated on demand,
- generated on configurable schedule.

Do not introduce multiple staggered scheduler cadences in MVP.

## 14. Dashboard

MVP dashboard sections:

- Current Brief
- Active Narratives
- NQ / BTC / GOLD Exposure
- Material Changes / Alert Feed

The dashboard should answer:

- what dominates,
- what it affects,
- what requires attention now.

The main object on the dashboard is the narrative.

Avoid MVP scope creep:

- no candlestick charts,
- no orderflow,
- no heatmaps,
- no complex settings UI,
- no full economic calendar UI.

## 15. Briefing

The first briefing should be one Morning Market Brief with instrument sections.

Structure:

1. Macro / Cross-Market
2. NQ
3. BTC
4. GOLD
5. Watch Today

The briefing should include important macro narratives even when directional impact is unclear.

Top Market Narratives should be ranked by importance, not only by directional impact.

Instrument Impact sections should show only narratives material to NQ, BTC, or GOLD.

## 16. Alerts

MVP alert channel:

```text
Alert -> PostgreSQL -> FastAPI -> Dashboard alert feed
```

Only in-app alerts are required for MVP.

Initial alert types:

- emerging_narrative
- confirmed_narrative
- narrative_acceleration
- high_impact_event_added_to_narrative
- conflicting_information
- unconfirmed_social_hype

Even if social intelligence is post-MVP, keeping the alert type in the model is acceptable.

Alert thresholds should eventually be configurable, but MVP can start with simple defaults.

## 17. Human Overrides

MVP human controls:

- watch
- mute
- rename display title
- mark irrelevant
- mark invalid
- reject event assignment
- restore / undo override

Post-MVP controls:

- merge narratives
- split narrative
- edit relations
- change canonical_key
- episode management

Every human correction should create an audit entry.

Suggested audit model:

- actor
- action
- target_id
- previous_value
- new_value
- timestamp
- reason

Override states:

- none
- user_preferred
- user_locked

`user_locked` means the system cannot automatically change the protected domain decision.

Override must not mean "stop observing the world." The system may still detect and alert on new evidence, but protected mappings become proposals rather than silent changes.

## 18. Explicit Non-Goals

Not MVP:

- X sentiment,
- Reddit sentiment,
- generic sentiment_score,
- market prediction,
- automated trading signals,
- Kafka,
- custom ML models,
- automatic narrative merge/split,
- merge/split UI,
- full Claim/Fact graph,
- automated NarrativeEpisode lifecycle,
- market-data confirmation,
- sentiment research,
- backtesting,
- Telegram/email/webhook alerts,
- complex multi-cadence scheduling,
- low-latency event-driven official-source processing.

## 19. MVP Success Criteria

### Product Success

The MVP is successful if a discretionary/research trader can open the dashboard and answer within a few minutes:

- what important things happened,
- which narratives are active,
- what may matter for NQ, BTC, and GOLD,
- what changed recently,
- and what evidence supports the system's view.

Minimum product capabilities:

- automatic source ingestion,
- event extraction,
- narrative grouping,
- EvidencePack generation,
- instrument impact assessment,
- current brief,
- active narratives,
- alert feed,
- human correction.

### Quality Gates

Required quality gates:

- every material narrative has traceable evidence,
- every directional impact has rationale and evidence,
- unsupported market-language claims are prohibited,
- the user can navigate from briefing to source document,
- manually rejected mappings do not silently return,
- syndicated articles do not count as independent evidence,
- the user can understand the system's conclusion without rereading every source.

## 20. Post-MVP Roadmap

Likely post-MVP milestones:

1. Social Intelligence
   - X adapter
   - Reddit adapter
   - social source quality
   - social velocity
   - SocialSentiment as input signal

2. Narrative Governance
   - merge/split UI
   - relation editing
   - canonical_key editing
   - stronger audit workflows

3. Narrative Episodes
   - automatic reactivation detection
   - peak detection
   - episode comparison

4. Market Data Confirmation
   - OHLCV
   - rates/yields where applicable
   - market-derived evidence
   - market-language permissioning

5. Research Platform
   - sentiment/impact vs returns
   - narrative episodes vs volatility
   - mention velocity vs market behavior

6. Delivery Channels
   - Telegram
   - email
   - webhooks

7. Advanced Infrastructure
   - distributed processing only when scale justifies it
   - Kafka only when real throughput or decoupling requirements justify it

