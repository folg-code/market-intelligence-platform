# Module Map

Living document - update whenever a module is added, removed, or moved.

Last updated: 2026-08-18. Sprint 001 tasks S001-T002..T011 and S001-T013 are
merged; the layout below reflects what is actually in the repo now.
`ingestion/` is still an empty package (stub) - its real content is
S001-T012; `cycle/` is now implemented (S001-T011).

## Layout

```text
src/moj_projekt/
  config/        settings.py - typed, environment-backed settings (implemented)
  domain/        document.py, source.py, event.py, evidence_pack.py,
                 narrative.py, narrative_episode.py, narrative_event.py,
                 narrative_relation.py, clock.py, cycle_run.py,
                 repositories.py, enums.py, evidence.py, embedding.py - value
                 objects, invariants, repository interfaces (implemented for
                 Source/Document/Event/EvidencePack/Narrative/
                 NarrativeEpisode/NarrativeEvent/NarrativeRelation/
                 NarrativeInstrumentImpact/Alert/LLMRun/AuditEntry/Clock/
                 CycleRun)
  persistence/   models.py, document_repository.py, source_repository.py,
                 event_repository.py, evidence_pack_repository.py,
                 narrative_repository.py, narrative_episode_repository.py,
                 narrative_event_repository.py, narrative_relation_repository.py,
                 health.py, seed_sources.py, seed_data/sources.py -
                 SQLAlchemy models, repository implementations, the /health
                 db+pgvector check (implemented for Source/Document/Event/
                 EvidencePack/Narrative/NarrativeEpisode/NarrativeEvent/
                 NarrativeRelation), and the idempotent MVP Source registry
                 seed (declarative `SEED_SOURCES` data + `seed_sources()`/CLI
                 entrypoint, reusing `SqlAlchemySourceRepository.add()`)
  ingestion/     empty package (stub) - source adapter interface + concrete
                 adapters land in S001-T012
  cycle/         stages.py, run_cycle.py, run_once.py - ordered six-stage
                 list (ingest, extract, narratives, evidence, state, alerts;
                 all no-op until S001-T012), orchestration with per-stage
                 failure isolation to one terminal CycleRun, and a direct
                 scheduler-free entrypoint (implemented)
  api/           app.py - FastAPI app, lifespan (db engine + APScheduler,
                 wired in S001-T011), GET /health (implemented; dashboard
                 read path in Phase 7)
  main.py        placeholder entrypoint predating the module layout
migrations/      Alembic environment and versions (0001: enable pgvector
                 extension; 0002: Source + Document tables, incl. an
                 immutability trigger on Document; 0003: Event + EvidencePack
                 tables, incl. an immutability trigger on EvidencePack;
                 0004: Narrative/NarrativeEpisode/NarrativeEvent/
                 NarrativeRelation tables, incl. the `identity_embedding`
                 vector(384) column - 384 is a documented placeholder
                 dimension, not a final choice - and the
                 evidence_packs.narrative_id -> narratives.id FK deferred
                 from 0003; 0005: NarrativeInstrumentImpact/Alert/LLMRun/
                 AuditEntry tables; 0006: cycle_runs table, incl. a partial
                 unique index enforcing at most one RUNNING row)
tests/           unit/ (no infrastructure, default pytest run) +
                 integration/ (marker `integration`, requires the compose db)
.github/
  workflows/     ci.yml - lint (ruff) + strict mypy, then unit + integration
                 tests against a live pgvector/pgvector:pg16 service
                 container, on every push/PR into main and sprint/** (S001-T013)
```

## Modules

| Module | Responsibility | Status | Depends on | May NOT depend on |
|---|---|---|---|---|
| `config` | Load and validate settings from the environment (`Settings`, `get_settings`) | Implemented | - | anything project-specific |
| `domain` | The model of `DOMAIN_MODEL.md`: value objects, invariants, repository interfaces | Implemented for Source, Document, Event, EvidencePack, Narrative, NarrativeEpisode, NarrativeEvent, NarrativeRelation, NarrativeInstrumentImpact, Alert, LLMRun, AuditEntry, Clock, CycleRun, enums, evidence, embedding descriptor | `config` (only for pure values) | SQLAlchemy, httpx, the Anthropic SDK - enforced by `tests/unit/test_domain_boundary.py` |
| `persistence` | Map domain objects to PostgreSQL; implement repository interfaces | Implemented for Source, Document (with DB-level immutability trigger + dedupe via unique constraint/`ON CONFLICT DO NOTHING`), Event (non-empty `source_ids` CHECK), EvidencePack (immutability trigger + `independent_source_count <= source_count` CHECK), Narrative (unique `canonical_key`, `identity_embedding vector(384)` placeholder dimension with an all-or-nothing CHECK against embedding_model/embedding_version), NarrativeEpisode (`EXCLUDE USING gist` preventing overlap per narrative), NarrativeEvent (composite PK), NarrativeRelation (self-relation CHECK + unique triple), NarrativeInstrumentImpact (upsert via `INSERT ... ON CONFLICT DO UPDATE` on `(narrative_id, instrument)`, non-neutral-direction CHECK), Alert (unique `(narrative_id, alert_type, trigger_key)`), LLMRun and AuditEntry (append-only trigger rejecting UPDATE and DELETE, `LLMRun` "latest"-alias CHECK), CycleRun (partial unique index enforcing at most one RUNNING row; no append-only trigger - `update()` is deliberate, see Known Risks in `CURRENT_STATUS.md`), the health check, and the idempotent MVP Source registry seed (`seed_sources.py` + declarative `seed_data/sources.py`, six sources across Tier 1/Tier 2) | `domain`, `config` | `ingestion`, `cycle`, `api` |
| `ingestion` | Fetch and normalize external sources into Documents; per-source failure isolation | Stub (empty package) - S001-T012. The Source registry it will read from (Fed/FOMC, BLS, SEC EDGAR as Tier 1; Reuters, AP, Bloomberg as Tier 2) is already seeded (S001-T010) | `domain`, `config` | `cycle`, `api` |
| `cycle` | Ordered stages of the 5-minute cycle, CycleRun recording, scheduler registration | Implemented (S001-T011): six-stage ordered list, per-stage failure isolation to one terminal `CycleRun`, overlap prevention at both the scheduler (`max_instances=1`) and DB level. Stages stay no-op until S001-T012 wires a real adapter into "ingest" | `domain`, `ingestion`, `persistence` | `api` |
| `api` | ASGI app, lifespan, `GET /health` (db connectivity + pgvector availability) | Implemented for health and scheduler start/stop (APScheduler wired into the lifespan, S001-T011); dashboard read path is a later task | all of the above | - |

Dependency direction is one-way: `api` -> `cycle` -> `ingestion`/`persistence`
-> `domain`. Nothing imports upward.

## Nested `CLAUDE.md` files

None yet. Add one only when a module diverges from repo-wide conventions - the
likely first candidate is `ingestion/`, once per-source quirks (feed formats,
rate limits, SEC/BLS access patterns) accumulate.

## Related

- `docs/reference/ARCHITECTURE_OVERVIEW.md`
- `docs/vision/DOMAIN_MODEL.md`
- root `CLAUDE.md`
