# Architecture Foundations

Status: Accepted
Approved by:
Approval date:

Requires explicit human approval before it is treated as binding (skill
`governance`). The four previously **OPEN** rows in the Tech Stack table (LLM
provider, scheduler, frontend, hosting) are now resolved and each carries its
own ADR; the pgvector addition is recorded in ADR-0014, which amends ADR-0005.

## 1. Purpose

Durable architectural principles and constraints for the Market Intelligence
Platform. Specific binding decisions live in `docs/adr/`; the current component
picture will live in `docs/reference/ARCHITECTURE_OVERVIEW.md`.

## 2. Tech Stack

| Layer | Choice | Why | Trade-off |
|---|---|---|---|
| Language/runtime | Python 3.11+ | Existing repo skeleton is Python; the LLM/NLP and feed-parsing ecosystem is strongest here | Weaker static guarantees than a typed compiled language; needs strict typing/linting discipline |
| API framework | FastAPI | Named explicitly in Vision section 16 (`Alert -> PostgreSQL -> FastAPI -> Dashboard`); async I/O suits fan-out to sources and LLM calls | Async correctness burden; no batteries-included admin/ORM layer |
| Database | PostgreSQL | Named explicitly in Vision section 16; single store for documents, narratives, evidence, audit, alert feed; JSONB covers semi-structured LLM payloads without a second store (ADR-0005) | Single-store coupling; polling-based alert feed instead of push |
| Vector search | `pgvector` extension **inside the same PostgreSQL instance** (ADR-0014) | Narrative candidate matching needs semantic retrieval from MVP - the largest modelling risk (`DOMAIN_MODEL.md` section 8); an extension keeps one store, one backup, one transaction | Hard prerequisite on the DB image/host; embedding model is a second model dependency; similarity thresholds need tuning |
| LLM provider / model | Anthropic Claude; tiered per task type - Haiku (low-risk Tier A), Sonnet (default workhorse, all Tier B), Opus (reserved, opt-in later) (ADR-0010) | One provider, one SDK, one cost surface; tiering keeps high-volume work cheap without weakening narrative reasoning | Provider lock-in for MVP; model deprecation is an external clock; tier misassignment can silently cost quality |
| Embedding model source | **OPEN** - Anthropic has no embeddings API; local open-weight model vs a second paid API (ADR-0014 follow-up) | Needed before Phase 4; a paid dependency requires explicit human approval (`governance`) | Local = one more runtime dependency; hosted = a second vendor and per-token cost |
| Scheduler / orchestration for the 5-min cycle | In-process APScheduler inside the FastAPI app; two jobs (cycle, Morning Brief); no worker, no broker (ADR-0011) | One recurring job at a 5-minute cadence needs no distributed execution; keeps domain code call-level testable | Schedule tied to process lifetime; API and cycle share a process; resumability becomes a hard requirement |
| Frontend / dashboard | FastAPI + Jinja2 templates + HTMX, server-rendered (ADR-0012) | Small interaction surface, polling feed, explicit UI non-goals; avoids a second language and a JS build toolchain | Interactivity ceiling; presentation coupled to the request cycle; a React/SPA move is the acknowledged *later* upgrade path, not MVP |
| Hosting / deployment target | Single host - local machine or one small VPS - via Docker Compose (`app` + `db`) (ADR-0013) | Matches the single-user, anti-scale stance; development and deployment share one shape | No HA; backups depend on a documented manual procedure; vertical scaling only |
| Secrets | Environment variables via an uncommitted `.env` (`.env.example` committed); one secret at MVP (Anthropic API key) (ADR-0013) | Proportionate to one user, one host, one key | Would not be adequate beyond single-user |
| Key libraries (feed/HTML parsing, ORM, migrations, schema validation, HTTP client) | To be settled in Sprint 001 Wave 0; individually low-risk and reversible | Single-module scope, cheap to change | Only elevate to an ADR if a choice becomes cross-cutting |

