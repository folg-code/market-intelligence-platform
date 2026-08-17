# Product Vision

Status: Accepted
Approved by:
Approval date:

Source: extracted and restated from `docs/MVP_Vision_Architecture_Decisions.md`
(sections 1-4, 12-19). That document remains the historical discovery record;
this file is the durable product-level truth.

## 1. Purpose

The Market Intelligence Platform is an **evidence-backed market narrative
intelligence system** - not a sentiment-analysis system.

It detects material market narratives, explains why they matter, and estimates
narrative-specific impact on a fixed set of instruments (NQ, BTC, GOLD).

It exists to help a discretionary/research trader answer, faster than manual
source reading:

- what important market narratives are active,
- what changed recently,
- which narratives may matter for NQ, BTC, and GOLD,
- what evidence supports each conclusion,
- where the system is uncertain.

The product prioritizes **traceability, epistemic discipline, and decision
support over prediction**.

## 2. Problem & Users

### User

A single discretionary/research trader (the MVP is single-user).

### Jobs the product supports

- morning market preparation,
- intraday alertness,
- narrative awareness,
- fast review of material source-driven changes,
- auditability of system conclusions.

### Today, without the product

The trader reads primary sources (Fed/FOMC, BLS, SEC) and news feeds manually,
reconstructs the day's narratives in their head, and has no durable record of
which evidence supported which interpretation, or of how a narrative evolved.
Syndicated repetition of a single originating report is easily mistaken for
independent confirmation.

### The one thing the MVP must prove

> Can the system detect a material narrative for NQ, BTC, or GOLD from reliable
> sources and present a short, auditable intelligence view faster than manual
> source reading?

First value moments:

- "I can see what is really moving the market today."
- "I can see which narratives are emerging before they become obvious."

## 3. Core User Flow

1. The user opens the dashboard.
2. The dashboard shows the current market brief.
3. The user reviews active narratives.
4. The user checks NQ / BTC / GOLD narrative exposure.
5. The user reviews material changes and alerts.
6. The user opens a narrative to inspect evidence, events, uncertainty, and
   instrument impact.
7. The user can correct the system: watch, mute, rename, mark
   invalid/irrelevant, or reject an event assignment.

The user must be able to understand **why** the system reached a conclusion
without rereading every source document.

### Surfaces

- **Dashboard sections:** Current Brief, Active Narratives, NQ/BTC/GOLD
  Exposure, Material Changes / Alert Feed. The main object on the dashboard is
  the narrative. The dashboard answers: what dominates, what it affects, what
  requires attention now.
- **Morning Market Brief:** Macro / Cross-Market, NQ, BTC, GOLD, Watch Today.
  Includes important macro narratives even when directional impact is unclear.
  Top narratives are ranked by importance, not only by directional impact.
  Instrument sections show only narratives material to that instrument.
- **Alert feed (in-app only):** emerging_narrative, confirmed_narrative,
  narrative_acceleration, high_impact_event_added_to_narrative,
  conflicting_information, unconfirmed_social_hype.

## 4. Scope of Coverage

### Tracked instruments

NQ, BTC, GOLD.

### MVP sources

- Federal Reserve / FOMC (Tier 1)
- BLS (Tier 1)
- SEC (Tier 1)
- two or three selected news / RSS sources (Tier 2)

### Candidate later sources

Company IR for large NQ components, crypto exchange announcements, specialist
research sources, X, Reddit. Social intelligence is post-MVP.

## 5. Product Principles

1. **Evidence before conclusion.** No material conclusion without an
   EvidencePack; no EvidencePack without source traceability.
2. **Independence over volume.** Ten articles repeating one originating report
   are not ten confirmations.
3. **Say only what the data supports.** Generated language must never imply a
   stronger level of evidence than the underlying data supports. Market-pricing
   language requires market data.
4. **Narratives, not topics.** The product object is a market interpretation
   with an economic mechanism and continuity over time - not a keyword cluster.
5. **Explain uncertainty, don't hide it.** Uncertainty reasons and
   contradiction signals are first-class output, not a failure state.
6. **The human can always correct the system**, and every correction is
   auditable and durable.
7. **Decision support, not prediction.** The system informs a trader; it does
   not forecast prices or emit trading signals.
8. **Simplicity over configurability** in MVP - one cadence, sensible defaults,
   no settings UI.

## 6. Non-goals

Durable exclusions (from section 18 of the source document):

- X sentiment, Reddit sentiment, social intelligence generally,
- a generic `sentiment_score` as a primary concept,
- market prediction and automated trading signals,
- custom ML models,
- a full Claim/Fact graph,
- automatic narrative merge/split and merge/split UI,
- automated NarrativeEpisode lifecycle,
- market-data confirmation and market-language permissioning,
- sentiment research, backtesting,
- Telegram / email / webhook alerts,
- Kafka and distributed processing,
- complex multi-cadence scheduling,
- low-latency event-driven official-source processing,
- candlestick charts, orderflow, heatmaps, complex settings UI, full economic
  calendar UI.

## 7. Success Definition

### Product success

A discretionary/research trader opens the dashboard and, within a few minutes,
can answer:

- what important things happened,
- which narratives are active,
- what may matter for NQ, BTC, and GOLD,
- what changed recently,
- what evidence supports the system's view.

### Minimum product capabilities

- automatic source ingestion,
- event extraction,
- narrative grouping,
- EvidencePack generation,
- instrument impact assessment,
- current brief,
- active narratives,
- alert feed,
- human correction.

### Quality gates (must all hold)

- every material narrative has traceable evidence,
- every directional impact has rationale and evidence,
- unsupported market-language claims are prohibited,
- the user can navigate from briefing to source document,
- manually rejected mappings do not silently return,
- syndicated articles do not count as independent evidence,
- the user can understand the system's conclusion without rereading every
  source.

## 8. Open Product Questions

Not answered by the source document; flagged rather than guessed:

- **Evaluation baseline.** "Faster than manual source reading" is the MVP
  hypothesis, but no measurement method (timed comparison, subjective log,
  sample of narratives reviewed) is defined.
- **Latency expectation for "emerging before obvious."** A 5-minute cadence is
  fixed, but no target from source publication to dashboard visibility is
  stated.
- **Volume expectation.** No expected documents/day or narratives/day, which
  affects cost modelling for LLM calls.
- **Coverage vs precision preference.** When the system is unsure, should it
  surface a low-confidence narrative or stay silent? Section 9 implies caution,
  but the tradeoff is not stated as a product rule.

## 9. Review Rules

Revise only on a change of product direction (new user type, new instrument
class, a shift from decision support toward prediction). New features go
through `docs/planning/` (Idea Inbox -> Roadmap -> sprint), not through edits
here.
