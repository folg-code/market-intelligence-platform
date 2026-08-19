# Current Status

## 1. Purpose

A short snapshot of where the project stands. Not an operational task board -
task status lives in the sprint table (and in an Issues tracker once one exists).

## 2. Status Metadata

```text
Status Date:             2026-08-19
Current Phase:           Sprint 001 closeout (Roadmap Phases 0-2)
Current Milestone:       MVP (Roadmap Phases 0-10)
Implementation Status:   Full Sprint 001 delivered: toolchain through
                         WORKFLOWS.md (S001-T002..T014). No LLM code yet.
Overall Status:          Approved - all Sprint 001 tasks done; sprint closeout
Active Sprint:           001 - Foundation to first real document (Status: Approved)
Last Completed Sprint:   none
Next Planned Capability: After Sprint 001: remaining Phase 2 source adapters
                         and Phase 3, the first LLM slice
```

## 3. Current Objective

Get from "everything is decided on paper" to "real documents from a live source
are in PostgreSQL", so Phase 3 (the first LLM slice) starts against real data.

## 4. Completed Capabilities

- Discovery: `docs/vision/PRODUCT_VISION.md`.
- Architecture: `ARCHITECTURE_FOUNDATIONS.md`, `DOMAIN_MODEL.md`,
  ADR-0001..ADR-0014 (all four previously blocking stack questions resolved,
  plus the pgvector amendment to ADR-0005).
- Planning: `ROADMAP.md` (Phases 0-10), `PROJECT_MANAGEMENT.md`, `SPRINT_001.md`,
  `S001_WAVE0_DECISIONS.md`.
- Reference: `ARCHITECTURE_OVERVIEW.md`, `MODULE_MAP.md`, root `CLAUDE.md`.
- Repository under git.
- S001-T002: toolchain and dependency baseline; `scripts/check.py` runs
  lint + strict mypy + tests as one command.
- S001-T003: Docker Compose stack (`app` + `db` on `pgvector/pgvector:pg16`),
  `.env.example`, typed settings (`config/settings.py`), `GET /health`
  reporting database connectivity and pgvector availability.
- S001-T004: Alembic migration baseline; the `vector` extension is enabled
  by migration `0001`, not app startup.
- S001-T005: pure domain value objects/enums (`domain/enums.py`,
  `evidence.py`, `embedding.py`), with an enforced no-infrastructure-import
  boundary test and a forbidden-vocabulary test.
- S001-T006: Source + Document persistence (`domain/document.py`,
  `source.py`, `repositories.py`; `persistence/models.py` and repositories;
  migration `0002`), with a DB-level immutability trigger on Document and
  dedupe via a unique constraint + `ON CONFLICT DO NOTHING`.
- S001-T007: Event + EvidencePack persistence (`domain/event.py`,
  `evidence_pack.py`; `persistence/models.py`, `event_repository.py`,
  `evidence_pack_repository.py`; migration `0003`). `extracted_facts` and
  `source_claims` are kept as two distinct fields, never merged (ADR-0008);
  `source_ids` must be non-empty (DB CHECK); EvidencePack is versioned by
  `(narrative_id, evidence_version)` (unique constraint), enforces
  `independent_source_count <= source_count` (domain + DB CHECK), and rejects
  every update via a DB trigger (stricter than Document's, which still allows
  `processing_status` to advance). `market_evidence` must be empty in MVP -
  enforced only in the domain layer (ADR-0003). `evidence_packs.narrative_id`
  has no foreign key yet - the `narratives` table lands in T008, which adds
  the FK (tracked in `SPRINT_001.md` S001-T008 scope).
