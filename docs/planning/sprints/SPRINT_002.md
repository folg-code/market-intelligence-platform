# Sprint 002 - The first LLM slice: Document to Event, validated and audited

## Metadata

```text
Sprint: 002
Phase: Roadmap Phase 3 (Event extraction - the first LLM slice)
Status: Approved
Approved By: folga33 (user, in-conversation approval)
Approved Date: 2026-08-19
Planned Start: 2026-08-19
Planned End:
Sprint Goal Owner: architect (planning) / engineer (implementation)
Depends On: human approval of ADR-0015 and ADR-0016, and of this sprint via the
            Wave 0 Checklist in S002_WAVE0_DECISIONS.md
Sprint Branch: sprint/first-llm-slice
Task Branch Convention: <prefix>/<descriptive-slug>  (feat/ fix/ docs/ test/ refactor/)
Architecture / Product Sources:
  - docs/vision/PRODUCT_VISION.md
  - docs/vision/ARCHITECTURE_FOUNDATIONS.md sections 5, 6, 7, 9
  - docs/vision/DOMAIN_MODEL.md sections 3, 5, 7
  - docs/adr/ADR-0002, ADR-0004, ADR-0007, ADR-0008, ADR-0010
  - docs/adr/ADR-0015 (Proposed), ADR-0016 (Proposed)
  - docs/planning/ROADMAP.md Phase 3
  - docs/planning/sprints/SPRINT_001.md section 9 (retro)
  - docs/planning/PROBLEM_REGISTRY.md, docs/planning/TECHNICAL_DEBT.md
```

`Status` starts as `Planned`. The architect never sets it to `Approved` - a
human does, after reviewing and checking off the Wave 0 Checklist in
`S002_WAVE0_DECISIONS.md`. `engineer` does not start until the status is
`Approved` **and** ADR-0015 and ADR-0016 are `Accepted` (`governance`; an
implementation relying on a `Proposed` ADR is a Critical review finding).

## 0. Why This Sprint

Sprint 001 built the whole schema for LLM-assisted work and left every row of it
empty on purpose. `llm_runs`, `events`, and `evidence_packs` exist, complete with
append-only and immutability triggers, and nothing has ever written to them. The
cycle collects real Documents every five minutes and each one sits at
`processing_status = COLLECTED` forever. The system stores; it does not yet
understand.

This sprint fills those tables for the first time, for exactly one step:
**Document to Event**. That makes it the sprint that decides, once and for every
later phase, how a model call is made, versioned, validated, priced, and
recorded.

The human owner chose Phase 3 over finishing Phase 2 deliberately: the remaining
source adapters are repeatable work against a pattern that already exists, while
the candidate/validation layer (ADR-0002) and the audit trail (ADR-0007) are the
real unknowns. More documents without extraction is just more unprocessed rows.

## 1. Goal

```text
Collected Documents are turned into Events inside the 5-minute cycle by a
pinned, cheap model behind a deterministic validator - every call recorded as an
LLMRun in the same transaction as the Event it produced, every rejection kept,
and a cycle with nothing new to process costing exactly nothing.
```

## 2. In Scope

- A unit-of-work boundary so an Event and its `LLMRun` are written atomically
  (repositories stop committing internally).
- A new `llm/` module: client port, an Anthropic implementation, a fixture-driven
  fake, versioned prompt and output-schema artifacts, and one declarative
  task-type -> pinned model + token-rate configuration table.
- A new `extraction/` module: candidate parsing and the deterministic validation
  layer producing `accepted` / `proposed` / `rejected` (ADR-0002), unit-testable
  with no model, no HTTP, and no database.
- The extraction service: candidate -> verdict -> Event (only when `accepted`)
  plus `LLMRun` (always), in one transaction.
- The cycle's `extract` stage: a work queue over `COLLECTED` Documents, a
  per-cycle document cap, per-document failure isolation, and monotonic
  `processing_status` advance.
- A deterministic monthly budget guard enforcing the ADR-0015 ceiling, computed
  from recorded `token_usage`.
- One live smoke run against the real Anthropic API, late in the sprint.
- Registry hygiene closing PRB-002 (seed honesty), PRB-001 (`.env` test trap),
  and PRB-004 (terminal-`CycleRun` guard).
- Documentation sync per the root `CLAUDE.md` delivery loop, plus a nested
  `CLAUDE.md` for the new `llm/` module.

## 3. Out of Scope

Full list and rationale in `S002_WAVE0_DECISIONS.md` D-S002-07. The hard lines:

