# Architecture Overview

Living document - describes the system as it currently is (and, where marked,
what is planned but not yet built). No approval required; update it whenever a
component is added, removed, or changed.

Last updated: 2026-08-19 (S002-T008 ExtractionService on `sprint/first-llm-slice`)

## 1. Current state

Sprint 001 is delivered through T014; this file reflects that shape. A clone
plus compose, migrations, and seed yields a running `app` + `db` stack.
`GET /health` reports database connectivity and pgvector availability. The 5-minute cycle runs in-process on
APScheduler, is invocable directly via `python -m moj_projekt.cycle.run_once`,
and persists real Documents from one live RSS source (Bloomberg Markets) with
per-source failure isolation. Every MVP entity in `DOMAIN_MODEL.md` section 3
has a table. There is no dashboard. The deterministic extraction validator
(`extraction/`) exists as a library. `ExtractionService` persists Event +
`LLMRun` in one unit of work when invoked (`FakeLLMClient` in tests). The
cycle extract stage stays passthrough until S002-T009.

How to run it: `docs/reference/WORKFLOWS.md`.

## 2. Components

| Component | Status | Responsibility |
|---|---|---|
| `app` container (FastAPI + APScheduler + processing cycle) | implemented - S001-T003/T011/T012 | Single process: `/health`, in-process 5-minute cycle, ingest via the RSS adapter. No durable state in the container. |
| `db` container (PostgreSQL + pgvector) | implemented - S001-T003/T004 | The single system of record, including narrative identity embeddings |
| Source + Document persistence | implemented - S001-T006 | Immutable, deduplicated ingestion aggregate storage |
| Event + EvidencePack persistence | implemented - S001-T007 | Extracted events (facts/claims kept separate, ADR-0008) and versioned, immutable evidence snapshots (ADR-0003); `evidence_packs.narrative_id` has an FK to `narratives.id` (S001-T008) |
| Narrative/NarrativeEpisode/NarrativeEvent/NarrativeRelation persistence | implemented - S001-T008 | Unique `canonical_key`, optional/manual-only episodes with no overlap in time (DB `EXCLUDE` constraint), narrative-event assignment (composite PK; the three-condition assignment rule is not yet enforced), typed relations (self-relations rejected). Carries `identity_embedding` - see Embedding model source below |
| NarrativeInstrumentImpact / Alert / LLMRun / AuditEntry persistence | implemented - S001-T009; LLMRun writes S002-T008 | Schema and repositories. `ExtractionService` writes `LLMRun` (always) and Event rows (on `accepted` only) when invoked; the cycle does not call it yet. Alert, impact, and AuditEntry remain unused in a cycle |
| Source registry seed | implemented - S001-T010 | Idempotent six-source MVP registry (three Tier 1 official, three Tier 2 professional) |
| Ingestion adapters | implemented for one RSS source - S001-T012 | Fetch, normalize, deduplicate source content into Documents. Remaining adapters (Fed/FOMC, BLS, SEC, further news) are Sprint 002 |
| Processing cycle | implemented - S001-T011/T012 | Ordered stages: ingest is wired; extract, narratives, evidence, state, alerts are passthrough (extract wiring is T009) |
| Extraction validator | implemented - S002-T007 | Parser + deterministic rules producing `accepted` / `proposed` / `rejected` (ADR-0002). No model, HTTP, or database. Used by `ExtractionService` |
| Extraction service | implemented - S002-T008 | One Document -> injected `LLMClient` + T007 validator -> one unit of work: `LLMRun` always, Event rows only on `accepted`. Driven by `FakeLLMClient` in this task. Not wired into the cycle (T009) |
| Anthropic Claude API (external) | not yet used - Phase 3 | Tiered LLM calls (Haiku/Sonnet/Opus) behind the validation layer |
| Embedding model source (external or local) | **undecided** - ADR-0014 follow-up | Produces narrative identity embeddings for candidate retrieval. The storage column exists (`narratives.identity_embedding`, `vector(384)`, added S001-T008) but 384 is only a documented placeholder dimension - which model actually produces the embeddings is still an open decision (see `docs/planning/CURRENT_STATUS.md` "Open Decisions"); changing it later is a migration plus a re-embedding pass, not data loss, since the embedding is derived data, never identity |
| Dashboard (Jinja2 + HTMX) | planned - Phase 7 | Brief, active narratives, instrument exposure, alert feed |
| CI | implemented - S001-T013 | Lint, strict mypy, unit + integration (not live-network) on every push/PR into `main` and `sprint/**` |

## 3. Runtime shape

```text
[Fed/FOMC, BLS, SEC - skipped until adapters exist]
[news/RSS - Bloomberg Markets live; Reuters/AP seeded but not live]
        | HTTP pull, every 5 minutes (APScheduler, in-process)
        | or python -m moj_projekt.cycle.run_once
        v
+-------------------------------+        +------------------------+
|  app container                | -----> |  Anthropic Claude API  |
|  FastAPI + scheduler + cycle  |        |  (not called yet)      |
+-------------------------------+        +------------------------+
        |  SQL (single connection pool)
        v
+-------------------------------+
|  db container                 |
|  PostgreSQL + pgvector        |
+-------------------------------+
        ^
        |  HTML + HTMX polling (Phase 7)
   [Trader's browser]
```

Two containers, one host, Docker Compose (ADR-0013). No broker, no worker
process, no separate frontend build (ADR-0005, ADR-0011, ADR-0012).

Host-side Alembic, seed, and `run_once` talk to the published db port
(5433 by default). The app image does not ship `migrations/` or
`alembic.ini`, so those commands never run inside the `app` container.

## 4. Key architectural facts

- One store: PostgreSQL holds relational entities, JSONB payloads, append-only
  audit records, and vectors (ADR-0005 as amended by ADR-0014).
- One cadence: a single 5-minute cycle produces everything, including alerts
  (ADR-0004). Alert *rows* are not written yet; the ingest stage is the only
  stage with a real body. `ExtractionService` can write Event + `LLMRun`
  atomically, but the cycle does not invoke it until T009.
- Alerts will be rows written in the same transaction as the change that caused
  them; the dashboard will poll (ADR-0005).
- All state is in the database volume; the app container is disposable.
- Migrations run as an explicit step, never on startup (ADR-0013).
- A failing source is recorded on the CycleRun and does not fail the cycle.
- Repositories flush; they do not commit. A unit of work owns the session and
  the single commit/rollback so Event + `LLMRun` writes are one
  transaction when `ExtractionService` is invoked. The cycle opens that
  boundary per stage (RUNNING is committed first; a failed stage's work
  rolls back; the terminal CycleRun is written in a following unit of
  work). Extract still does not call the service (T009).

## 5. Related

- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` (durable principles and stack)
- `docs/reference/MODULE_MAP.md` (code layout)
- `docs/reference/WORKFLOWS.md` (how to run it)
- `docs/adr/README.md` (decision index)
