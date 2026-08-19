# Sprint 001 - Foundation to first real document

## Metadata

```text
Sprint: 001
Phase: Roadmap Phases 0, 1, 2 (partial - one source adapter only)
Status: Done
Approved By: folga33 (user, in-conversation approval)
Approved Date: 2026-08-17
Planned Start: 2026-08-17
Planned End:
Actual Start: 2026-08-17 (PR #1 merged)
Actual End: 2026-08-19 (PR #14 merged; sprint closed)
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
| S001-T010 | MVP Source registry seeded idempotently with tiers and publisher metadata | T006 | Done |
| S001-T011 | Cycle skeleton on APScheduler with a CycleRun record and overlap prevention | T004, T006 | Done |
| S001-T012 | One live RSS source adapter producing real Documents inside the cycle | T010, T011 | Done |
| S001-T013 | CI runs lint, type-check, and tests on every push and PR | T002 | Done |
| S001-T014 | `WORKFLOWS.md`, README quickstart, and reference docs match the running system | T012 | Done |

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

Closed 2026-08-19. Recorded from the merged result (PRs #1-#14 into
`sprint/mvp-foundation`), not from the plan.

### Completed

All 14 planned tasks, in 14 merged PRs:

| Task | PR | Delivered |
|---|---|---|
| S001-T001 | - | Wave 0 approval gate; human approval of vision/architecture/ADR-0001..0014/roadmap recorded 2026-08-17 |
| S001-T002 | #1 | Pinned dependencies, `src/` module layout, `scripts/check.py` = ruff + strict mypy + pytest |
| S001-T003 | #2 | `compose.yaml` (`app` + `pgvector/pgvector:pg16`), `.env.example`, typed `config/settings.py`, `GET /health` reporting DB + pgvector |
| S001-T004 | #3 | Alembic baseline; migration `0001` enables the `vector` extension; migrations never run on app startup |
| S001-T005 | #4 | Pure domain value objects/enums; no-infrastructure-import boundary test; forbidden-vocabulary test |
| S001-T006 | #5 | Source + Document persistence, migration `0002`, DB immutability trigger, natural-key dedupe via `ON CONFLICT DO NOTHING` |
| S001-T007 | #6 | Event + EvidencePack, migration `0003`; facts/claims separate (ADR-0008); EvidencePack fully immutable and versioned |
| S001-T008 | #7 | Narrative aggregate, migration `0004`; `identity_embedding vector(384)` placeholder; `EXCLUDE USING gist` on episodes; self-relation CHECK; the deferred `evidence_packs.narrative_id` FK |
| S001-T009 | #8 | Impact/Alert/LLMRun/AuditEntry, migration `0005`; append-only triggers; `ck_llm_runs_no_latest_alias`; the deferred `narrative_events.llm_run_id` FK |
| S001-T010 | #9 | Declarative, idempotent Source registry seed (3 Tier 1, 3 Tier 2, pairwise-distinct publishers) |
| S001-T013 | #10 | CI: lint + strict mypy, then unit + integration against a live pgvector service; verified red-then-green |
| (process) | #11 | Local pre-commit hooks mirroring `scripts/check.py`; tester/reviewer mechanical checks slimmed in root `CLAUDE.md` |
| S001-T011 | #12 | Cycle skeleton: `Clock`, `CycleRun`, six ordered stages, per-stage failure isolation, `run_once`, migration `0006`; overlap prevented twice (`max_instances=1` + partial unique index) |
| S001-T012 | #13 | RSS adapter interface + Bloomberg Markets implementation wired into the ingest stage; per-source failure isolation; dedupe reuse |
| S001-T014 | #14 | `docs/reference/WORKFLOWS.md` (clone to stored Document), README quickstart, refreshed `ARCHITECTURE_OVERVIEW.md` / `MODULE_MAP.md` / `docs/README.md` / root `CLAUDE.md` |

All eight sprint-level acceptance criteria in section 7 are met, including the
last one: no LLM call exists anywhere in this sprint's code.

### Not Completed

Nothing planned was dropped. What remains open was out of scope by design:

- Only one of the MVP source adapters was built (Bloomberg Markets RSS). The
  Fed/FOMC, BLS, SEC EDGAR, Reuters and AP adapters were explicitly deferred,
  so Roadmap Phase 2 is **partially** delivered, not complete.
- `Planned End` was never filled in during the sprint; the sprint ran
  2026-08-17 to 2026-08-19.

### Demonstrated Capability

```text
git clone -> docker compose up -> alembic upgrade head -> seed sources ->
one cycle -> real Bloomberg Markets Document rows in PostgreSQL,
recorded in a CycleRun, with a re-run creating zero duplicates
```

- All 12 MVP entities from `DOMAIN_MODEL.md` section 3 are persisted with
  migrations, plus `cycle_runs`.
- Domain invariants have DB-level backstops where they are genuine invariants:
  immutability triggers (Document, EvidencePack), append-only triggers
  (LLMRun, AuditEntry), pinned-model-ID CHECK, non-neutral-direction CHECK,
  episode-overlap EXCLUDE, self-relation CHECK, dedupe/idempotency
  constraints.
- Mechanical quality gates run without anyone remembering them: pre-commit
  locally, CI on every push/PR.

### Problems Discovered

Recorded in the newly created `docs/planning/PROBLEM_REGISTRY.md`:

- PRB-001 - a local `.env` can leak into the unit suite and make
  `test_missing_password_is_rejected` fail. Environment-level, pre-existing,
  hit repeatedly by testers in T007-T009, never fixed.
- PRB-002 - the Reuters and AP seed `feed_url` values are not live public
  feeds, so a full cycle records those sources as failed every run.
- PRB-003 - the three-condition NarrativeEvent assignment rule
  (`DOMAIN_MODEL.md` section 5) is not enforced anywhere yet. Correctly out of
  a persistence-only sprint's scope, but Phase 4 must close it.
- PRB-004 - `cycle_runs.update()` has no DB-level guard against re-updating an
  already-terminal row (inert today).
- PRB-005 - the planning registries themselves did not exist for the whole
  sprint, despite being referenced by reviewers and by
  `PROJECT_MANAGEMENT.md` section 6. Resolved by this closeout.

None is CRITICAL or HIGH.

### Decisions Required

No new decision was surfaced by the sprint. The four decisions open at sprint
start are still open, unchanged, and none of them blocked any task:

| Decision | Needed by |
|---|---|
| Embedding model source (local open-weight vs a second paid API) | Roadmap Phase 4 |
| Dashboard access protection when reachable beyond localhost | before any VPS deploy |
| Retention policy for document bodies and LLM `raw_output` | Phase 10 |
| Monthly LLM cost ceiling | before Phase 3 spending grows |

The embedding-model decision is now also the repayment trigger for TD-003
(the `vector(384)` placeholder), which raises its cost of delay slightly but
does not make it urgent.

### Technical Debt Added

Recorded in the newly created `docs/planning/TECHNICAL_DEBT.md`. All four
entries are LOW/MEDIUM and self-approvable per the `governance` matrix:

- TD-001 - the forbidden-vocabulary checker still misses a forbidden word
  buried in a separator-less identifier (`postsignal`); accepted deliberately
  because closing it reintroduces the `contradiction_signals` false positive.
- TD-002 - `EvidencePack.market_evidence` must-be-empty is enforced in the
  domain layer only, with no DB CHECK; accepted because ADR-0003 makes that
  data valid once a market feed exists, so a DB constraint would have to be
  removed later.
- TD-003 - `identity_embedding` is `vector(384)`, a documented placeholder
  dimension tied to the still-open embedding-model decision.
- TD-004 - `NarrativeInstrumentImpact` is a current-state row updated by
  upsert, with no assessment history.

### Lessons Learned

1. **Per-task documentation cannot be deferred.** `tech-writer` was skipped
   after the merges of T002-T006 and had to be caught up in one retroactive
   pass (commits `630154e`, `e2548cf`). The fix was made mid-sprint: the
   "Per-task delivery loop" section in root `CLAUDE.md` now makes the
   `engineer -> tester -> reviewer -> tech-writer` order explicit, and from
   T007 onward the doc sync ran inside each task's own PR. This is the
   sprint's main process lesson.
2. **The review loop paid for itself in defects tests alone did not catch.**
   Three real defects were found by `tester`/`reviewer` after the engineer
   self-reported green:
   - T006: the Document immutability trigger protected every content column
     but not the `id` primary key. Found via raw SQL against the live
     database, fixed in-PR (the guard `IF NEW.id IS DISTINCT FROM OLD.id` is
     in migration `0002` today).
   - T008: the fix for a genuine false positive in the forbidden-vocabulary
     test (`contradiction_signals`) over-corrected into a blind spot for
     compound snake_case identifiers such as `signal_strength`. Caught by
     `tester`, closed with token-based matching (`1ad9f17`).
   - T009: the ADR-0010 pinned-model-ID rule was enforced in the domain layer
     only, with no DB backstop, while the analogous ADR-0006 rule in the same
     migration did have one. Caught by `tester`, closed with
     `ck_llm_runs_no_latest_alias` (`5b18156`).

   Squash merges hide these in-PR corrections from `git log`; the review
   record, not the history, is the evidence.
3. **"Enforce it in the database too" is a judgment call, not a reflex.** The
   counter-example is `market_evidence`: the reviewer deliberately left it
   domain-only because ADR-0003 makes an empty `market_evidence` a temporary
   MVP condition, not a permanent invariant - a DB constraint would need
   removing once a market feed exists. Recorded as TD-002, an accepted
   trade-off, not a defect.
4. **Mechanical gates belong in hooks and CI, not in reviewer attention.**
   Mid-sprint (PR #11) pre-commit hooks were added mirroring
   `scripts/check.py`, and `tester`/`reviewer` were relieved of routinely
   re-running ruff/mypy/unit tests, with a fallback when CI cannot be
   confirmed green for the exact commit. This moved review effort onto live-DB
   behaviour and ADR compliance, which is where the three defects above were
   actually found.
5. **Deferred foreign keys need an explicit carrier.** Two FKs could not be
   created when their column was (`evidence_packs.narrative_id` in T007,
   `narrative_events.llm_run_id` in T008). Both were carried forward as an
   explicit line in the *next* task's scope and landed in `0004` and `0005`.
   Writing the deferral into the following task's spec, not a comment, is what
   kept them from being lost.
6. **A registry that does not exist does not get used.** Reviewers referenced
   `PROBLEM_REGISTRY.md` and `TECHNICAL_DEBT.md` throughout the sprint while
   neither file existed, so limitations lived in PR bodies and in
   `CURRENT_STATUS.md` section 9 instead. Both now exist and are backfilled.

### Follow-up

Carried into Sprint 002 planning (`architect`'s call, not decided here):

- Complete Roadmap Phase 2: the remaining MVP source adapters (Fed/FOMC, BLS,
  SEC EDGAR, and working newswire feeds), which also resolves PRB-002.
- Open Roadmap Phase 3, the first LLM slice: extraction, versioned prompts and
  output schemas, the deterministic validation layer (ADR-0002), and `LLMRun`
  recording on every material call (ADR-0007/ADR-0010) - writing into the
  schema this sprint built.
- Before Phase 3 spending grows, the monthly LLM cost ceiling decision needs
  an answer.
- Cheap hygiene, not sprint-worthy on its own: PRB-001 (document or fix the
  `.env` trap) and PRB-004 (terminal-`CycleRun` guard).