- S001-T008: Narrative, NarrativeEpisode, NarrativeEvent, NarrativeRelation
  persistence (`domain/narrative.py`, `narrative_episode.py`,
  `narrative_event.py`, `narrative_relation.py`; `persistence/models.py` and
  the four matching repositories; migration `0004`). `canonical_key` is
  unique; a Narrative without `economic_mechanism` or `market_interpretation`
  is rejected; `identity_embedding` may be NULL (embedding is derived, never
  identity - ADR-0001/ADR-0014), and a CHECK constraint keeps
  `identity_embedding`/`embedding_model`/`embedding_version` all-null or
  all-set together. **The `identity_embedding` column is `vector(384)`, and
  384 is an explicitly documented placeholder dimension, not a finalized
  choice** - it is tied to the still-open embedding-model-source decision
  (see "Open Decisions" below); changing the model later means a migration
  plus a re-embedding pass, not data loss. `narrative_episodes` uses a
  Postgres `EXCLUDE USING gist` constraint (via `btree_gist`) so episodes of
  one Narrative cannot overlap in time - NarrativeEpisode itself stays
  optional/manual-only in MVP, with no automated lifecycle. `narrative_events`
  has a composite primary key on `(narrative_id, event_id)`; the
  three-condition assignment rule from `DOMAIN_MODEL.md` section 5 is not yet
  enforced in code or the database - that is future matching-logic work, out
  of T008's persistence-only scope. `narrative_relations` rejects
  self-relations (CHECK) and duplicate `(source, target, type)` triples
  (unique constraint). This task also adds the
  `evidence_packs.narrative_id -> narratives.id` foreign key that S001-T007
  had deferred, resolving that carried-forward note.
- S001-T009: NarrativeInstrumentImpact, Alert, LLMRun, AuditEntry persistence
  (`domain/instrument_impact.py`, `alert.py`, `llm_run.py`, `audit_entry.py`,
  `AlertType` in `enums.py`; `persistence/models.py` and four matching
  repositories; migration `0005`). One current impact assessment per
  `(narrative, instrument)` via `upsert()` backed by
  `INSERT ... ON CONFLICT DO UPDATE` against a unique constraint - a
  documented judgment call, since `DOMAIN_MODEL.md` gives this entity no
  versioning language the way it does for `EvidencePack`. A DB-level CHECK
  mirrors the domain rule that a non-neutral `direction` requires a
  rationale and non-empty `evidence_refs` (ADR-0006). `LLMRun` and
  `AuditEntry` are append-only, enforced by a DB trigger rejecting both
  UPDATE and DELETE (stricter than `EvidencePack`'s update-only trigger, per
  ADR-0007/ADR-0009). `LLMRun` rejects `model`/`model_version == "latest"` at
  both construction and via a DB-level CHECK (ADR-0010). `Alert.add()` is
  idempotent per `(narrative_id, alert_type, trigger_key)` via a unique
  constraint. Adds the `narrative_events.llm_run_id -> llm_runs.id` foreign
  key that S001-T008 had deferred until `llm_runs` existed.
- S001-T010: MVP Source registry seed (`persistence/seed_data/sources.py`,
  `persistence/seed_sources.py`). Declarative data only - a
  `SEED_SOURCES` tuple of `Source` instances, no per-source branching -
  seeded idempotently by reusing `SqlAlchemySourceRepository.add()`'s
  existing `INSERT ... ON CONFLICT DO NOTHING` from S001-T006, so no new
  idempotency logic was needed. Three Tier 1 primary/official sources
  (Fed/FOMC, BLS, SEC EDGAR) and three Tier 2 professional sources
  (Reuters, Associated Press, Bloomberg L.P.), each with a genuinely
  distinct `publisher` - the independence-grouping key from
  `DOMAIN_MODEL.md` section 3 - so no two seeded sources are treated as
  independent while actually sharing an owner.
- S001-T013: CI pipeline (`.github/workflows/ci.yml`). Two jobs on every
  push/PR into `main` and `sprint/**`: lint (ruff) + strict mypy, then
  (on success) unit + integration tests against a live
  `pgvector/pgvector:pg16` service container. Credentials are supplied to
  the test job via a written `.env` file rather than job-level `env:`
  vars - a literal `POSTGRES_PASSWORD` environment variable would make
  `test_missing_password_is_rejected` fail even though it never touches
  the database, since `Settings` reads the password from `.env` without
  it ever landing in the process environment. Verified live on the PR's
  own CI with a deliberate red/green demonstration: an unused-import
  commit failed the lint job (test job correctly skipped via `needs:`),
  and reverting it restored a green run.