- The remaining Phase 2 source adapters (Fed/FOMC, BLS, SEC EDGAR, further
  newswires) - deferred by the human; PRB-002 is closed by deactivating
  adapter-less sources, not by building adapters.
- Anything narrative: candidate matching, `canonical_key` assignment,
  `NarrativeEvent` writes, the three-condition rule (PRB-003 stays open).
- EvidencePack generation, instrument impact, alerts, overrides.
- Any dashboard page or template; the review surface for `proposed` candidates
  is Phase 7.
- Embeddings and the embedding-model-source decision (TD-003 stays open).
- Batch API usage, prompt caching, multi-model routing.
- Retention policy for `raw_output`, cost dashboards, per-stage timing
  observability (Phase 10).
- Deployment, backup/restore.

## 4. Dependencies

- **Approval gate:** `ROADMAP.md` is `Status: Accepted` (verified - it is).
  This sprint must be `Status: Approved` with the Wave 0 Checklist checked, and
  **ADR-0015 and ADR-0016 must be `Accepted`**, before T002 starts.
- **Anthropic API key:** not held at sprint start; the human obtains one during
  the sprint. Every task except S002-T011 runs against a fixture-driven fake
  client. The key is a secret - it is read through the typed settings object,
  placeholder only in `.env.example`, never committed.
- Docker Desktop (or equivalent) and the compose database, as in Sprint 001.
- A populated `documents` table to extract from: run the existing cycle against
  the live Bloomberg feed for real inputs, or use fixtures.

## 5. Task Breakdown

Each task is one vertical slice and one PR. Full specifications follow in
section 5.1; the table is a lightweight overview, not a second task board.

| Task | Outcome | Depends on | Status |
|---|---|---|---|
| S002-T001 | Wave 0 decisions and ADR-0015 / ADR-0016 approved by a human | - | Done |
| S002-T002 | Repositories stop committing; a unit of work makes multi-repository writes atomic | T001 | Done |
| S002-T003 | The unit suite passes regardless of ambient `POSTGRES_*` env or a local `.env` (PRB-001) | T001 | Done |
| S002-T004 | A terminal `CycleRun` row cannot be updated again (PRB-004) | T001 | Done |
| S002-T005 | A clean cycle over the seeded registry records zero expected source failures (PRB-002) | T001 | Done |
| S002-T006 | An LLM client port with versioned prompt/schema artifacts, a pinned-model rate table, and a fixture-driven fake | T001 | Done |
| S002-T007 | A deterministic validator turning raw model output into `accepted` / `proposed` / `rejected`, with no infrastructure | T006 | Done |
| S002-T008 | Extraction service writing Event + `LLMRun` in one transaction, driven by the fake client | T002, T006, T007 | Todo |
| S002-T009 | The cycle's extract stage: work queue, per-cycle cap, per-document isolation, status advance | T008 | Todo |
| S002-T010 | Monthly budget guard enforcing the ADR-0015 ceiling from recorded token usage | T009 | Todo |
| S002-T011 | One live Anthropic run producing a real Event and a real `LLMRun` | T009, API key | Todo |
| S002-T012 | Reference docs, `WORKFLOWS.md`, and `CURRENT_STATUS.md` match the delivered system | T011 | Todo |

### 5.1 Task Specifications

#### S002-T001 - Wave 0 approval and the two cost ADRs

- **Category:** Architecture. **Goal:** the human confirms the binding decisions
  in `S002_WAVE0_DECISIONS.md` and accepts ADR-0015 and ADR-0016.
- **Scope:** review and approval only.
- **Acceptance:** every box in the Wave 0 Checklist is checked; ADR-0015 and
  ADR-0016 read `Status: Accepted` with an approver and date; this sprint reads
  `Status: Approved`.
- **Out of scope:** any code.
- **Depends on:** -.
- **Refs:** `governance`, `S002_WAVE0_DECISIONS.md`, ADR-0015, ADR-0016.
- **Validation:** none - this is a gate, not an implementation.

#### S002-T002 - Unit of work: repositories stop committing

- **Category:** Technical Debt / Architecture.
- **Goal:** a caller can write to several repositories and commit once, so an
  Event and its `LLMRun` cannot be persisted apart.
