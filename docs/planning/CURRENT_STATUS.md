# Current Status

## 1. Purpose

A short snapshot of where the project stands. Not an operational task board -
task status lives in the sprint table (and in an Issues tracker once one exists).

## 2. Status Metadata

```text
Status Date:             2026-08-19
Current Phase:           Roadmap Phases 0 and 1 complete; Phase 2 partial
                         (one source adapter of the MVP set); Phase 3 planned
                         as Sprint 002
Current Milestone:       MVP (Roadmap Phases 0-10)
Implementation Status:   Sprint 001 complete. Sprint 002 Waves 1-2 plus
                         T008 landed (S002-T002..T008): unit of work,
                         env-isolated unit tests, terminal CycleRun trigger,
                         honest seed registry, llm/ client port with
                         FakeLLMClient, the deterministic extraction
                         validator, and ExtractionService persisting Event
                         + LLMRun.
Overall Status:          Sprint 002 in progress - Waves 1-2 and T008 merged
                         (PRs #16-#23). Next: S002-T009 (cycle extract stage).
Active Sprint:           002 - The first LLM slice (Status: Approved)
Last Completed Sprint:   001 - Foundation to first real document
                         (closed 2026-08-19, 14/14 tasks, PRs #1-#14)
Next Planned Capability: S002-T009 - cycle extract stage: work queue,
                         per-cycle cap, per-document isolation, status advance
```

## 3. Current Objective

Sprint 001's objective - get from "everything is decided on paper" to "real
documents from a live source are in PostgreSQL" - is met. The next objective is
Sprint 002: turn collected Documents into Events inside the cycle, with the
candidate/validation layer (ADR-0002) and the `LLMRun` audit trail (ADR-0007) in
place from the very first model call, under a binding $10/month cost ceiling.

Completing Roadmap Phase 2 (the remaining source adapters) was deliberately
deferred by the human owner in favour of Phase 3: the remaining adapters are
repeatable work against an existing pattern, while the validation and audit
machinery is the real unknown.

## 4. Completed Capabilities

- Discovery: `docs/vision/PRODUCT_VISION.md`.
- Architecture: `ARCHITECTURE_FOUNDATIONS.md`, `DOMAIN_MODEL.md`,
  ADR-0001..ADR-0014 (all four previously blocking stack questions resolved,
  plus the pgvector amendment to ADR-0005). ADR-0015 (cost ceiling) and
  ADR-0016 (Haiku as the default extraction model, amending ADR-0010's
  model-tier mapping) are `Accepted` as of 2026-08-19.
- Planning: `ROADMAP.md` (Phases 0-10), `PROJECT_MANAGEMENT.md`, `SPRINT_001.md`
  (closed, with the sprint review in section 9), `S001_WAVE0_DECISIONS.md`,
  `PROBLEM_REGISTRY.md`, `TECHNICAL_DEBT.md`, and - new - `SPRINT_002.md` plus
  `S002_WAVE0_DECISIONS.md`.
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
  enforced only in the domain layer (ADR-0003).
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
  (see "Open Decisions" below). `narrative_episodes` uses a Postgres
  `EXCLUDE USING gist` constraint so episodes of one Narrative cannot overlap
  in time. `narrative_events` has a composite primary key on
  `(narrative_id, event_id)`; the three-condition assignment rule from
  `DOMAIN_MODEL.md` section 5 is not yet enforced in code or the database
  (PRB-003, Phase 4). `narrative_relations` rejects self-relations (CHECK) and
  duplicate `(source, target, type)` triples (unique constraint). This task
  also adds the `evidence_packs.narrative_id -> narratives.id` foreign key
  that S001-T007 had deferred.