Setup commands, pinned versions, and how to run things belong in
`docs/reference/WORKFLOWS.md`, not here.

## 3. Guiding Principles

### General

1. **Business logic separated from infrastructure.** Narrative/evidence rules
   must be evaluable without a database, an HTTP request, or a live LLM.
2. **Validation at system boundaries.** Source feeds, LLM responses, and API
   requests are validated on entry against explicit schemas; inside the
   boundary, code trusts its types.
3. **Explicit dependencies, no global state.** No hidden singletons, no
   side-effecting imports, no uncontrolled clock or randomness (the clock is
   injected - the pipeline is time-sensitive and must be testable).
4. **YAGNI.** No abstraction before two concrete use cases. This is a
   single-user MVP with an explicit anti-scale stance (Vision section 18).

### Project-specific (non-negotiable, derived from the Vision)

5. **LLM outputs are candidates, never truth.** Every LLM result passes through
   a deterministic validation layer that yields `accepted` / `proposed` /
   `rejected`. See section 5 below and ADR-0002.
6. **Auditability by construction.** Every material LLM run and every human
   override is persisted with enough context to reconstruct the decision later.
   See ADR-0007, ADR-0009.
7. **Raw input is immutable.** Documents are stored as collected; corrections
   are new records, not overwrites.
8. **Evidence-gated language generation.** Generated text may not exceed the
   evidential level of its inputs. See section 6 below and ADR-0003.
9. **Reproducibility.** The same input plus the same prompt/model/parameter
   versions must be reconstructible for audit. Hashing input is insufficient -
   input references or snapshots are stored too (ADR-0007).
10. **Derived data is never identity.** Embeddings, scores, and similarity
    values may retrieve, rank, or block - they never *are* a domain decision.
    Narrative identity stays the semantic `canonical_key` (ADR-0001, ADR-0014).

## 4. Processing Model

- **One processing cycle, every 5 minutes** (ADR-0004), fired by in-process
  APScheduler with overlap prevention (ADR-0011):
  1. ingest new documents,
  2. extract events,
  3. update narrative candidates,
  4. rebuild affected EvidencePacks,
  5. recalculate narrative state,
  6. evaluate alert rules.
- Alerts are generated **inside** the same cycle - no separate alerting cadence.
- **Morning Brief is a separate job**: on demand, plus a configurable schedule.
- **No multi-cadence or staggered schedulers in MVP.** No event-driven
  low-latency path for official sources.
- The cycle must be **idempotent and re-runnable**: a cycle that fails partway
  must be safe to run again without duplicating events, evidence, or alerts.
- Every cycle writes a **run record**; missed ticks coalesce into one catch-up
  cycle rather than a backlog (ADR-0011).

Pipeline shape (Vision section 11):

```text
Sources -> Documents -> Event Extraction (extracted_facts, source_claims)
  -> Events -> Narrative Candidates -> EvidencePack -> Validated Narratives
  -> Instrument Impact -> Brief / Alerts / Dashboard
```

## 5. LLM Decision Boundaries

LLMs are analytical components, not sources of truth. Decisions are tiered
(ADR-0002):

**Tier A - LLM may perform independently** (low-risk semantic transformation):
entity extraction, topic classification, candidate event extraction, candidate
economic mechanism, candidate market interpretation, relation candidate
generation, uncertainty reason generation, summary generation.

**Tier B - LLM may propose, not finalize** (a deterministic validator may
auto-accept when confidence and evidence thresholds are met; otherwise the
result becomes a `proposed` item for the human): event-to-narrative assignment,
creation of a new narrative, instrument relevance, instrument direction,
narrative relations, canonical mapping changes.

**Tier C - LLM must never finalize** (human or hard rule only):
`validity_status = confirmed`, merge, split, any change to a `user_locked`
decision, high-confidence/high-impact instrument impact without evidence, any
durable change to semantic narrative identity.

