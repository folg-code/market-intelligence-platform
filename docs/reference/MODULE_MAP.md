# Module Map

Living document - update whenever a module is added, removed, or moved.

Last updated: 2026-08-19. Matches the package layout on `sprint/mvp-foundation`
after S001-T014 (`WORKFLOWS.md`, README, reference docs).

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
                 seed. Files: models.py, health.py, seed_sources.py,
                 seed_data/sources.py, document_repository.py,
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
                 0006 cycle_runs (partial unique index: at most one RUNNING)
tests/           unit/ (no infrastructure; default pytest run)
                 integration/ (marker `integration`; needs compose db)
                 fixtures/rss/ (sample, empty, malformed feeds)
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
| `persistence` | Map domain objects to PostgreSQL; implement repository interfaces; seed the Source registry; `/health` db+pgvector check | Implemented for every MVP entity above. Document: DB-level immutability trigger + dedupe (`ON CONFLICT DO NOTHING`). Event: non-empty `source_ids` CHECK. EvidencePack: immutability trigger + `independent_source_count <= source_count`. Narrative: unique `canonical_key`, `identity_embedding vector(384)` placeholder with all-or-nothing CHECK. NarrativeEpisode: `EXCLUDE USING gist`. NarrativeEvent: composite PK. NarrativeRelation: self-relation CHECK + unique triple. NarrativeInstrumentImpact: upsert on `(narrative_id, instrument)`. Alert: unique `(narrative_id, alert_type, trigger_key)`. LLMRun and AuditEntry: append-only trigger; LLMRun rejects `"latest"`. CycleRun: partial unique index, at most one RUNNING; `update()` is deliberate. Seed: `python -m moj_projekt.persistence.seed_sources` over six declarative sources | `domain`, `config` | `ingestion`, `cycle`, `api` |
| `ingestion` | Fetch and normalize external sources into Documents | Implemented (S001-T012): `SourceAdapter` + one RSS adapter. Persistence is the cycle ingest stage. A later adapter implements the interface and is registered by `source_type` | `domain`, `config` | `cycle`, `api` |
| `cycle` | Ordered stages of the 5-minute cycle, CycleRun recording, scheduler-free entrypoint | Implemented (S001-T011/T012): six-stage list; ingest wired with per-source isolation; other stages passthrough; overlap prevention at scheduler (`max_instances=1`) and DB | `domain`, `ingestion`, `persistence` | `api` |
| `api` | ASGI app, lifespan, `GET /health` | Implemented for health and scheduler start/stop; dashboard read path is later | all of the above | - |

Dependency direction is one-way: `api` -> `cycle` -> `ingestion`/`persistence`
-> `domain`. Nothing imports upward.

## Nested `CLAUDE.md` files

None yet. Add one only when a module diverges from repo-wide conventions - the
likely first candidate is `ingestion/`, once per-source quirks (feed formats,
rate limits, SEC/BLS access patterns) accumulate.

## Related

- `docs/reference/ARCHITECTURE_OVERVIEW.md`
- `docs/reference/WORKFLOWS.md`
- `docs/vision/DOMAIN_MODEL.md`
- root `CLAUDE.md`