- S001-T009: NarrativeInstrumentImpact, Alert, LLMRun, AuditEntry persistence
  (`domain/instrument_impact.py`, `alert.py`, `llm_run.py`, `audit_entry.py`,
  `AlertType` in `enums.py`; `persistence/models.py` and four matching
  repositories; migration `0005`). One current impact assessment per
  `(narrative, instrument)` via `upsert()` backed by
  `INSERT ... ON CONFLICT DO UPDATE`. A DB-level CHECK mirrors the domain rule
  that a non-neutral `direction` requires a rationale and non-empty
  `evidence_refs` (ADR-0006). `LLMRun` and `AuditEntry` are append-only,
  enforced by a DB trigger rejecting both UPDATE and DELETE (ADR-0007/
  ADR-0009). `LLMRun` rejects `model`/`model_version == "latest"` at both
  construction and via a DB-level CHECK (ADR-0010). `Alert.add()` is
  idempotent per `(narrative_id, alert_type, trigger_key)`. Adds the
  `narrative_events.llm_run_id -> llm_runs.id` foreign key deferred from
  S001-T008.
- S001-T010: MVP Source registry seed (`persistence/seed_data/sources.py`,
  `persistence/seed_sources.py`). Declarative data only, seeded idempotently
  by reusing `SqlAlchemySourceRepository.add()`'s `ON CONFLICT DO NOTHING`.
  Three Tier 1 primary/official sources (Fed/FOMC, BLS, SEC EDGAR) and three
  Tier 2 professional sources (Reuters, Associated Press, Bloomberg L.P.),
  each with a distinct `publisher` - the independence-grouping key.
- S001-T013: CI pipeline (`.github/workflows/ci.yml`). Two jobs on every
  push/PR into `main` and `sprint/**`: lint (ruff) + strict mypy, then
  (on success) unit + integration tests against a live
  `pgvector/pgvector:pg16` service container. Credentials are supplied to
  the test job via a written `.env` file rather than job-level `env:` vars
  (see PRB-001). Verified live with a deliberate red/green demonstration.
- S001-T011: Processing cycle skeleton on APScheduler (`domain/clock.py`,
  `domain/cycle_run.py`, `cycle/stages.py`'s ordered six-stage list - ingest,
  extract, narratives, evidence, state, alerts; `cycle/run_cycle.py`,
  `cycle/run_once.py`; migration `0006` adding `cycle_runs`). Overlap
  prevention is enforced twice: `max_instances=1` on the APScheduler job and a
  partial unique index at the database level (ADR-0011).
- S001-T012: First source adapter (`ingestion/adapter.py` interface;
  `ingestion/rss.py` Bloomberg Markets RSS implementation; `cycle/ingest.py`
  wired into the ingest stage). Feed URL is data-driven from seed
  `endpoint_config`. Fetch failures are isolated per source on
  `CycleRun.source_outcomes`; the cycle still `SUCCEEDED`. Live-feed test is
  marked `network` and excluded from CI.
- S001-T014: `docs/reference/WORKFLOWS.md` (clone to a stored Document),
  README quickstart, and a refresh of `ARCHITECTURE_OVERVIEW.md`,
  `MODULE_MAP.md`, `docs/README.md`, and root `CLAUDE.md`.
