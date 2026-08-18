# Module Map

Living document - update whenever a module is added, removed, or moved.

Last updated: 2026-08-18. Sprint 001 tasks S001-T002..T007 are merged; the
layout below reflects what is actually in the repo now. `ingestion/` and
`cycle/` are still empty packages (stubs) - their real content is later
Sprint 001 tasks (T011, T012).

## Layout

```text
src/moj_projekt/
  config/        settings.py - typed, environment-backed settings (implemented)
  domain/        document.py, source.py, event.py, evidence_pack.py,
                 repositories.py, enums.py, evidence.py, embedding.py - value
                 objects, invariants, repository interfaces (implemented for
                 Source/Document/Event/EvidencePack; Narrative/impact/alert/
                 governance types land in T008-T009)
  persistence/   models.py, document_repository.py, source_repository.py,
                 event_repository.py, evidence_pack_repository.py, health.py -
                 SQLAlchemy models, repository implementations, the /health
                 db+pgvector check (implemented for Source/Document/Event/
                 EvidencePack)
  ingestion/     empty package (stub) - source adapter interface + concrete
                 adapters land in S001-T012
  cycle/         empty package (stub) - processing cycle stages, CycleRun
                 record, scheduler wiring land in S001-T011
  api/           app.py - FastAPI app, lifespan (db engine only so far),
                 GET /health (implemented; scheduler wiring added in T011,
                 dashboard read path in Phase 7)
  main.py        placeholder entrypoint predating the module layout
migrations/      Alembic environment and versions (0001: enable pgvector
                 extension; 0002: Source + Document tables, incl. an
                 immutability trigger on Document; 0003: Event + EvidencePack
                 tables, incl. an immutability trigger on EvidencePack)
tests/           unit/ (no infrastructure, default pytest run) +
                 integration/ (marker `integration`, requires the compose db)
```

## Modules

| Module | Responsibility | Status | Depends on | May NOT depend on |
|---|---|---|---|---|
| `config` | Load and validate settings from the environment (`Settings`, `get_settings`) | Implemented | - | anything project-specific |
| `domain` | The model of `DOMAIN_MODEL.md`: value objects, invariants, repository interfaces | Implemented for Source, Document, Event, EvidencePack, enums, evidence, embedding descriptor; Narrative/impact/alert/governance types are T008-T009 | `config` (only for pure values) | SQLAlchemy, httpx, the Anthropic SDK - enforced by `tests/unit/test_domain_boundary.py` |
| `persistence` | Map domain objects to PostgreSQL; implement repository interfaces | Implemented for Source, Document (with DB-level immutability trigger + dedupe via unique constraint/`ON CONFLICT DO NOTHING`), Event (non-empty `source_ids` CHECK), EvidencePack (immutability trigger + `independent_source_count <= source_count` CHECK), plus the health check | `domain`, `config` | `ingestion`, `cycle`, `api` |
| `ingestion` | Fetch and normalize external sources into Documents; per-source failure isolation | Stub (empty package) - S001-T012 | `domain`, `config` | `cycle`, `api` |
| `cycle` | Ordered stages of the 5-minute cycle, CycleRun recording, scheduler registration | Stub (empty package) - S001-T011 | `domain`, `ingestion`, `persistence` | `api` |
| `api` | ASGI app, lifespan, `GET /health` (db connectivity + pgvector availability) | Implemented for health; scheduler start/stop and dashboard read path are later tasks | all of the above | - |

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
