# Sprint 001 - Foundation to first real document

## Metadata

```text
Sprint: 001
Phase: Roadmap Phases 0, 1, 2 (partial - one source adapter only)
Status: Approved
Approved By: folga33 (user, in-conversation approval)
Approved Date: 2026-08-17
Planned Start: 2026-08-17
Planned End:
Sprint Goal Owner: architect (planning) / engineer (implementation)
Depends On: human approval of PRODUCT_VISION, ARCHITECTURE_FOUNDATIONS,
            DOMAIN_MODEL, ADR-0001..ADR-0014, and ROADMAP
Sprint Branch: sprint/mvp-foundation
Task Branch Convention: <prefix>/<descriptive-slug>  (feat/ fix/ docs/ test/ refactor/)
Architecture / Product Sources:
  - docs/vision/PRODUCT_VISION.md
  - docs/vision/ARCHITECTURE_FOUNDATIONS.md
  - docs/vision/DOMAIN_MODEL.md
  - docs/adr/ADR-0001 .. ADR-0014
  - docs/planning/ROADMAP.md (Phases 0-2)
```

`Status` starts as `Planned`. The architect never sets it to `Approved` - a
human does, after reviewing and checking off the Wave 0 Checklist in
`S001_WAVE0_DECISIONS.md`. `engineer` does not start until the status is
`Approved` (`governance`).

## 0. Why This Sprint

Every architectural question that blocked implementation is now decided
(ADR-0010..ADR-0014). Nothing in the repo yet exercises those decisions: there
is a Python skeleton, no dependencies, no database, no schema, and no data. This
sprint turns approved documents into a running system that ingests a real
document from a real source, so that Phase 3 (the first LLM slice) starts
against real rows rather than fixtures.

## 1. Goal

```text
A cloned repo comes up with one command as app + PostgreSQL/pgvector, the full
domain schema is migrated, and the 5-minute cycle pulls real documents from one
live source into immutable, deduplicated Document rows.
```

## 2. In Scope

- Toolchain: dependencies, lint, type-check, test runner, one composite check
  command, CI.
- Docker Compose stack: `app` + `db` (PostgreSQL with pgvector), `.env.example`,
  typed settings, health endpoint (ADR-0013).
- Alembic migration baseline, including enabling the `pgvector` extension
  (ADR-0014).
- Pure domain value objects/enums from `DOMAIN_MODEL.md` section 4.
- SQLAlchemy models + migrations for every MVP entity in `DOMAIN_MODEL.md`
  section 3, including the Narrative identity embedding column.
- Seeded Source registry with tiers and publisher/independence metadata.
- Cycle skeleton driven by in-process APScheduler, with a CycleRun record,
  overlap prevention, and direct (non-scheduled) invocation (ADR-0011).
- **One** source adapter (a Tier 2 RSS/news source) producing real Documents
  inside the cycle, with per-source failure isolation.
- `docs/reference/WORKFLOWS.md`, README quickstart, reference docs refresh.

## 3. Out of Scope

- Any LLM call, prompt, or `LLMRun` write (schema only) - Phase 3, Sprint 002+.
- The remaining source adapters (Fed/FOMC, BLS, SEC, further news sources) -
  the first adapter establishes the pattern; the rest follow next sprint.
- Event extraction, narrative logic, evidence, impact, alerts, overrides.
- Any dashboard page, Jinja template, or HTMX interaction (only `/health`).
- Embedding computation and the choice of embedding model source (still an open
  decision; only the storage column exists this sprint).
- Deployment to a VPS, backup/restore procedure, retention policy.
- Any index tuning on the vector column (exact scan is fine at MVP volumes).

## 4. Dependencies

- **Approval gate:** `ROADMAP.md` must be `Status: Accepted` and this sprint
  `Status: Approved` with the Wave 0 Checklist checked before T002 starts.
- All ADRs referenced by tasks must be `Accepted`, not `Proposed` - an
  implementation relying on a `Proposed` ADR is a Critical review finding.
- Docker Desktop (or equivalent) available on the development host.
- No Anthropic API key needed this sprint (no LLM calls).

## 5. Task Breakdown

Each task below is one vertical slice and one PR. Full task specifications
follow in section 5.1; the table is a lightweight overview, not a second task
board.

