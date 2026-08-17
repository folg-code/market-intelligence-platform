# Architecture Overview

Living document - describes the system as it currently is (and, where marked,
what is planned but not yet built). No approval required; update it whenever a
component is added, removed, or changed.

Last updated: 2026-08-17 (architecture phase closed; Sprint 001 not yet started)

## 1. Current state

**Nothing is implemented yet.** The repository contains a Python package
skeleton, a placeholder test, and the documentation set. Everything below marked
*planned* is delivered by Sprint 001 unless noted.

## 2. Components

| Component | Status | Responsibility |
|---|---|---|
| `app` container (FastAPI + APScheduler + processing cycle) | planned - S001-T003/T011 | Single process: serves the read path and runs the 5-minute cycle |
| `db` container (PostgreSQL + pgvector) | planned - S001-T003 | The single system of record, including narrative identity embeddings |
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