- **Scope:** every repository in `persistence/` replaces its internal
  `session.commit()` with `flush()` (keeping `refresh()` where the caller needs
  server-assigned values); a unit-of-work boundary owns the session lifecycle and
  the single commit/rollback; existing callers (`cycle/run_cycle.py`,
  `cycle/ingest.py`, `persistence/seed_sources.py`, tests) are updated to open
  the boundary explicitly. Repository *interfaces* in `domain/repositories.py`
  keep their signatures - the transaction boundary must not leak a SQLAlchemy
  type into domain code.
- **Acceptance:**
  - no repository implementation calls `commit()`;
  - two writes through two different repositories inside one unit of work are
    both visible after commit and both absent after rollback (integration test
    against the live database);
  - the existing idempotent paths still behave: `DocumentRepository.add`
    (`ON CONFLICT DO NOTHING`), `SourceRepository.add`, `AlertRepository.add`,
    and `NarrativeInstrumentImpactRepository.upsert` are re-verified inside the
    new boundary, since `ON CONFLICT` semantics were previously exercised with a
    commit per call;
  - `CycleRun`'s two-phase write (RUNNING then terminal) still produces exactly
    one row with a terminal state, including when a stage raises - the cycle's
    failure record must survive the rollback of the failed stage's work, so the
    boundary must be per stage, not one transaction for the whole cycle;
  - the whole existing test suite passes unchanged in intent;
  - no SQLAlchemy type appears in any `domain/` signature (existing boundary
    test still green).
- **Out of scope:** nested transactions/savepoints, retry-on-serialization,
  connection pooling changes, any new entity.
- **Depends on:** T001.
- **Refs:** reviewer's S001-T009 observation (`SPRINT_001.md` section 9);
  `S002_WAVE0_DECISIONS.md` D-S002-04 clause 6; `ARCHITECTURE_FOUNDATIONS.md`
  principle on the repository boundary; root `CLAUDE.md`.
- **Validation:** integration tests for commit and rollback across two
  repositories; a failure-injection test asserting no partial write; the full
  existing suite as a regression net.
- **Size note:** this is the largest diff in the sprint (13 repositories) but is
  mechanical and one coherent outcome. If it exceeds ~600 lines of meaningful
  change, split by bounded context (ingestion repositories first, then the rest)
  rather than by file.

#### S002-T003 - Make the unit suite immune to the ambient environment (PRB-001)

- **Category:** Bug / Maintenance.
- **Goal:** `pytest tests/unit` is green regardless of a local `.env` or an
  inherited `POSTGRES_*` environment variable.
- **Scope:** `tests/unit/test_settings.py::test_missing_password_is_rejected`
  gains `monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)`, matching what
  its sibling already does for `POSTGRES_HOST`; a `tests/conftest.py` is added
  (the repo currently has none) with an `autouse` fixture that clears `POSTGRES_*`
  for unit tests; the trap is documented in one line in `WORKFLOWS.md`.
- **Acceptance:**
  - with `POSTGRES_PASSWORD` exported in the shell, the unit suite is green;
  - with a fully populated `.env` present and a dotenv pytest plugin installed,
    the unit suite is green;
  - integration tests, which legitimately need those variables, still pass;
  - PRB-001 is moved to `RESOLVED` in `PROBLEM_REGISTRY.md`.
- **Out of scope:** changing `Settings` itself; changing how CI supplies
  credentials (the `.env`-file workaround in `ci.yml` may stay, but a note
  records that it is no longer load-bearing).
- **Depends on:** T001.
- **Refs:** `PROBLEM_REGISTRY.md` PRB-001; `.github/workflows/ci.yml`;
  `src/moj_projekt/config/settings.py`.
- **Validation:** run the unit suite twice - once with the variables exported,
  once without - and record both in the PR.

#### S002-T004 - A terminal `CycleRun` cannot be updated again (PRB-004)

- **Category:** Bug / Architecture.
- **Goal:** the database refuses a second write to a `CycleRun` that has already
  reached a terminal status, in the same pattern as the existing immutability
  and append-only triggers.
- **Scope:** a new Alembic migration adding a `BEFORE UPDATE` trigger on
  `cycle_runs` that rejects any update to a row already in a terminal status,
  while still permitting the legitimate RUNNING -> terminal transition; a
  downgrade that drops it.
- **Acceptance:**
  - the normal cycle write path (insert RUNNING, update to terminal) is
    unaffected;
  - a second update of a terminal row raises at the database level, not only in
    Python;
  - `upgrade` then `downgrade` then `upgrade` is clean;
  - PRB-004 is moved to `RESOLVED` in `PROBLEM_REGISTRY.md`.