| Task | Outcome | Depends on | Status |
|---|---|---|---|
| S001-T001 | Wave 0 decisions reviewed and approved by a human | - | Done |
| S001-T002 | Toolchain and dependency baseline; one command runs lint + types + tests | T001 | Done |
| S001-T003 | Docker Compose stack (`app` + Postgres/pgvector) with typed settings and a `/health` endpoint | T002 | Done |
| S001-T004 | Alembic baseline; `vector` extension enabled by migration | T003 | Done |
| S001-T005 | Pure domain value objects and enums, unit-tested without a database | T002 | Done |
| S001-T006 | Source + Document persisted, with immutability and dedupe enforced | T004, T005 | Done |
| S001-T007 | Event + EvidencePack persisted, facts/claims kept separate | T006 | Done |
| S001-T008 | Narrative, NarrativeEpisode, NarrativeEvent, NarrativeRelation persisted, incl. the identity embedding column | T007 | Done |
| S001-T009 | NarrativeInstrumentImpact, Alert, LLMRun, AuditEntry persisted (append-only where required) | T008 | Done |
| S001-T010 | MVP Source registry seeded idempotently with tiers and publisher metadata | T006 | TODO |
| S001-T011 | Cycle skeleton on APScheduler with a CycleRun record and overlap prevention | T004, T006 | TODO |
| S001-T012 | One live RSS source adapter producing real Documents inside the cycle | T010, T011 | TODO |
| S001-T013 | CI runs lint, type-check, and tests on every push and PR | T002 | TODO |
| S001-T014 | `WORKFLOWS.md`, README quickstart, and reference docs match the running system | T012 | TODO |

### 5.1 Task Specifications

#### S001-T001 - Wave 0 approval

- **Category:** Architecture. **Goal:** the human confirms the binding decisions
  in `S001_WAVE0_DECISIONS.md`.
- **Acceptance:** every box in the Wave 0 Checklist is checked; sprint `Status`
  is `Approved`; `ROADMAP.md` is `Accepted`; ADR-0001..ADR-0014 are `Accepted`.
- **Out of scope:** any code.
- **Refs:** `governance`, `S001_WAVE0_DECISIONS.md`.
- **Validation:** none - this is a gate, not an implementation.

#### S001-T002 - Toolchain and dependency baseline

- **Goal:** a fresh clone reaches "lint + types + tests green" with one
  documented command.
- **Scope:** `pyproject.toml` gains runtime dependencies implied by the accepted
  ADRs (FastAPI + ASGI server, SQLAlchemy, Alembic, PostgreSQL driver, the
  pgvector Python integration, the Anthropic SDK, APScheduler, Pydantic /
  pydantic-settings, an HTTP client, a feed parser) and dev dependencies (pytest,
  ruff, mypy). Tool configuration lives in `pyproject.toml`. Package layout under
  `src/` is reorganized into the module map (`ingestion/`, `domain/`,
  `persistence/`, `cycle/`, `api/`, `config/`).
- **Acceptance:**
  - one documented command runs lint, type-check, and tests, all green;
  - dependencies are version-pinned or bounded, and every runtime dependency
    traces to an accepted ADR;
  - mypy runs in strict mode over `src/` with no ignores added to silence real
    errors;
  - the existing placeholder test still passes.
- **Out of scope:** Docker, database, CI.
- **Refs:** ADR-0010, ADR-0011, ADR-0012, ADR-0014; `ARCHITECTURE_FOUNDATIONS.md`
  section 2; root `CLAUDE.md`.
- **Validation:** the composite check command, run from a clean checkout.
- **Note:** all dependencies here are free/open-source. Adding anything paid
  requires human approval first.

#### S001-T003 - Docker Compose stack, settings, health endpoint

- **Goal:** `docker compose up` yields a running app talking to PostgreSQL with
  pgvector available.
- **Scope:** `compose.yaml` with `app` and `db` (a PostgreSQL image that ships
  pgvector) and a named data volume; `.env.example` committed and `.env`
  git-ignored; a typed settings object (no `os.environ` reads scattered through
  the code); a FastAPI app exposing `GET /health` that reports database
  connectivity and whether the `vector` extension is available.
- **Acceptance:**
  - from a clean checkout plus a copied `.env`, one compose command brings both
    services up;
  - `/health` returns a success payload including `database: ok` and
    `pgvector: available`;
  - no secret value is committed;
  - the app container holds no durable state (destroying it and re-creating it
    changes nothing).
- **Out of scope:** migrations, any domain endpoint, any HTML page, VPS deploy.
- **Refs:** ADR-0013, ADR-0014, ADR-0005.
- **Validation:** an integration test hitting `/health` against the compose
  database; manual `compose up` documented in the PR.

#### S001-T004 - Alembic baseline and the pgvector extension migration

- **Goal:** schema changes have exactly one mechanism, and the vector extension
  exists before anything needs it.
