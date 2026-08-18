# Current Status

## 1. Purpose

A short snapshot of where the project stands. Not an operational task board -
task status lives in the sprint table (and in an Issues tracker once one exists).

## 2. Status Metadata

```text
Status Date:             2026-08-18
Current Phase:           Sprint 001 in progress (Roadmap Phases 0-2)
Current Milestone:       MVP (Roadmap Phases 0-10)
Implementation Status:   Toolchain, Docker Compose stack, typed settings,
                         /health endpoint, Alembic baseline, Source + Document
                         persistence, and Event + EvidencePack persistence
                         implemented (S001-T002..T007). No Narrative-aggregate,
                         ingestion, cycle, or LLM code yet.
Overall Status:          Approved - engineer continues with S001-T008
Active Sprint:           001 - Foundation to first real document (Status: Approved)
Last Completed Sprint:   none
Next Planned Capability: S001-T008 - Narrative, NarrativeEpisode,
                         NarrativeEvent, NarrativeRelation persistence,
                         including the identity embedding column
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

## 5. Work in Progress

- S001-T008 (Narrative aggregate persistence, incl. identity embedding
  column and the `evidence_packs.narrative_id` FK) is the next task; not
  started.

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

## 10. Next Planned Capability

After Sprint 001: complete Roadmap Phase 2 (remaining source adapters) and open
Phase 3, the first LLM slice - extraction, prompt versioning, the validation
layer, and `LLMRun` recording.

## 11. Sprint Progress

| Sprint | Goal | Status | Progress |
|---|---|---|---|
| 001 | Foundation to first real document | APPROVED | 7 / 14 |

## 12. Update Rules

Update when a sprint starts or ends, the phase changes, a capability completes,
a critical blocker appears, a decision changes direction, or the next planned
step changes.