- **Out of scope:** retry/resume semantics for cycles, any change to
  `CycleRunRepository`'s interface.
- **Depends on:** T001. Independent of T002 - but if T002 merges first, re-run
  this task's integration test inside the new transaction boundary.
- **Refs:** `PROBLEM_REGISTRY.md` PRB-004; migration `0006`; ADR-0011.
- **Validation:** integration test against the live database asserting the
  rejected second update.

#### S002-T005 - Seed registry honesty: no expected source failures (PRB-002)

- **Category:** Bug / Maintenance.
- **Goal:** a clean cycle over the seeded registry produces zero expected
  per-source failures, so a recorded failure means something again.
- **Scope:** in `persistence/seed_data/sources.py`, every source that has no
  adapter (`fed_fomc`, `bls`, `sec_edgar` - `source_type: official_api`) or no
  live feed (`reuters_markets`, `ap_news`) is seeded `active=False`, with the
  reason stated in the module docstring next to the entry. If a genuinely live,
  public RSS feed for Reuters or AP can be verified working during the task, the
  URL may be corrected and the source left active instead - that is the better
  outcome, but it must be *verified*, not assumed. The seed remains declarative
  data with no per-source branching, and remains idempotent; re-seeding must
  update the `active` flag of an already-seeded source rather than silently
  leaving it (`SourceRepository.add` is currently `ON CONFLICT DO NOTHING`, so
  this needs an explicit decision recorded in the PR: either widen the seed path
  to update `active`, or document that a re-seed onto an existing registry
  requires a manual flag change).
- **Acceptance:**
  - a full cycle against the seeded registry records `source_outcomes` with no
    failures;
  - the count of active sources equals the count of sources that actually have a
    working adapter and feed;
  - seeding twice leaves the registry in the same state, including `active`;
  - the deactivation reason is discoverable from the repository, not only from
    the PR;
  - PRB-002 is moved to `RESOLVED` (or `MITIGATED`, if any URL correction is
    left open) in `PROBLEM_REGISTRY.md`.
- **Out of scope:** building any adapter; changing the adapter interface; a
  registry admin UI.
- **Depends on:** T001.
- **Refs:** `PROBLEM_REGISTRY.md` PRB-002; `S002_WAVE0_DECISIONS.md`
  D-S002-04 clause 14; `persistence/seed_sources.py`; `cycle/ingest.py`.
- **Validation:** integration test running the seed twice and asserting registry
  stability and the active/inactive split; a cycle test asserting an empty
  failure set.
- **Note:** this narrows live ingestion to one active source. That is accepted:
  document volume stays comfortably inside the ADR-0015 cost model, and source
  breadth is a Phase 2 concern, not this sprint's.

#### S002-T006 - LLM client port, versioned prompt artifacts, and the model rate table

- **Category:** Feature / Architecture.
- **Goal:** the system can *make* a model call - through one narrow port, with a
  versioned prompt and output schema and a pinned model - without any domain
  wiring and without an API key.
- **Scope:** a new `llm/` module containing:
  - `LLMClient` protocol: one method taking a rendered prompt plus inference
    parameters and returning a raw response with token usage and latency. No
    domain type crosses this port.
  - `AnthropicClient`: the real implementation over the pinned model, using the
    provider's structured-output mechanism, reading the API key through the
    existing typed settings object. Recorded token usage includes
    `cache_creation_input_tokens` and `cache_read_input_tokens` (expected zero -
    ADR-0015 clause 6).
  - `FakeLLMClient`: fixture-driven, deterministic, counts calls. Used by every
    other task in the sprint.
  - Prompt artifacts on disk under `llm/prompts/`, versioned by filename or an
    explicit version field: a system prompt and an event-extraction prompt, each
    with a version string; plus the event-extraction **output schema `v1`** as a
    versioned artifact.
  - `llm/models.py`: one declarative table mapping task type ->
    (pinned model id, model version, input rate per 1M tokens, output rate per
    1M tokens). Extraction maps to `claude-haiku-4-5-20251001`.
  - `src/moj_projekt/llm/CLAUDE.md` (nested module context): the prompt-version
    bump rule, the never-commit-secrets rule, the pinned-id rule, and the fact
    that this module is the only place allowed to talk to the Anthropic SDK.