- **Scope:** Alembic configured against the SQLAlchemy metadata and the settings
  object; the first migration enables the `vector` extension; migrations run as
  an explicit command, never implicitly on app startup.
- **Acceptance:**
  - upgrade to head from an empty database succeeds and is repeatable;
  - downgrade of the baseline is defined;
  - a vector column can be created in a later migration without further manual
    steps;
  - starting the app does not run migrations.
- **Out of scope:** entity tables.
- **Refs:** ADR-0013 (explicit migration step), ADR-0014.
- **Validation:** an integration test that upgrades a throwaway database to head.

#### S001-T005 - Domain value objects and enums

- **Goal:** the vocabulary of `DOMAIN_MODEL.md` section 4 exists as real Python
  types with no infrastructure dependency.
- **Scope:** SourceTier, ValidityStatus, LifecycleStatus, ImpactDirection,
  ImpactHorizon, OverrideState, CandidateStatus, EpistemicCategory, RelationType,
  Instrument, plus EvidenceRef and the IdentityEmbedding descriptor (model name +
  version + vector, without any storage concern).
- **Acceptance:**
  - every value object from the domain model table is represented, with the
    exact member names used in the document;
  - importing the domain package pulls in no database, HTTP, or LLM code
    (asserted by a test);
  - illegal values are rejected at construction;
  - no `sentiment_score` or equivalent exists anywhere.
- **Out of scope:** ORM mapping, persistence.
- **Refs:** `DOMAIN_MODEL.md` sections 4, 7; `ARCHITECTURE_FOUNDATIONS.md`
  principle 1; ADR-0006.
- **Validation:** unit tests, no database.

#### S001-T006 - Source and Document persistence

- **Goal:** the ingestion aggregate is storable, immutable, and deduplicating.
- **Scope:** SQLAlchemy models and a migration for Source and Document; the
  repository boundary (domain code depends on an interface, not on a session);
  the deduplication natural key (source + source-native id/URL + published
  timestamp); `processing_status` as a monotonic value.
- **Acceptance:**
  - a Document round-trips through the store unchanged;
  - inserting the same document twice yields one row, not an error path the
    caller must handle ad hoc;
  - an update attempt on a collected Document's content is rejected;
  - a `collected_at < published_at` case is flagged as a data-quality issue,
    not silently corrected;
  - domain-level invariants are unit-testable without a database.
- **Out of scope:** fetching anything over the network.
- **Refs:** `DOMAIN_MODEL.md` sections 3 (Ingestion), 5; ADR-0005.
- **Validation:** unit tests for invariants + integration tests against the
  compose database.

#### S001-T007 - Event and EvidencePack persistence

- **Goal:** extraction and evidence have a stable shape to write into.
- **Scope:** models and migration for Event (with `extracted_facts` and
  `source_claims` as separate JSONB structures) and EvidencePack (versioned
  snapshot).
- **Acceptance:**
  - an Event cannot be stored with an empty `source_ids`;
  - facts and claims are separate columns/structures - no code path merges them;
  - an EvidencePack rebuild creates a new `evidence_version` instead of mutating
    a row;
  - `independent_source_count <= source_count` is enforced.
- **Out of scope:** producing events or evidence (no extractor, no builder).
- **Refs:** ADR-0008, ADR-0003; `DOMAIN_MODEL.md` section 3.
- **Validation:** invariant unit tests + persistence integration tests.

#### S001-T008 - Narrative aggregate persistence, including the identity embedding column

- **Goal:** the product's central object is storable, with its retrieval column
  in place from the start.
- **Scope:** models and migration for Narrative (including `identity_embedding`
  as a `vector` column plus `embedding_model` and `embedding_version`),
  NarrativeEpisode, NarrativeEvent (assignment, with shortlist reference and
  LLMRun reference fields), NarrativeRelation. Also adds the foreign key from
  `evidence_packs.narrative_id` to `narratives.id` (T007 created the column
  and its unique-with-`evidence_version` constraint before the `narratives`
  table existed, so the FK could not be added then - reviewer note on
  S001-T007, carried forward here so it is not dropped).
- **Acceptance:**
  - `canonical_key` is unique;
  - `evidence_packs.narrative_id` has a foreign key to `narratives.id`;
  - a Narrative without an `economic_mechanism` or `market_interpretation` is
    rejected;
  - a Narrative with a NULL `identity_embedding` is fully valid (the embedding is
    derived, never identity);
  - a nearest-neighbour query over the vector column executes successfully
    against seeded test vectors;
  - self-relations are rejected; episodes of one narrative cannot overlap.
- **Out of scope:** computing embeddings, choosing the embedding model, any
  index tuning, any matching logic.