Most Tier B decisions will not involve a human - they are auto-accepted by
deterministic rules. The boundary is about *who is allowed to finalize*, not
about forcing manual review.

Model tier (Haiku/Sonnet/Opus) is chosen per task type and is **independent of**
the A/B/C decision tier: a cheaper model never grants a task more authority
(ADR-0010).

## 6. Evidence & Trust Rules

Hard rules enforced in code, not only in prompts:

- No material conclusion without an EvidencePack.
- No EvidencePack without source traceability to Documents.
- No market claim without evidence from the corresponding market data domain.
- Independent source counting is mandatory; syndicated repetition of one
  originating report counts once (ADR-0003).

The system distinguishes five epistemic categories and must not blur them:
**observed facts**, **source claims**, **model inference**, **system-derived
metrics**, **market-derived evidence**.

Language permissioning (no market data available in MVP -> market-pricing
language is forbidden):

- Forbidden: "Markets are pricing in...", "Market pricing suggests...",
  "Options pricing reflects..."
- Allowed: "Financial commentary increasingly expects...", "Monitored sources
  increasingly frame this as...", "Discussion is shifting toward...", "The
  dominant interpretation among monitored sources is..."

This must be checked by a deterministic post-generation validator, not left to
model compliance.

## 7. LLM Run Reproducibility

Every material LLM run persists: `id`, `task_type`, `provider`, `model`,
`model_version`, `prompt_version`, `system_prompt_version`, `input_hash`,
`input_reference_ids`, `output_schema_version`, `raw_output`, `parsed_output`,
`validation_status`, `validation_errors`, `temperature`,
`inference_parameters`, `token_usage`, `latency`, `created_at`.

Model identifiers are **pinned** (dated model IDs, never a floating alias), so a
provider-side rotation cannot silently change behaviour (ADR-0010). Where a run
was preceded by embedding retrieval, the retrieved shortlist and its scores are
recorded with the run (ADR-0014).

The system must be able to answer *"why did the system assign this event to
this narrative on that date?"* and return input, prompt version, model, raw
output, parsed result, and validator result (ADR-0007).

## 8. System Context

```text
[Fed/FOMC, BLS, SEC, news/RSS feeds]  --(HTTP pull, 5-min cycle)-->
        [app container: FastAPI + APScheduler + processing cycle]
                  |                         |
                  v                         v
        [PostgreSQL + pgvector]      [Anthropic Claude API]
                  ^
                  |
        [Jinja2 + HTMX dashboard] --> [Trader]
```

Two containers on one host (ADR-0013). External dependencies: public source
endpoints (rate limits, format drift, availability outside our control), the
Anthropic API (cost, latency, availability, model deprecation), and an
embedding model source (**open**, ADR-0014). No outbound delivery channels in
MVP.

## 9. Key Constraints

- Single-user system; no multi-tenancy, no auth model beyond protecting one
  deployment.
- No market data feed in MVP - this constrains what the system may *say*.
- LLM inference cost is a real budget constraint: rebuild only what changed in
  each cycle rather than reprocessing all narratives.
- Sources are third-party and unstable; ingestion must degrade gracefully when
  one source fails (a failing feed must not fail the cycle).
- No Kafka, no distributed processing, no custom ML models (Vision section 18).
- Single host, no HA: the system may be down; it may not lose or corrupt data
  (ADR-0013).
- The PostgreSQL image/host **must** provide `pgvector` (ADR-0014).

## 10. Prioritized Quality Attributes

For this project, in conflict, in this order:

1. **Traceability / auditability** - a conclusion that cannot be explained is a
   defect, even if it is right.
2. **Correctness** of evidence and epistemic labelling.
3. **Readability / testability** - the domain rules are the product; they must
   be readable and unit-testable without infrastructure.
4. **Reliability** of the 5-minute cycle (idempotent, resumable).
5. **Performance** - explicitly last. A 5-minute cadence with a handful of
   sources leaves ample headroom.