- **Acceptance:**
  - the module exposes exactly one way to call a model; nothing outside `llm/`
    imports the Anthropic SDK (asserted by a test, in the same style as the
    existing domain boundary test);
  - prompt and schema artifacts carry explicit versions, and a helper returns
    them for recording on an `LLMRun`;
  - no model identifier anywhere is an undated alias; a test asserts the
    configured extraction model matches the pinned dated form and is rejected by
    the same rule `LLMRun` uses;
  - `FakeLLMClient` reproduces a recorded response byte-for-byte and reports how
    many times it was called;
  - constructing `AnthropicClient` without an API key fails with a clear error
    and is never reached by the default test run;
  - output schema `v1` carries candidate mechanism, affected entities/exposures,
    and candidate interpretation as extracted material, and carries **no** field
    expressing narrative membership, instrument relevance, or direction
    (D-S002-04 clause 11 / PRB-003 constraint);
  - `extracted_facts` and `source_claims` are separate arrays in the schema, with
    no field that merges them (ADR-0008).
- **Out of scope:** calling the real API (T011); the validator (T007); writing
  any row; retries and rate-limit backoff beyond a single bounded timeout.
- **Depends on:** T001. Parallelizable with T002-T005.
- **Refs:** ADR-0007, ADR-0010, ADR-0015, ADR-0016, ADR-0008;
  `ARCHITECTURE_FOUNDATIONS.md` sections 5 and 7; `module-context` skill.
- **Validation:** unit tests only - fixture round-trip through the fake, the
  no-SDK-outside-`llm/` boundary test, the pinned-id test, and a schema test
  asserting the forbidden fields are absent.

#### S002-T007 - The deterministic validation layer for extraction output

- **Category:** Feature.
- **Goal:** raw model output becomes exactly one of `accepted` / `proposed` /
  `rejected`, decided by deterministic code with no model, no HTTP, and no
  database (ADR-0002).
- **Scope:** a new `extraction/` module with a parser (raw text -> structured
  candidate, or a parse failure) and a validator producing a verdict plus a list
  of validation errors. Rules, split explicitly into hard and soft:
  - **hard (`rejected`):** unparseable output; schema-`v1` violation; an event
    with no supporting document reference; an `occurred_at` outside a configured
    plausibility window relative to the document's `published_at`; a field that
    merges facts and claims; forbidden vocabulary (`sentiment_score`,
    "prediction", "signal", "forecast" per `DOMAIN_MODEL.md` section 7) in
    generated text; market-pricing language while there is no market data feed
    (`ARCHITECTURE_FOUNDATIONS.md` section 6); any value that would violate an
    `Event` domain invariant (empty `type`/`title`, empty `source_ids`,
    confidence outside 0..1);
  - **soft (`proposed`):** schema-valid output whose confidence is below the
    configured auto-accept threshold.
  - Anything passing every rule is `accepted`.
  - Thresholds are configuration, not constants in the rule bodies.
- **Acceptance:**
  - each hard rule has at least one test that fails only that rule and asserts
    both the `rejected` verdict and a specific, human-readable validation error;
  - a below-threshold confidence yields `proposed` with the Event *not*
    constructed;
  - the market-language check is deterministic and post-generation, and the
    allowed phrasings from `ARCHITECTURE_FOUNDATIONS.md` section 6 pass while the
    forbidden ones fail;
  - the module imports no SQLAlchemy, no httpx, and no Anthropic SDK (asserted);
  - validation errors are structured well enough to be stored verbatim in
    `LLMRun.validation_errors`;
  - the validator never mutates or "repairs" model output - it only judges it.
- **Out of scope:** persistence, LLM calls, the three-condition narrative
  assignment rule (Phase 4), any auto-accept rule for a Tier B decision.
- **Depends on:** T006 (needs output schema `v1`).
- **Refs:** ADR-0002, ADR-0008; `ARCHITECTURE_FOUNDATIONS.md` sections 5 and 6;
  `DOMAIN_MODEL.md` sections 3 and 7; `S002_WAVE0_DECISIONS.md` D-S002-04
  clauses 2, 11, 12.
- **Validation:** unit tests only, one per rule, plus a table-driven pass case.

#### S002-T008 - Extraction service: Event and `LLMRun` in one transaction

- **Category:** Feature.
- **Goal:** for one Document, produce a verdict and persist its consequences
  atomically - the `LLMRun` always, the Event only when `accepted`.