- **Refs:** ADR-0001, ADR-0014; `DOMAIN_MODEL.md` sections 3, 4, 5.
- **Validation:** invariant unit tests + an integration test performing a vector
  similarity query.
- **Dependency note:** the vector dimension is a migration-level constant; pick
  a documented placeholder and record in the PR that changing it later is a
  migration plus a re-embedding pass.

#### S001-T009 - Impact, alert, and governance persistence

- **Goal:** the remaining MVP entities exist, with their append-only guarantees.
- **Scope:** models and migration for NarrativeInstrumentImpact, Alert, LLMRun,
  AuditEntry.
- **Acceptance:**
  - one current impact assessment per (narrative, instrument);
  - a non-neutral direction without a rationale and non-empty `evidence_refs` is
    rejected;
  - Alerts are unique per (narrative, type, trigger);
  - LLMRun and AuditEntry reject updates and deletes (append-only, enforced in
    the repository and covered by a test);
  - LLMRun carries every reproducibility field listed in
    `ARCHITECTURE_FOUNDATIONS.md` section 7, including `provider`, `model`,
    `model_version`, `prompt_version`.
- **Out of scope:** writing any real LLM run or audit entry from a live flow.
- **Refs:** ADR-0006, ADR-0007, ADR-0009, ADR-0010.
- **Validation:** invariant unit tests + persistence integration tests.

#### S001-T010 - Source registry seed

- **Goal:** the MVP sources exist as data, with the metadata later phases need.
- **Scope:** an idempotent seed command creating Fed/FOMC, BLS, SEC (Tier 1) and
  two or three news/RSS sources (Tier 2), each with tier, endpoint config,
  publisher/owner, and an independence grouping key.
- **Acceptance:**
  - running the seed twice leaves the registry unchanged;
  - every seeded source has exactly one tier and a publisher/independence key;
  - the seed is data-driven (a declarative file), not hard-coded branching.
- **Out of scope:** fetching from any of them.
- **Refs:** `DOMAIN_MODEL.md` section 3 (Source); `PRODUCT_VISION.md` section 4;
  ADR-0003 (independence is needed later).
- **Validation:** integration test running the seed twice and asserting stability.

#### S001-T011 - Processing cycle skeleton on APScheduler

- **Goal:** the 5-minute heartbeat exists, records what it did, and cannot
  overlap itself.
- **Scope:** APScheduler started with the FastAPI lifespan; the cycle as an
  ordered list of stages (ingest, extract, narratives, evidence, state, alerts)
  where only "ingest" is non-empty later; a CycleRun record (start, end, per
  stage outcome, per source outcome, failure reason); `max_instances=1` plus a
  data-level guard; `coalesce` with a bounded misfire grace; a direct
  entrypoint that runs one cycle without the scheduler.
- **Acceptance:**
  - a cycle produces exactly one CycleRun record with a terminal state, including
    when a stage raises;
  - two overlapping triggers result in one execution;
  - after simulated downtime, one catch-up cycle runs, not a backlog;
  - the cycle can be executed in a test by calling it directly, with an injected
    clock;
  - stopping the app stops the scheduler cleanly.
- **Out of scope:** any real work inside the stages.
- **Refs:** ADR-0004, ADR-0011; `ARCHITECTURE_FOUNDATIONS.md` section 4.
- **Validation:** unit tests with an injected clock + an integration test of two
  consecutive cycles.

#### S001-T012 - First source adapter: one RSS source to Documents

- **Goal:** the system ingests real data end to end - the sprint's payoff slice.
- **Scope:** a source adapter interface plus one concrete Tier 2 RSS/news
  implementation; fetch, normalize into Documents, deduplicate against existing
  rows, persist; wire it into the cycle's ingest stage; per-source failure
  isolation (a failing source is recorded in the CycleRun and does not fail the
  cycle); network access confined to the adapter layer.
- **Acceptance:**
  - a scheduled cycle against the live feed creates Document rows with source,
    url, published_at, collected_at, title, and body/content reference;
  - re-running the cycle immediately creates zero new rows;
  - a simulated fetch failure (timeout, HTTP error, malformed feed) leaves the
    cycle successful, the source marked failed in the CycleRun, and no partial
    Document written;
  - adapter parsing is tested against recorded fixtures, with no network access
    in unit tests;
  - adding a second adapter later requires implementing the interface only.
- **Out of scope:** the Fed/FOMC, BLS, and SEC adapters; any interpretation of
  content; rate-limit strategy beyond a simple timeout and retry-free failure.
- **Refs:** ADR-0004, ADR-0005; `ROADMAP.md` Phase 2; `DOMAIN_MODEL.md`
  section 3 (Ingestion).
