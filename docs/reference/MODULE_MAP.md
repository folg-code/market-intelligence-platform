# Module Map

Living document - update whenever a module is added, removed, or moved.

Last updated: 2026-08-18. Sprint 001 tasks S001-T002..T013 are on the sprint
branch or in review; the layout below reflects the repo including S001-T012
(`ingestion/` is the RSS adapter interface + one concrete adapter; `cycle/`
ingest is wired).

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
  ingestion/     adapter.py, rss.py - source adapter interface + one Tier 2
                 RSS adapter (Bloomberg Markets; feed URL from seed
                 endpoint_config). Network I/O confined here.
  cycle/         stages.py, ingest.py, run_cycle.py, run_once.py - ordered
                 six-stage list; ingest fetches via adapters and persists
                 Documents with per-source isolation; other stages still
                 passthrough; CycleRun recording and a direct scheduler-free
                 entrypoint (implemented)
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
                 + live RSS feed (markers `network` and `integration`,
                 excluded from CI)
.github/
  workflows/     ci.yml - lint (ruff) + strict mypy, then unit + integration
                 tests against a live pgvector/pgvector:pg16 service
                 container, on every push/PR into main and sprint/**;
                 `pytest -m "not network"` so the live RSS feed is excluded
                 (S001-T013, S001-T012)
```

## Modules

| Module | Responsibility | Status | Depends on | May NOT depend on |
|---|---|---|---|---|
| `config` | Load and validate settings from the environment (`Settings`, `get_settings`) | Implemented | - | anything project-specific |
| `domain` | The model of `DOMAIN_MODEL.md`: value objects, invariants, repository interfaces | Implemented for Source, Document, Event, EvidencePack, Narrative, NarrativeEpisode, NarrativeEvent, NarrativeRelation, NarrativeInstrumentImpact, Alert, LLMRun, AuditEntry, Clock, CycleRun, enums, evidence, embedding descriptor | `config` (only for pure values) | SQLAlchemy, httpx, the Anthropic SDK - enforced by `tests/unit/test_domain_boundary.py` |
| `persistence` | Map domain objects to PostgreSQL; implement repository interfaces | Implemented for Source, Document (with DB-level immutability trigger + dedupe via unique constraint/`ON CONFLICT DO NOTHING`), Event (non-empty `source_ids` CHECK), EvidencePack (immutability trigger + `independent_source_count <= source_count` CHECK), Narrative (unique `canonical_key`, `identity_embedding vector(384)` placeholder dimension with an all-or-nothing CHECK against embedding_model/embedding_version), NarrativeEpisode (`EXCLUDE USING gist` preventing overlap per narrative), NarrativeEvent (composite PK), NarrativeRelation (self-relation CHECK + unique triple), NarrativeInstrumentImpact (upsert via `INSERT ... ON CONFLICT DO UPDATE` on `(narrative_id, instrument)`, non-neutral-direction CHECK), Alert (unique `(narrative_id, alert_type, trigger_key)`), LLMRun and AuditEntry (append-only trigger rejecting UPDATE and DELETE, `LLMRun` "latest"-alias CHECK), CycleRun (partial unique index enforcing at most one RUNNING row; no append-only trigger - `update()` is deliberate, see Known Risks in `CURRENT_STATUS.md`), the health check, and the idempotent MVP Source registry seed (`seed_sources.py` + declarative `seed_data/sources.py`, six sources across Tier 1/Tier 2) | `domain`, `config` | `ingestion`, `cycle`, `api` |
| `ingestion` | Fetch and normalize external sources into Documents; per-source failure isolation | Implemented (S001-T012): `SourceAdapter` interface + one RSS adapter. Network (`httpx`/`feedparser`) confined here; persistence is the cycle ingest stage via repository interfaces. A later adapter implements the interface and is registered by `source_type` | `domain`, `config` | `cycle`, `api` |
| `cycle` | Ordered stages of the 5-minute cycle, CycleRun recording, scheduler registration | Implemented (S001-T011/T012): six-stage ordered list, ingest wired to the RSS adapter with per-source outcomes on `CycleRun`, other stages still passthrough, overlap prevention at both the scheduler (`max_instances=1`) and DB level | `domain`, `ingestion`, `persistence` | `api` |
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
