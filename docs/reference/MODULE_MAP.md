# Module Map

Living document - update whenever a module is added, removed, or moved.

Last updated: 2026-08-19. Matches `sprint/first-llm-slice` after S002-T002..T007.

## Layout

```text
src/moj_projekt/
  config/        settings.py - typed, environment-backed settings
  domain/        value objects, invariants, repository interfaces.
                 Files: document.py, source.py, event.py, evidence_pack.py,
                 narrative.py, narrative_episode.py, narrative_event.py,
                 narrative_relation.py, instrument_impact.py, alert.py,
                 llm_run.py, audit_entry.py, clock.py, cycle_run.py,
                 repositories.py, enums.py, evidence.py, embedding.py
  persistence/   SQLAlchemy models, repository implementations, health check,
                 seed, unit of work. Files: models.py, health.py, seed_sources.py,
                 seed_data/sources.py, unit_of_work.py, document_repository.py,
                 source_repository.py, event_repository.py,
                 evidence_pack_repository.py, narrative_repository.py,
                 narrative_episode_repository.py, narrative_event_repository.py,
                 narrative_relation_repository.py,
                 instrument_impact_repository.py, alert_repository.py,
                 llm_run_repository.py, audit_entry_repository.py,
                 cycle_run_repository.py
  ingestion/     adapter.py (SourceAdapter + SourceFetchError), rss.py
                 (RssFeedAdapter; feed URL from seed endpoint_config).
                 Network I/O confined here.
  llm/           client.py (LLMClient port), anthropic_client.py, fake.py,
                 artifacts.py, models.py (task -> pinned id + rates),
                 prompts/ (system_v1, event_extraction_v1, schema v1).
                 Only this package may import the Anthropic SDK; AnthropicClient
                 is lazy-loaded so artifacts stay SDK-free.
  extraction/    parser.py (raw text -> JSON object or parse failure),
                 validator.py (accepted / proposed / rejected), types.py,
                 schema.py, vocabulary.py, market_language.py.
                 No model, HTTP, or database. Persistence and LLM calls
                 are T008; cycle extract wiring is T009.
  cycle/         stages.py (six-stage list), ingest.py (production ingest),
                 run_cycle.py (orchestration + CycleRun recording),
                 run_once.py (scheduler-free CLI: python -m moj_projekt.cycle.run_once)
  api/           app.py - FastAPI app, lifespan (db engine + APScheduler),
                 GET /health. Dashboard read path is Phase 7.
  main.py        leftover placeholder entrypoint ("Hello from moj-projekt!")
migrations/      Alembic env + versions
                 0001 enable pgvector; 0002 Source + Document (immutability
                 trigger); 0003 Event + EvidencePack (immutability trigger);
                 0004 Narrative family + identity_embedding vector(384)
                 placeholder + evidence_packs.narrative_id FK; 0005
                 NarrativeInstrumentImpact/Alert/LLMRun/AuditEntry;
                 0006 cycle_runs (partial unique index: at most one RUNNING);
                 0007 terminal CycleRun immutability trigger
tests/           unit/ (no infrastructure; default pytest run)
                 integration/ (marker `integration`; needs compose db)
                 fixtures/rss/ and fixtures/llm/
                 live RSS test is marked `network` and `integration`,
                 excluded from CI
.github/
  workflows/     ci.yml - ruff + strict mypy, then unit + integration
                 against pgvector/pgvector:pg16; pytest -m "not network"
scripts/
  check.py       ruff check, mypy src, pytest (unit)
```

## Modules