- **Validation:** fixture-based unit tests + one integration test against the
  live feed, marked so it can be excluded from CI.

#### S001-T013 - CI pipeline

- **Goal:** the quality gate runs without anyone remembering to run it.
- **Scope:** a CI workflow running lint, type-check, and tests on push and on
  PRs into `sprint/*` and `main`, with a PostgreSQL/pgvector service for
  integration tests; network-dependent tests excluded by marker.
- **Acceptance:**
  - CI is green on the sprint branch;
  - a deliberately broken lint rule or failing test fails the pipeline;
  - integration tests run against a real pgvector-enabled database in CI;
  - no secret is required for CI to pass.
- **Out of scope:** deployment, coverage gates, release automation.
- **Refs:** `ROADMAP.md` Phase 0; `git-workflow`.
- **Validation:** the pipeline itself, plus one intentional-failure run
  documented in the PR.

#### S001-T014 - Workflow and reference documentation

- **Goal:** the documented way to run the system matches the built system.
- **Scope:** `docs/reference/WORKFLOWS.md` (setup, compose up, migrations, seed,
  running one cycle manually, running checks, running tests); README quickstart;
  refresh `docs/reference/ARCHITECTURE_OVERVIEW.md` and
  `docs/reference/MODULE_MAP.md` to the delivered shape; update `docs/README.md`.
- **Acceptance:**
  - a person who has never seen the repo can go from clone to a stored Document
    following only `WORKFLOWS.md`;
  - every command in the document was actually executed;
  - the module map matches the real package layout;
  - root `CLAUDE.md` conventions still match reality (amend if not).
- **Out of scope:** API reference documentation, user-facing docs.
- **Refs:** `product-architecture` skill; `PROJECT_MANAGEMENT.md` section 6.
- **Validation:** a clean-clone walkthrough, described in the PR.

## 6. Suggested PR Waves

PR boundaries are the engineer's call; this is the expected dependency shape.

1. **Wave 0 - approval:** T001.
2. **Wave 1 - it runs:** T002, T003, T004, T005 (T005 parallel with T003/T004).
3. **Wave 2 - it stores:** T006, then T007 -> T008 -> T009; T010 in parallel
   after T006; T013 in parallel any time after T002.
4. **Wave 3 - it ingests:** T011, then T012.
5. **Wave 4 - closeout:** T014.

## 7. Acceptance Criteria

1. `docker compose up` plus the documented migration and seed commands yields a
   system whose `/health` reports database connectivity and pgvector
   availability.
2. Every MVP entity in `DOMAIN_MODEL.md` section 3 is persisted with migrations,
   and each aggregate's invariants from section 5 are covered by tests.
3. Domain rules and value objects are unit-testable with no database, no HTTP,
   and no LLM.
4. The 5-minute cycle runs on APScheduler, records a CycleRun, does not overlap
   itself, and is directly invocable in tests with an injected clock.
5. Real Documents from one live source appear in PostgreSQL; re-running a cycle
   creates no duplicates; a source failure is isolated and visible.
6. CI runs lint, type-check, and tests green on the sprint branch.
7. `WORKFLOWS.md` takes a newcomer from clone to a stored Document.
8. No LLM call is made anywhere in this sprint's code.

## 8. Risks

| Risk | Mitigation |
|---|---|
| The schema is built for all entities before most are used, inviting over-modelling | Keep uncertain shapes in JSONB (ADR-0005); do not add relationships no invariant requires |
| Vector dimension is chosen before the embedding model is | Treat it as a documented placeholder; the column is derived data, so a later change is a migration plus a re-embedding pass, not a data loss |
| Chosen RSS source turns out to be unstable or blocks us | Adapter interface is the deliverable; swapping the concrete source is a small change - pick the simplest well-behaved feed first |
| Integration tests need a real database, slowing feedback | Split unit (no infra, always run) from integration (compose/CI service) with markers, from T006 onward |
| Sprint spans three roadmap phases and could sprawl | Only one adapter, zero LLM calls, and zero UI - all three are hard out-of-scope lines |
| Windows development host vs Linux containers | All commands documented for both in `WORKFLOWS.md`; CI runs Linux |

## 9. Review

### Completed

- (filled at sprint close)

### Not Completed

- (filled at sprint close)

### Demonstrated Capability

- (filled at sprint close)

### Problems Discovered

- (filled at sprint close)

### Decisions Required

- (filled at sprint close)

### Technical Debt Added

- (filled at sprint close)

### Lessons Learned

- (filled at sprint close)

### Follow-up

- (filled at sprint close)
