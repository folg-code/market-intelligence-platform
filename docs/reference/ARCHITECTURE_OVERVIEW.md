# Architecture Overview

Living document - describes the system as it currently is (and, where marked,
what is planned but not yet built). No approval required; update it whenever a
component is added, removed, or changed.

Last updated: 2026-08-18 (Sprint 001 tasks S001-T002..T007 merged into
`sprint/mvp-foundation`)

## 1. Current state

Sprint 001 is in progress. The toolchain, the Docker Compose stack (`app` +
`db`), typed settings, the `/health` endpoint, the Alembic migration
baseline (pgvector extension enabled), Source + Document persistence
(with immutability and dedupe enforced at the database level), and Event +
EvidencePack persistence (facts/claims kept separate, evidence versioned and
immutable once written) are implemented and merged. The processing cycle,
ingestion adapters, and every MVP entity beyond Source/Document/Event/
EvidencePack (Narrative and its related tables, impact, alert, LLMRun,
AuditEntry) are not yet built. Everything below marked *planned* is
delivered later in Sprint 001 unless noted.

## 2. Components

| Component | Status | Responsibility |
|---|---|---|
| `app` container (FastAPI + APScheduler + processing cycle) | partially implemented - S001-T003 done (FastAPI + `/health`); APScheduler/cycle wiring is S001-T011 | Single process: serves the read path and runs the 5-minute cycle |
| `db` container (PostgreSQL + pgvector) | implemented - S001-T003/T004 | The single system of record, including narrative identity embeddings |
| Source + Document persistence | implemented - S001-T006 | Immutable, deduplicated ingestion aggregate storage |
| Event + EvidencePack persistence | implemented - S001-T007 | Extracted events (facts/claims kept separate, ADR-0008) and versioned, immutable evidence snapshots (ADR-0003); `evidence_packs.narrative_id` has no FK yet - added in S001-T008 once `narratives` exists |
| Ingestion adapters | planned - S001-T012 (one RSS source; the rest in Sprint 002) | Fetch, normalize, deduplicate source content into Documents |
| Processing cycle | planned - S001-T011 (skeleton, stages empty) | Ordered stages: ingest, extract, narratives, evidence, state, alerts |
| Anthropic Claude API (external) | not yet used - Phase 3 | Tiered LLM calls (Haiku/Sonnet/Opus) behind the validation layer |
| Embedding model source (external or local) | **undecided** - ADR-0014 follow-up | Produces narrative identity embeddings for candidate retrieval |
| Dashboard (Jinja2 + HTMX) | planned - Phase 7 | Brief, active narratives, instrument exposure, alert feed |

## 3. Runtime shape

```text
[Fed/FOMC, BLS, SEC, news/RSS]
        | HTTP pull, every 5 minutes (APScheduler, in-process)
        v
+-------------------------------+        +------------------------+
|  app container                | -----> |  Anthropic Claude API  |
|  FastAPI + scheduler + cycle  |        +------------------------+
+-------------------------------+
        |  SQL (single connection pool)
        v
+-------------------------------+
|  db container                 |
|  PostgreSQL + pgvector        |
+-------------------------------+
        ^
        |  HTML + HTMX polling
   [Trader's browser]
```

Two containers, one host, Docker Compose (ADR-0013). No broker, no worker
process, no separate frontend build (ADR-0005, ADR-0011, ADR-0012).

## 4. Key architectural facts

- One store: PostgreSQL holds relational entities, JSONB payloads, append-only
  audit records, and vectors (ADR-0005 as amended by ADR-0014).
- One cadence: a single 5-minute cycle produces everything, including alerts
  (ADR-0004).
- Alerts are rows written in the same transaction as the change that caused them;
  the dashboard polls (ADR-0005).
- All state is in the database volume; the app container is disposable.
- Migrations run as an explicit step, never on startup (ADR-0013).

## 5. Related

- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` (durable principles and stack)
- `docs/reference/MODULE_MAP.md` (code layout)
- `docs/adr/README.md` (decision index)