- **Scope:** a service that takes a Document, renders the versioned prompt, calls
  the injected `LLMClient`, parses and validates the response, and writes inside
  **one** unit of work: an `LLMRun` carrying every ADR-0007 field (including
  `input_reference_ids` resolving to the source Document id, the pinned model id,
  prompt/system-prompt/schema versions, `token_usage`, `latency`, the verdict as
  `validation_status`, and `validation_errors`), plus - only on `accepted` - one
  or more Event rows whose `source_ids` reference that Document. The clock is
  injected. Driven entirely by `FakeLLMClient` in this task.
- **Acceptance:**
  - `accepted` yields Event row(s) and exactly one `LLMRun`, both visible after
    one commit;
  - `proposed` and `rejected` yield an `LLMRun` and **zero** Event rows;
  - a failure injected between the two writes leaves neither (failure-injection
    integration test, not code inspection);
  - `input_reference_ids` on the stored run resolves to a real `documents.id`,
    and `input_hash` is also present (ADR-0007 requires both);
  - the stored `model` passes the `ck_llm_runs_no_latest_alias` constraint;
  - `raw_output` is stored verbatim, including for rejected runs;
  - a zero-event but well-formed response (a document containing no economic
    development) is a normal `accepted` outcome with no Event rows - not a
    rejection;
  - no `datetime.now()` appears in the service.
- **Out of scope:** the cycle wiring (T009), the budget guard (T010), any real
  API call, narrative assignment.