- S001-T011: Processing cycle skeleton on APScheduler (`domain/clock.py`'s
  `Clock`/`SystemClock`; `domain/cycle_run.py`'s `CycleRun`/`CycleRunStatus`/
  `StageOutcome`; `cycle/stages.py`'s ordered six-stage list - ingest,
  extract, narratives, evidence, state, alerts - all no-op until S001-T012;
  `cycle/run_cycle.py` orchestrating them with per-stage failure isolation to
  one terminal `CycleRun`; `cycle/run_once.py` as a direct, scheduler-free
  entrypoint; migration `0006` adding `cycle_runs`). Overlap prevention is
  enforced twice, independently: `max_instances=1` on the APScheduler job
  wired into the FastAPI lifespan (`api/app.py`), and a partial unique index
  at the database level (ADR-0011).
- S001-T012: First source adapter (`ingestion/adapter.py` interface;
  `ingestion/rss.py` Bloomberg Markets RSS implementation; `cycle/ingest.py`
  wired into the ingest stage). Feed URL is data-driven from seed
  `endpoint_config`. Fetch failures (timeout, HTTP error, malformed feed) are
  isolated per source on `CycleRun.source_outcomes`; the cycle still
  `SUCCEEDED` and no partial Document is written. Dedupe reuses
  `DocumentRepository.add()` ON CONFLICT. Live-feed test is marked `network`
  and excluded from CI.
- S001-T014: `docs/reference/WORKFLOWS.md` (clone to a stored Document),
  README quickstart, and a refresh of `ARCHITECTURE_OVERVIEW.md`,
  `MODULE_MAP.md`, `docs/README.md`, and root `CLAUDE.md` to the delivered
  system.

## 5. Work in Progress

None. Sprint 001 tasks T001-T014 are complete; sprint closeout is next.

## 6. Blocked Work

None. The user approved, in-conversation, on 2026-08-17:
`PRODUCT_VISION.md`, `ARCHITECTURE_FOUNDATIONS.md`, `DOMAIN_MODEL.md`,
ADR-0001..ADR-0014, and `ROADMAP.md` are `Accepted`; `SPRINT_001.md` is
`Approved` with the Wave 0 Checklist in `S001_WAVE0_DECISIONS.md` checked off.
`engineer` may begin S001-T002 (T001 was the approval gate itself, now closed).

## 7. Open Critical Problems

- None recorded.

## 8. Open Decisions

| Decision | Needed by | Note |
|---|---|---|
| Embedding model source (local open-weight vs a second paid API) | Roadmap Phase 4 | ADR-0014 follow-up; a paid dependency needs explicit approval |
| Dashboard access protection when reachable beyond localhost | before any VPS deploy | ADR-0013 follow-up |
| Retention policy for document bodies and LLM `raw_output` | Phase 10 | ADR-0005/ADR-0013 follow-up |
| Monthly LLM cost ceiling | before Phase 3 spending grows | ADR-0010 follow-up |

## 9. Known Risks

- Phase 4 (narrative identity and candidate matching) remains the make-or-break
  risk; ADR-0014 reduces but does not remove it.
- Third-party source instability (format drift, rate limits) will surface as
  soon as ingestion is live.
- Sprint 001 spans three roadmap phases; the hard out-of-scope lines (one
  adapter, no LLM, no UI) are what keep it bounded.
- S001-T011 review follow-up (non-blocking): `cycle_runs.update()` has no
  DB-level guard against re-updating an already-terminal row (inert today,
  worth hardening later). The `Stage` callable signature was updated in
  S001-T012 so ingest can record per-source outcomes.
- Reuters and AP seed `feed_url` values are not live public feeds; a full
  seed cycle records those sources failed and continues. Bloomberg Markets
  is the live RSS source.

## 10. Next Planned Capability

After Sprint 001: complete Roadmap Phase 2 (remaining source adapters) and open
Phase 3, the first LLM slice - extraction, prompt versioning, the validation
layer, and `LLMRun` recording.

## 11. Sprint Progress

| Sprint | Goal | Status | Progress |
|---|---|---|---|
| 001 | Foundation to first real document | APPROVED | 14 / 14 |

## 12. Update Rules

Update when a sprint starts or ends, the phase changes, a capability completes,
a critical blocker appears, a decision changes direction, or the next planned
step changes.