- S002-T002: `SqlAlchemyUnitOfWork` owns the session; repositories `flush()`
  only. Cycle commits RUNNING, then one UoW per stage, then a terminal write
  that survives a rolled-back stage (PRs #20).
- S002-T003: unit suite ignores ambient `POSTGRES_*` / `.env` (`tests/conftest.py`);
  PRB-001 resolved (PR #16).
- S002-T004: migration `0007` `BEFORE UPDATE` trigger rejects writes to a
  terminal `cycle_runs` row; PRB-004 resolved (PR #19).
- S002-T005: only `bloomberg_markets` is seeded active; PRB-002 resolved
  (PR #17). Existing registries that still have those keys active need a
  manual flag flip (`ON CONFLICT DO NOTHING`).
- S002-T006: `llm/` port, FakeLLMClient, versioned prompt/schema v1, pinned
  `claude-haiku-4-5-20251001` (PR #18). Real API is T011.
- S002-T007: `extraction/` parser + deterministic validator producing
  `accepted` / `proposed` / `rejected` (ADR-0002), with no model, HTTP, or
  database (PR #21). Duplicate fact/claim *text* is not a merge (ADR-0008:
  merge = one field/list); `facts_and_claims` field remapping remains.
  `llm/` lazy-loads Anthropic so importing extraction does not load the SDK.
- S002-T008: `ExtractionService` renders the versioned prompt, calls an
  injected `LLMClient` (`FakeLLMClient` in this task), validates with T007,
  and writes inside one unit of work: `LLMRun` always (ADR-0007), Event
  rows only on `accepted` (PR #23). `proposed`/`rejected` persist the run
  and zero events. A well-formed empty `events` array is `accepted` with
  no Event rows. Failure between the two writes leaves neither. The cycle
  extract stage stays passthrough until T009.

## 5. Work in Progress

- S002-T009 (cycle extract stage: work queue, per-cycle cap, per-document
  isolation, status advance) is next; depends on T008.

## 6. Blocked Work

- **S002-T011 only** needs an Anthropic API key, which the human obtains during
  the sprint. It is the last task for exactly that reason; every other task runs
  against a fixture-driven fake client.

Historical: the user approved, in-conversation, on 2026-08-17:
`PRODUCT_VISION.md`, `ARCHITECTURE_FOUNDATIONS.md`, `DOMAIN_MODEL.md`,
ADR-0001..ADR-0014, and `ROADMAP.md` are `Accepted`; `SPRINT_001.md` is
`Approved`.

## 7. Open Critical Problems

- None. Open in `PROBLEM_REGISTRY.md`: PRB-003 only (Phase 4). PRB-001, PRB-002
  and PRB-004 are RESOLVED. `TECHNICAL_DEBT.md`: TD-001..TD-004.

## 8. Open Decisions

| Decision | Needed by | Note |
|---|---|---|
| Embedding model source (local open-weight vs a second paid API) | Roadmap Phase 4 | ADR-0014 follow-up; a paid dependency needs explicit approval; also the repayment trigger for TD-003 |
| Dashboard access protection when reachable beyond localhost | before any VPS deploy | ADR-0013 follow-up |
| Retention policy for document bodies and LLM `raw_output` | Phase 10 | ADR-0005/ADR-0013 follow-up. Becomes pressing during Sprint 002, since `llm_runs` starts filling with verbatim `raw_output` for the first time |

ADR-0015 ($10/month MVP ceiling) and ADR-0016 (Haiku 4.5 as default extraction
model) are `Accepted` as of 2026-08-19.

## 9. Known Risks

- Phase 4 (narrative identity and candidate matching) remains the make-or-break
  risk; ADR-0014 reduces but does not remove it.
- **New with Sprint 002:** extraction quality on the cheapest model tier
  (ADR-0016's explicitly accepted trade-off), and the mirror risk of an
  over-strict validator silently suppressing good extractions (ADR-0002's own
  warning). Both are watched through the recorded rejection rate.
- Third-party source instability (format drift, rate limits). Sprint 002 narrows
  live ingestion to the one source that actually works (PRB-002 fix), which
  removes the noise but also narrows the corpus.
- Registry-tracked from Sprint 001 close, with full context in
  `PROBLEM_REGISTRY.md` and `TECHNICAL_DEBT.md`: PRB-001..PRB-004 and
  TD-001..TD-004.

## 10. Next Planned Capability

Sprint 002 - Roadmap Phase 3, the first LLM slice. Collected Documents become
Events inside the 5-minute cycle: versioned prompts and output schemas, the
deterministic validation layer producing `accepted`/`proposed`/`rejected`
(ADR-0002), and an `LLMRun` written in the same transaction as the decision it
produced (ADR-0007, ADR-0010, ADR-0016) - filling the schema Sprint 001 built
and left empty, under the ADR-0015 cost ceiling.

After Sprint 002: completing Roadmap Phase 2 (the remaining MVP source adapters)
and Phase 4 (narrative candidates and identity), whose blocker is the still-open
embedding-model-source decision.

## 11. Sprint Progress

| Sprint | Goal | Status | Progress |
|---|---|---|---|
| 001 | Foundation to first real document | CLOSED (2026-08-19) | 14 / 14 |
| 002 | The first LLM slice: Document to Event, validated and audited | APPROVED (2026-08-19) | 8 / 12 |

## 12. Update Rules

Update when a sprint starts or ends, the phase changes, a capability completes,
a critical blocker appears, a decision changes direction, or the next planned
step changes.