| Module | Responsibility | Status | Depends on | May NOT depend on |
|---|---|---|---|---|
| `config` | Load and validate settings from the environment (`Settings`, `get_settings`) | Implemented | - | anything project-specific |
| `domain` | The model of `DOMAIN_MODEL.md`: value objects, invariants, repository interfaces | Implemented for Source, Document, Event, EvidencePack, Narrative, NarrativeEpisode, NarrativeEvent, NarrativeRelation, NarrativeInstrumentImpact, Alert, LLMRun, AuditEntry, Clock, CycleRun, enums, evidence, embedding descriptor | - | SQLAlchemy, httpx, the Anthropic SDK - enforced by `tests/unit/test_domain_boundary.py` |
| `persistence` | Map domain objects to PostgreSQL; implement repository interfaces; seed the Source registry; `/health` db+pgvector check | Implemented for every MVP entity above. Document: DB-level immutability trigger + dedupe (`ON CONFLICT DO NOTHING`). Event: non-empty `source_ids` CHECK. EvidencePack: immutability trigger + `independent_source_count <= source_count`. Narrative: unique `canonical_key`, `identity_embedding vector(384)` placeholder with all-or-nothing CHECK. NarrativeEpisode: `EXCLUDE USING gist`. NarrativeEvent: composite PK. NarrativeRelation: self-relation CHECK + unique triple. NarrativeInstrumentImpact: upsert on `(narrative_id, instrument)`. Alert: unique `(narrative_id, alert_type, trigger_key)`. LLMRun and AuditEntry: append-only trigger; LLMRun rejects `"latest"`. CycleRun: partial unique index (at most one RUNNING) plus `0007` terminal-row UPDATE trigger. Repositories flush; `SqlAlchemyUnitOfWork` owns session lifecycle and the single commit/rollback. Seed: `python -m moj_projekt.persistence.seed_sources` (only `bloomberg_markets` active) | `domain`, `config` | `ingestion`, `cycle`, `api` |
| `ingestion` | Fetch and normalize external sources into Documents | Implemented (S001-T012): `SourceAdapter` + one RSS adapter. Persistence is the cycle ingest stage. A later adapter implements the interface and is registered by `source_type` | `domain`, `config` | `cycle`, `api` |
| `llm` | One port to call a model: versioned prompts/schema, pinned ids, FakeLLMClient | Implemented (S002-T006). Real Anthropic path is T011 | `config` | `domain`, `cycle`, `api` — Anthropic SDK must not leak outside this package (`tests/unit/test_llm_boundary.py`) |
| `extraction` | Parse raw model output and judge it with deterministic rules into `accepted` / `proposed` / `rejected` (ADR-0002) | Implemented (S002-T007). Does not construct an `Event`. Duplicate fact/claim text is not a merge (ADR-0008). Persistence and LLM calls are T008; cycle wiring is T009 | `domain`, `llm.artifacts` | SQLAlchemy, httpx, Anthropic SDK (`tests/unit/test_extraction_boundary.py`); `cycle`, `api`, `persistence` |
| `cycle` | Ordered stages of the 5-minute cycle, CycleRun recording, scheduler-free entrypoint | Implemented (S001-T011/T012, S002-T002): six-stage list; ingest wired with per-source isolation; other stages passthrough; overlap prevention at scheduler (`max_instances=1`) and DB. CycleRun two-phase write is one unit of work for RUNNING, one per stage, then one that finalizes even if a stage rolled back | `domain`, `ingestion`, `persistence` | `api` |
| `api` | ASGI app, lifespan, `GET /health` | Implemented for health and scheduler start/stop; dashboard read path is later | all of the above | - |

Dependency direction is one-way: `api` -> `cycle` -> `ingestion`/`persistence`/`llm` -> `domain`/`config`. `extraction` sits beside `llm` (`extraction` -> `domain` + `llm.artifacts`; not yet called by `cycle`). Nothing imports upward.

## Nested `CLAUDE.md` files

- `src/moj_projekt/llm/CLAUDE.md` - pinned model ids, prompt-version bumps, secrets, Anthropic SDK stays in this package.
- `src/moj_projekt/extraction/CLAUDE.md` - validator judges only (no repair, no Event construction); verdicts are `CandidateStatus`; schema artifacts via `llm.artifacts`.

## Related

- `docs/reference/ARCHITECTURE_OVERVIEW.md`
- `docs/reference/WORKFLOWS.md`
- `docs/vision/DOMAIN_MODEL.md`
- root `CLAUDE.md`
