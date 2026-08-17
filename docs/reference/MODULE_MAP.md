# Module Map

Living document - update whenever a module is added, removed, or moved.

Last updated: 2026-08-17. **The layout below is the target established for
Sprint 001 (task S001-T002); today the repo contains only
`src/moj_projekt/main.py` and a placeholder test.**

## Layout

```text
src/moj_projekt/
  config/        settings (typed, environment-backed)
  domain/        value objects, enums, invariants, repository interfaces
  persistence/   SQLAlchemy models, repository implementations, session handling
  ingestion/     source adapter interface + concrete adapters
  cycle/         processing cycle stages, CycleRun record, scheduler wiring
  api/           FastAPI app, lifespan, health endpoint (dashboard later)
migrations/      Alembic environment and versions
tests/           unit (no infrastructure) + integration (marked)
```

## Modules

| Module | Responsibility | Depends on | May NOT depend on |
|---|---|---|---|
| `config` | Load and validate settings from the environment | - | anything project-specific |
| `domain` | The model of `DOMAIN_MODEL.md`: value objects, invariants, repository interfaces | `config` (only for pure values) | SQLAlchemy, httpx, the Anthropic SDK - enforced by a test |
| `persistence` | Map domain objects to PostgreSQL; implement repository interfaces | `domain`, `config` | `ingestion`, `cycle`, `api` |
| `ingestion` | Fetch and normalize external sources into Documents; per-source failure isolation | `domain`, `config` | `cycle`, `api` |
| `cycle` | Ordered stages of the 5-minute cycle, CycleRun recording, scheduler registration | `domain`, `ingestion`, `persistence` | `api` |
| `api` | ASGI app, lifespan (starts/stops the scheduler), health endpoint, later the dashboard read path | all of the above | - |

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
