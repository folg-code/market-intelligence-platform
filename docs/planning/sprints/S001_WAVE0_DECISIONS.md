# Sprint 001 - Wave 0 Decisions

Binding decisions for **Sprint 001 - Foundation to first real document**.

Date: 2026-08-17
Basis: `docs/vision/ARCHITECTURE_FOUNDATIONS.md`, `docs/vision/DOMAIN_MODEL.md`,
ADR-0001..ADR-0014, `docs/planning/ROADMAP.md` Phases 0-2.

## D-S001-01 - Problem Statement

The architecture is decided and documented, but nothing in the repository
exercises it. The repo holds a bare Python skeleton with no dependencies, no
database, no schema, and no data. Until real Documents exist in PostgreSQL,
every later phase (event extraction, narrative identity, evidence, impact) has
nothing to run against and every design assumption stays untested.

Sprint 001 closes that gap: toolchain and container stack -> full domain schema
with migrations -> a scheduled cycle -> real documents from one live source.

## D-S001-02 - Path / Scope Inventory

| ID | Path / Area | Key Modules | Entrypoints | Priority |
|---|---|---|---|---|
| P1 | `pyproject.toml`, tool config, `src/` layout | package skeleton | composite check command | HIGH |
| P2 | `compose.yaml`, `.env.example`, `src/.../config/` | settings | `docker compose up` | HIGH |
| P3 | `migrations/` (Alembic) | migration env | migrate command | HIGH |
| P4 | `src/.../domain/` | value objects, enums, invariants | imported only | HIGH |
| P5 | `src/.../persistence/` | ORM models, repositories | via domain interfaces | HIGH |
| P6 | `src/.../cycle/` | cycle stages, CycleRun, scheduler wiring | scheduler + direct CLI | HIGH |
| P7 | `src/.../ingestion/` | adapter interface + one RSS adapter | called by cycle ingest stage | HIGH |
| P8 | `src/.../api/` | FastAPI app, lifespan, `/health` | ASGI server | MEDIUM |
| P9 | `.github/workflows/`, `docs/reference/` | CI, WORKFLOWS, overview, module map | CI, humans | MEDIUM |

## D-S001-03 - Success Metrics

1. From a clean clone: copy `.env`, `docker compose up`, migrate, seed, and the
   `/health` endpoint reports `database: ok` and `pgvector: available`.
2. Every entity in `DOMAIN_MODEL.md` section 3 has a table and a migration; every
   aggregate in section 5 has at least one invariant test.
3. A cycle run against one live RSS source creates real Document rows; an
   immediate re-run creates zero new rows.
4. A simulated source failure leaves the cycle successful and the failure visible
   in the CycleRun record.
5. Lint + type-check + tests green in CI on `sprint/mvp-foundation`.
6. Zero LLM API calls exist in the sprint's code.

## D-S001-04 - Correctness / Quality Gate

- **Test split is binding:** unit tests import no database, no HTTP client, and
  no LLM SDK (asserted by a test on the domain package). Integration tests are
  marked and run against a real pgvector-enabled PostgreSQL. Network-dependent
  tests are marked separately and excluded from CI.
- **Clock is injected** everywhere it is read - no direct `datetime.now()` in
  domain or cycle code.
- **mypy strict** over `src/`; a new `type: ignore` needs a comment explaining
  why.
- **Migrations are the only schema mechanism.** No `create_all()`, and no
  migration on application startup.
- **Repository boundary:** domain code depends on interfaces; SQLAlchemy types
  do not appear in domain signatures.
- Definition of Done from `docs/planning/PROJECT_MANAGEMENT.md` section 6
  applies to every PR.

## D-S001-05 - Branch and PR Rules

Defaults from the `git-workflow` skill:

```text
Integration branch: sprint/mvp-foundation
Working branches:   <prefix>/<descriptive-slug>  (feat/ fix/ docs/ test/ refactor/)
PR base:            sprint/mvp-foundation  (never main)
```

- One PR = one coherent outcome; 1-3 logical commits per PR
  (`commit-convention` format: `<type>(<scope>): <subject>`).
- Branch and commit names describe the change, never the task ID; the task ID
  belongs in the PR description only.
- The engineer opens the PR and stops before merge. The engineer never merges
  its own PR and never merges into `main`.
- Wait for a dependency PR to be merged into the sprint branch before starting
  the dependent one (see the task dependency column in `SPRINT_001.md`).
- This repo currently has **no remote**. Until one is configured, "open a PR"
  degrades to: keep the working branch, report the branch and commits, and stop
  before merging into the sprint branch. Configuring a remote is a human
  decision.

## D-S001-06 - Out of Scope

- Any LLM invocation, prompt, or provider SDK call (schema only).
- Source adapters other than the first RSS one.
- Event extraction, narrative matching, evidence building, instrument impact,
  alerts, overrides.
- Any dashboard page, template, or HTMX interaction beyond `/health`.
- Computing embeddings and choosing the embedding model source (open decision).
- Vector index tuning (HNSW/IVFFlat) - exact scan is sufficient at MVP volumes.
- VPS deployment, backup/restore procedure, retention policy, cost ceiling
  instrumentation.

## D-S001-07 - Follow-on Ownership

| Area | Owner / Future Sprint |
|---|---|
| Fed/FOMC, BLS, SEC adapters and remaining news sources | Sprint 002 (completes Roadmap Phase 2) |
| Embedding model source decision + ADR | human decision, then architect - before Phase 4 |
| First LLM slice: prompts, validation layer, LLMRun writes | Sprint 002/003 (Phase 3) |
| Dashboard, templates, HTMX | Phase 7 |
| Backup/restore, retention, observability, cost ceiling | Phase 10 |
| Dashboard access protection (non-local exposure) | human decision, before any VPS deploy |

## Wave 0 Checklist

These checkboxes are checked ONLY by a human, as the act of approval - the
agent proposes them unchecked and never checks them itself. Only a full set of
checked items = a green light for `engineer` (`governance`).

- [x] Confirm sprint branch (`sprint/mvp-foundation`).
- [x] Confirm scope inventory (D-S001-02).
- [x] Confirm validation strategy (D-S001-04).
- [x] Confirm out-of-scope items (D-S001-06).
- [x] Confirm follow-on ownership (D-S001-07).
- [x] Confirm that `ROADMAP.md`, the vision documents, and ADR-0001..ADR-0014
      are set to `Accepted`, and `SPRINT_001.md` to `Approved`.

Approved by: folga33 (user, in-conversation approval)
Approved date: 2026-08-17