This overrides the plugin default order, which puts correctness first:
here, an unexplainable correct answer still violates the product's core
promise.

## 11. Explicitly Out of Scope (Architectural)

- Multi-tenancy, RBAC, i18n.
- Message brokers / streaming (Kafka), distributed workers, separate worker
  processes.
- Horizontal scale, sharding, read replicas, HA.
- Real-time push transport (WebSocket/SSE) for the alert feed - polling is
  sufficient at a 5-minute cadence.
- **A separate vector store or search cluster.** Vector search is in scope, but
  only as the `pgvector` extension of the single PostgreSQL instance (ADR-0014);
  a standalone vector service remains excluded.
- A JavaScript build toolchain / SPA frontend in MVP (ADR-0012).
- Managed cloud services, Kubernetes, secrets managers (ADR-0013).
- Outbound delivery channels (Telegram/email/webhooks).

## 12. Related ADRs

- [ADR-0001](../adr/ADR-0001-semantic-narrative-identity.md) - semantic
  `canonical_key` as narrative identity
- [ADR-0002](../adr/ADR-0002-llm-candidate-validation-layer.md) - LLM outputs
  are candidates behind a deterministic validation layer
- [ADR-0003](../adr/ADR-0003-mandatory-evidencepack.md) - mandatory EvidencePack
  with independent-source counting
- [ADR-0004](../adr/ADR-0004-single-five-minute-cadence.md) - single 5-minute
  processing cadence
- [ADR-0005](../adr/ADR-0005-postgresql-fastapi-alerting.md) - PostgreSQL +
  FastAPI alert path, no broker (amended by ADR-0014)
- [ADR-0006](../adr/ADR-0006-instrument-impact-over-sentiment.md) - instrument
  impact direction replaces a generic sentiment score
- [ADR-0007](../adr/ADR-0007-llm-run-audit-record.md) - LLM run audit record
- [ADR-0008](../adr/ADR-0008-no-standalone-claim-fact-model.md) - facts/claims
  embedded in Event, no Claim/Fact graph
- [ADR-0009](../adr/ADR-0009-override-states-and-audit.md) - override states and
  human-correction audit
- [ADR-0010](../adr/ADR-0010-anthropic-claude-tiered-models.md) - Anthropic
  Claude, tiered model selection
- [ADR-0011](../adr/ADR-0011-in-process-apscheduler.md) - in-process APScheduler
  for the 5-minute cycle
- [ADR-0012](../adr/ADR-0012-server-rendered-dashboard-jinja-htmx.md) -
  server-rendered dashboard (Jinja2 + HTMX), SPA staged later
- [ADR-0013](../adr/ADR-0013-single-host-docker-compose-deployment.md) - single
  host, Docker Compose
- [ADR-0014](../adr/ADR-0014-pgvector-for-narrative-candidate-matching.md) -
  pgvector for narrative candidate matching (amends ADR-0005)

## 13. Open Architectural Questions

Previously blocking, now **resolved**: LLM provider (ADR-0010), scheduler
(ADR-0011), frontend (ADR-0012), hosting (ADR-0013), narrative candidate
matching mechanism (ADR-0014). The repository is now under version control.

Still open (none block Sprint 001):

1. **Embedding model source** (local open-weight vs a second paid API) - needed
   before Phase 4; a paid dependency requires explicit human approval.
2. **Dashboard access protection** once reachable beyond localhost - needed
   before any non-local exposure.
3. **Retention policy** for raw document bodies and LLM `raw_output` - needed
   by Phase 10.
4. **Monthly LLM cost ceiling** and the alert on approaching it.
5. Non-blocking: migration tooling specifics, materiality threshold, and
   independence-detection mechanism (see `DOMAIN_MODEL.md` section 8).

## 14. Review Rules

Revise on a significant architecture change or when evidence contradicts an
assumption here - not on every ADR.