- **Depends on:** T002 (unit of work), T006 (client + prompts), T007 (validator).
- **Refs:** ADR-0002, ADR-0007, ADR-0008; `S002_WAVE0_DECISIONS.md` D-S002-04
  clauses 1, 2, 6; root `CLAUDE.md` ("Every material LLM call writes an
  `LLMRun` ... in the same unit of work as the decision it produced").
- **Validation:** integration tests against the live database for each verdict,
  plus the failure-injection atomicity test; unit tests for prompt rendering and
  run-field assembly.

#### S002-T009 - The extract stage inside the cycle

- **Category:** Feature.
- **Goal:** the cycle's second stage stops being a passthrough - it finds
  unprocessed Documents, extracts them, and costs nothing when there is nothing
  to do.
- **Scope:** `cycle/extract.py`, wired in place of the `extract` passthrough in
  `build_production_stages`, mirroring `cycle/ingest.py`'s shape. A work queue
  selecting Documents at `processing_status = COLLECTED`, ordered oldest first,
  bounded by a configured per-cycle document cap. Per-document failure
  isolation: a transport failure (timeout, 5xx, rate limit) leaves the Document
  at `COLLECTED` and is recorded on the `CycleRun`; a terminal verdict
  (`accepted` / `proposed` / `rejected`) advances the Document to
  `EVENTS_EXTRACTED` and is never retried automatically. A new
  `DocumentRepository` method listing documents by processing status with a
  limit. `ProcessingStatus.EVENTS_EXTRACTED`'s docstring is corrected to mean
  *"extraction attempted and a terminal verdict reached"* (D-S002-04 clause 3).
- **Acceptance:**
  - a cycle with unprocessed Documents produces Events and `LLMRun` rows and
    advances exactly the Documents it processed;
  - **a cycle with an empty work queue calls the client zero times** (asserted
    against the fake client's call counter) - the sprint's central cost
    invariant;
  - re-running a cycle immediately extracts nothing and makes no further calls;
  - the per-cycle cap is respected: with more unprocessed Documents than the cap,
    exactly the cap is processed and the rest remain for the next cycle;
  - an extraction that raises does not fail the stage or the cycle; the failure
    appears on the `CycleRun` and that Document stays `COLLECTED`;
  - a stage-level failure still yields exactly one terminal `CycleRun`;
  - `processing_status` never regresses.
- **Out of scope:** the budget guard (T010), the remaining four passthrough
  stages, any parallelism or concurrency across documents.
- **Depends on:** T008.
- **Refs:** ADR-0004, ADR-0015 clause 2; `cycle/ingest.py` as the isolation
  pattern; `S002_WAVE0_DECISIONS.md` D-S002-04 clauses 3, 4, 5, 9.
- **Validation:** integration tests for the populated queue, the empty queue
  (zero calls), the cap, and per-document isolation; unit tests with an injected
  clock.

#### S002-T010 - Monthly budget guard

- **Category:** Feature.
- **Goal:** the $10/month ceiling is enforced by code, not by hope, and running
  out of budget degrades the product without failing the cycle or corrupting
  data.
- **Scope:** a deterministic guard that computes spend for the current budget
  period from `llm_runs.token_usage` against the `llm/models.py` rate table,
  compares it to a configured monthly ceiling and soft threshold (defaults: $10
  and 80%), and is consulted by the extract stage **before** each call. At or
  above the ceiling the stage issues no further calls for the period and records
  that on the `CycleRun`; below the soft threshold nothing changes; between them
  the approach is recorded. Cost computation is a pure function over token counts
  and rates, unit-testable with no database.
- **Acceptance:**
  - cost for a known token count and rate matches a hand-computed figure to the
    cent;
  - with recorded runs pushing simulated spend over the ceiling, the next cycle
    makes zero LLM calls, the cycle still `SUCCEEDED`, and the reason is visible
    on the `CycleRun`;
  - Documents are not advanced when they were skipped for budget reasons - they
    stay `COLLECTED` and resume when the period rolls over;
  - the soft threshold changes no behaviour but is recorded;
  - the ceiling, the soft threshold, and the per-cycle cap are configuration, not
    constants;
  - a test computes projected monthly cost at the current document rate and
    asserts it is under the ceiling for the configured model.
- **Out of scope:** any dashboard or alert surface (Phase 10); per-task-type cost
  breakdown reporting; rate-table versioning by effective date.
- **Depends on:** T009.
- **Refs:** ADR-0015 clauses 3, 4, 7; ADR-0016 clause 5;
  `ARCHITECTURE_FOUNDATIONS.md` section 9.
- **Validation:** unit tests for the cost function and the threshold logic;
  integration tests for the stop-at-ceiling behaviour inside a real cycle.

#### S002-T011 - Live Anthropic smoke run

- **Category:** Feature / Research.
- **Goal:** prove the whole slice against the real provider, once, on real
  documents, and replace estimated cost figures with measured ones.
- **Scope:** run the cycle with `AnthropicClient` against a small, explicitly
  bounded number of real collected Documents (suggest 5-10, well under $0.10).
  Record in the PR: the pinned model id actually used, token usage per document,
  measured latency, the verdict distribution, and the measured cost per document
  against the ADR-0015 estimate of ~$0.005. Add a live test marked `network` and
  excluded from CI, in the same style as the existing live RSS test. Fix any
  provider-shaped mismatch this reveals (response envelope, structured-output
  mechanics, token-usage field names).
- **Acceptance:**
  - at least one real Event exists in the database, traceable to a real
    `LLMRun` with a real `raw_output` and a pinned dated model id;
  - "why was this Event created?" is answered end to end from stored data alone,
    demonstrated in the PR by an actual query and its output;
  - measured cost per document is recorded and compared against the ADR-0015
    estimate; a material divergence is raised as a problem, not absorbed
    silently;
  - `cache_creation_input_tokens` and `cache_read_input_tokens` are present in
    the recorded `token_usage` (expected zero - the caching decision stays
    evidence-backed);
  - the live test is excluded from CI and CI stays green without any secret;
  - the API key exists only in the local `.env` and in nothing that is committed.
- **Out of scope:** tuning prompt quality against the results (record findings;
  a prompt-quality pass is its own future task), any bulk backfill.
- **Depends on:** T009 (T010 preferably merged first, so the guard is live for
  the first real spend). **Requires the Anthropic API key**, which the human
  obtains during the sprint - this is the only task blocked on it, and it is
  scheduled last for exactly that reason.
- **Refs:** ADR-0007, ADR-0010, ADR-0015, ADR-0016; `S002_WAVE0_DECISIONS.md`
  D-S002-04 clause 13, D-S002-05.
- **Validation:** the live run itself, with its query output pasted into the PR;
  the marked live test.

#### S002-T012 - Documentation sync and sprint close-out

- **Category:** Documentation.
- **Goal:** the documented system matches the delivered one, and the registries
  reflect what this sprint actually resolved.
- **Scope:** `docs/reference/ARCHITECTURE_OVERVIEW.md` and `MODULE_MAP.md` gain
  the `llm/` and `extraction/` modules, the new dependency directions, and the
  transaction boundary; `WORKFLOWS.md` gains the API key setup step, how to run
  one extraction cycle, and the `.env` note from T003; root `CLAUDE.md` gains any
  convention this sprint actually established (prompt-version bump rule, the
  unit-of-work rule) and drops anything it contradicts; `CURRENT_STATUS.md` moves
  to Sprint 002 closed; `PROBLEM_REGISTRY.md` reflects PRB-001/002/004 outcomes;
  `TECHNICAL_DEBT.md` records anything knowingly deferred; `ROADMAP.md` Phase 3
  completion criteria are ticked against evidence, not intent.
- **Acceptance:**
  - every command added to `WORKFLOWS.md` was actually executed;
  - the module map matches the real package layout;
  - Phase 3's four completion criteria in `ROADMAP.md` are each either checked
    with the evidence that satisfies them, or explicitly left open with a reason;
  - no document still describes `extract` as a passthrough stage.
- **Out of scope:** the sprint Review section itself is written at close by
  `tech-writer` (per-task doc sync still happens inside each task's own PR - the
  Sprint 001 lesson).
- **Depends on:** T011.
- **Refs:** `product-architecture` skill; `PROJECT_MANAGEMENT.md` section 6;
  root `CLAUDE.md` per-task delivery loop.
- **Validation:** a clean-clone walkthrough of the updated `WORKFLOWS.md`,
  described in the PR.

## 6. Suggested PR Waves

PR boundaries are the engineer's call; this is the expected dependency shape.

1. **Wave 0 - approval:** T001 (includes accepting ADR-0015 and ADR-0016).
2. **Wave 1 - clear the ground, in parallel:** T002 (the big one) alongside T003,
   T004, T005, and T006. T002 and T006 are the two on the critical path.
3. **Wave 2 - judgement without infrastructure:** T007.
4. **Wave 3 - it writes:** T008, then T009.
5. **Wave 4 - it stays affordable:** T010.
6. **Wave 5 - it is real:** T011 (needs the API key), then T012.

The API key gates only Wave 5. If it arrives early, nothing changes; if it
arrives late, everything up to and including T010 is already done against the
fake client.

## 7. Acceptance Criteria

1. Events are extracted automatically inside the 5-minute cycle, from Documents
   collected by the existing ingest stage.
2. Every Event traces to at least one Document and to the `LLMRun` that produced
   it, and both were written in one transaction.
3. Malformed, schema-invalid, or rule-violating model output produces a
   `rejected` `LLMRun` and never a corrupt or partial Event.
4. "Why was this Event created?" is answerable from stored data alone -
   demonstrated with a real query against a real run (T011).
5. A cycle with no unprocessed Documents makes zero LLM calls and costs $0.
6. Projected monthly spend at the observed document rate is under the $10 ceiling
   (ADR-0015), and the hard ceiling demonstrably stops calls without failing the
   cycle.
7. A clean cycle over the seeded registry records no expected source failures
   (PRB-002), and the unit suite is immune to the ambient environment (PRB-001).
8. Nothing in this sprint writes a Narrative, a `NarrativeEvent`, an
   EvidencePack, an impact assessment, or an Alert.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Haiku 4.5 extracts materially worse than Sonnet would (ADR-0016's accepted risk) | The validator is the gate, not the model; rejection rate is recorded from the first call, and escalation is a configuration change. T011 is the first real evidence - treat a high rejection rate as a finding, not a nuisance |
| A too-strict validator silently suppresses good extractions (ADR-0002's own warning) | Every rejection is stored with structured errors; T011 reports the verdict distribution explicitly. If nearly everything is rejected, that is a T011 outcome, not a T007 success |
| The unit-of-work refactor (T002) destabilises the whole existing suite | It lands first, in its own PR, with the full existing suite as the regression net; the `ON CONFLICT` idempotent paths are re-verified explicitly because they were previously exercised with a commit per call |
| The API key never arrives, blocking the sprint | Only T011 needs it. Everything else runs against the fixture-driven fake, by design |
| Cost runs above the model in ADR-0015 (longer articles, more retries) | The budget guard is a task, not a hope; the per-cycle cap bounds a single cycle's spend; a divergence found in T011 is raised as a problem |
| Extraction schema `v1` foreclosing Phase 4's matching options (PRB-003) | D-S002-04 clause 11 is a binding constraint on T006, with an explicit acceptance criterion that the forbidden fields are absent |
| The `EVENTS_EXTRACTED` semantic change quietly misleads later phases | The docstring change is an explicit acceptance criterion in T009 and is repeated in the T012 docs sync |
| Deactivating five of six seeded sources makes the corpus narrow | Accepted deliberately: volume fits the cost model and source breadth is Phase 2's job. Recorded here so it is a decision, not a drift |
| The sprint drifts into Phase 4 because narratives feel like the natural next step | Acceptance criterion 8 is a hard line: this sprint writes no Narrative and no assignment |

## 9. Review

To be completed by `tech-writer` at sprint close. Records what actually
happened; never rewrites the plan.
