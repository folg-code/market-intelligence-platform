# Sprint 002 - Wave 0 Decisions

Binding decisions for **Sprint 002 - The first LLM slice: Document to Event,
validated and audited**.

Date: 2026-08-19
Basis: `docs/vision/PRODUCT_VISION.md`, `docs/vision/ARCHITECTURE_FOUNDATIONS.md`
(sections 5, 6, 7, 9), `docs/vision/DOMAIN_MODEL.md` (sections 3, 5, 7),
ADR-0002, ADR-0004, ADR-0007, ADR-0008, ADR-0010, and the two ADRs proposed with
this sprint (ADR-0015 cost ceiling, ADR-0016 Haiku as the default extraction
model), `docs/planning/ROADMAP.md` Phase 3,
`docs/planning/sprints/SPRINT_001.md` section 9,
`docs/planning/PROBLEM_REGISTRY.md`, `docs/planning/TECHNICAL_DEBT.md`.

## D-S002-01 - Problem Statement

Sprint 001 built the entire schema for LLM-assisted work and deliberately left
every row of it empty: `llm_runs`, `events`, and `evidence_packs` exist, with
append-only and immutability triggers, and nothing has ever written to them.
Ingestion produces real Documents on a 5-minute cadence, and every one of them
sits at `processing_status = COLLECTED` forever. The system currently collects
and stores; it does not yet understand anything.

Sprint 002 closes that gap for exactly one step of the pipeline: **Document to
Event**. It is the first slice where a model is in the loop, so it is also the
sprint that establishes - once, for every later phase - how a model call is
made, versioned, validated, priced, and recorded.

The choice to do Phase 3 and *not* finish Phase 2's remaining adapters is
deliberate and was made by the human owner: the remaining adapters are
repeatable work against a pattern that already exists (`SourceAdapter` +
`ingest.py`), whereas the candidate/validation layer (ADR-0002) and the audit
trail (ADR-0007) are the real unknowns. More documents without extraction is
just more unprocessed rows.

## D-S002-02 - Path / Scope Inventory

| ID | Path / Area | Key Modules | Entrypoints | Priority |
|---|---|---|---|---|
| P1 | `src/moj_projekt/persistence/` (all 13 repositories) | unit-of-work boundary; repositories stop committing | called by cycle stages | HIGH |
| P2 | `src/moj_projekt/llm/` (**new module**) | client port, Anthropic client, fake client, model/rate config, prompt + schema artifacts | called by the extraction service | HIGH |
| P3 | `src/moj_projekt/llm/prompts/` (**new**) | versioned prompt artifacts, versioned output schemas | loaded by the client port | HIGH |
| P4 | `src/moj_projekt/extraction/` (**new module**) | candidate parsing, deterministic validator, extraction service | called by the cycle extract stage | HIGH |
| P5 | `src/moj_projekt/cycle/extract.py` (**new**) | extract stage: work queue, per-document isolation, budget guard | cycle | HIGH |
| P6 | `src/moj_projekt/domain/` | `ProcessingStatus` semantics, repository interfaces, budget value objects | imported only | HIGH |
| P7 | `src/moj_projekt/persistence/seed_data/sources.py` | seed honesty (PRB-002) | seed command | MEDIUM |
| P8 | `migrations/` | one migration at most (terminal-`CycleRun` guard); extraction needs **no** new table | migrate command | MEDIUM |
| P9 | `tests/`, `docs/reference/`, `docs/planning/` | fixtures, conftest isolation, reference docs, status | CI, humans | MEDIUM |

## D-S002-03 - Success Metrics

1. A cycle over collected Documents produces Event rows, and every Event row is
   reachable from its `LLMRun` and from at least one Document.
2. A cycle in which no Document is unprocessed makes **zero** LLM API calls and
   costs exactly $0 (asserted by a test against a call-counting fake client).
3. Malformed, schema-invalid, or rule-violating model output produces a
   `rejected` `LLMRun` and **no** Event row - never a partial or corrupt Event.
4. "Why was this Event created?" is answerable from stored data alone: input
   document references, prompt version, system prompt version, output schema
   version, pinned model id, raw output, parsed output, validator verdict, and
   validator errors.
5. Event and `LLMRun` are written in **one** database transaction: killing the
   process between them is not a reachable state.
6. Re-running a cycle immediately re-extracts nothing and spends nothing.
7. A clean cycle over the seeded registry records **no expected source
   failures** (PRB-002 closed).
8. Projected monthly cost, computed from recorded `token_usage` against the
   configured rate table, is under the $10 ceiling at the observed document
   rate; the hard ceiling is demonstrated to stop LLM calls without failing the
   cycle.

## D-S002-04 - Binding Design Decisions

These are decided here so no task re-opens them mid-sprint.

**1. The `LLMRun` record *is* the candidate store. No new table.**
ADR-0002 requires rejected candidates to be persisted (they are the evaluation
dataset). `llm_runs` already carries `raw_output`, `parsed_output`,
`validation_status`, and `validation_errors`. A separate `event_candidates`
table would duplicate all four. Consequence: extraction adds **no** entity and
**no** migration.

**2. `accepted` / `proposed` / `rejected` for extraction mean exactly this:**

| Verdict | Event row | `LLMRun` | When |
|---|---|---|---|
| `accepted` | written | written, same transaction | output parses against schema `v1` and passes every deterministic rule |
| `proposed` | **not** written | written | output is schema-valid but fails a *soft* rule (below the auto-accept confidence threshold) - it waits for the Phase 7 review surface |
| `rejected` | **not** written | written | output is unparseable, schema-invalid, or violates a *hard* rule |

Extraction is Tier A (`ARCHITECTURE_FOUNDATIONS.md` section 5), so `proposed` is
rare by design; it exists so a low-confidence extraction is preserved rather
than discarded. No Event is ever written for a non-`accepted` verdict.

**3. A terminal verdict is terminal for that Document at that prompt version.**
A Document whose extraction returns `rejected`, `proposed`, or a legitimate
"zero events here" advances to `EVENTS_EXTRACTED` anyway and is never retried
automatically. This is a cost decision as much as a correctness one: automatic
retry of a poison document is an unbounded money leak. Re-extraction after a
prompt or model version bump is a deliberate offline replay (ADR-0015 clause 5),
not a cycle behaviour.

Consequence, to be implemented explicitly: `ProcessingStatus.EVENTS_EXTRACTED`
means *"extraction has been attempted and reached a terminal verdict"*, not
"at least one Event exists". Its docstring must be corrected in the task that
first relies on this.

**4. Transport failures are not terminal verdicts.** An API timeout, 5xx, or
rate-limit response leaves the Document at `COLLECTED` for the next cycle and is
recorded on the `CycleRun`, mirroring per-source ingest isolation. Retry
pressure is bounded by the per-cycle document cap and the budget guard, not by a
retry counter (no new column).

**5. A failing extraction must not fail the cycle**, per source and per
document, exactly as ingestion already behaves.

**6. Repositories stop committing; the caller owns the transaction.** Writing an
Event and its `LLMRun` atomically is impossible while every repository calls
`session.commit()` internally (reviewer's S001-T009 observation). Repositories
`flush()`/`refresh()`; a unit-of-work boundary owned by the cycle stage commits
once. This lands **before** anything writes an Event.

**7. Prompts and output schemas are versioned artifacts in the repository**, not
strings in Python code, and the version travels onto every `LLMRun`
(`prompt_version`, `system_prompt_version`, `output_schema_version`). A prompt
edit without a version bump is a review-blocking defect.

**8. The model is `claude-haiku-4-5-20251001`** - the pinned dated identifier.
The undated `claude-haiku-4-5` alias is forbidden (ADR-0010, ADR-0016, and the
`ck_llm_runs_no_latest_alias` CHECK). Model id, model version, and per-token
rates live in one declarative configuration table.

**9. Cost scales with new documents, never with cycles** (ADR-0015). A cycle
with an empty work queue issues no HTTP request at all. This is asserted by a
test, not by inspection.

**10. No batch API and no prompt caching in this sprint** (ADR-0015 clauses 5
and 6). `cache_creation_input_tokens` and `cache_read_input_tokens` are recorded
in `token_usage` anyway, so the caching decision can later be revisited on data.

**11. The extraction output schema must not foreclose Phase 4 matching
(PRB-003).** The three-condition assignment rule needs, per extracted event:
the candidate economic mechanism, the affected entities/exposures, and the
candidate interpretation. Schema `v1` must carry that material as *extracted
candidate material* inside `extracted_facts` / `source_claims` / `parsed_output`
JSONB - and must **not** decide narrative membership, instrument relevance, or
direction, all of which are later phases and higher decision tiers. Facts and
claims stay in two separate fields; nothing merges them (ADR-0008).

**12. Forbidden vocabulary and market-pricing language are checked
deterministically after generation** (`ARCHITECTURE_FOUNDATIONS.md` section 6;
`DOMAIN_MODEL.md` section 7), inside the validator - not in the prompt. A
violation is a hard rule and yields `rejected`.

**13. The API key is a secret and is never committed.** It is read through the
existing typed settings object, with a placeholder in `.env.example` only. Work
proceeds against a fixture-driven fake client; only the live smoke task needs a
real key, and it is the last task in the sprint.

**14. PRB-002 is closed by honesty, not by new adapters.** Sources with no
adapter or no live feed are seeded `active=False` with the reason recorded in
the seed data. Building the Fed/FOMC, BLS, and SEC adapters remains Phase 2 work
and is out of scope; the human deferred it deliberately.

## D-S002-05 - Correctness / Quality Gate

Everything from `S001_WAVE0_DECISIONS.md` D-S001-04 still applies (test split,
injected clock, strict mypy, migrations-only, repository boundary, Definition of
Done). Added for this sprint:

- **No live network or live LLM call in the default test run.** Unit tests use a
  fake client over recorded fixtures; the live smoke test is marked `network`
  and excluded from CI, exactly as the live RSS test already is.
- **The domain boundary test now also matters for the Anthropic SDK.**
  `domain/` must not import it (already asserted); `extraction/`'s validator
  must be unit-testable with no SDK, no HTTP, and no database.
- **Every `LLMRun` written in a test must satisfy the ADR-0007 field set** - a
  test asserting field presence is not enough; assert that
  `input_reference_ids` actually resolves to stored Document ids.
- **Atomicity is tested by failure injection**, not by reading the code: force
  the `LLMRun` write to fail and assert no orphan Event row exists, and vice
  versa.
- **Zero-call assertion:** a cycle with an empty work queue asserts the fake
  client's call count is 0.

## D-S002-06 - Branch and PR Rules

Defaults from the `git-workflow` skill:

```text
Integration branch: sprint/first-llm-slice
Working branches:   <prefix>/<descriptive-slug>  (feat/ fix/ docs/ test/ refactor/)
PR base:            sprint/first-llm-slice  (never main)
Merge method:       squash merge, by a human
```

- One PR = one coherent outcome; 1-3 logical commits per PR
  (`commit-convention` format: `<type>(<scope>): <subject>`).
- Branch and commit names describe the change, never the task ID; the task ID
  belongs in the PR description only.
- The engineer opens the PR and stops before merge; never merges its own PR,
  never merges into `main`.
- Wait for a dependency PR to be merged before starting the dependent one.

**Process change carried from the Sprint 001 retro.** Sprint 001 produced zero
PR review comments across PRs #1-#14 because every review happened in
conversation, and squash merges erased the in-PR defect corrections - for the
T006 `id`-trigger fix, the code is the only surviving evidence. Binding for this
sprint:

- `tester` and `reviewer` post their verdict as a **PR review on GitHub**
  (Approve / Request Changes with findings), not only in conversation. The
  conversation may summarise it; the PR is the record.
- The PR description lists **corrections made inside the PR** after the first
  review pass, in one short "Fixed during review" list. Squash merge is kept -
  the fix is to record findings durably, not to pollute `main`'s history with
  fixup commits.

## D-S002-07 - Out of Scope

- **The remaining Phase 2 source adapters** (Fed/FOMC, BLS, SEC EDGAR, further
  newswires). Deliberately deferred by the human; PRB-002 is closed by
  deactivating adapter-less sources, not by building adapters.
- **Narrative anything**: candidate matching, `canonical_key` assignment,
  `NarrativeEvent` writes, the three-condition rule (PRB-003 stays open - Phase
  4), narrative dynamics.
- EvidencePack generation, instrument impact, alerts, overrides, audit entries
  from human actions.
- Any dashboard page, template, or HTMX interaction; the review surface for
  `proposed` candidates is Phase 7.
- Embedding computation and the embedding-model-source decision (TD-003 stays
  open; it is Phase 4's blocker, not this sprint's).
- Batch API usage; prompt caching; multi-model routing per document.
- Retention policy for `raw_output` (Phase 10) - though `llm_runs` starts
  growing this sprint, which raises its priority.
- Cost dashboards, per-stage timing, operator observability (Phase 10). The
  budget guard in this sprint is enforcement, not observability.
- Deployment, backup/restore.

## D-S002-08 - Follow-on Ownership

| Area | Owner / Future Sprint |
|---|---|
| Fed/FOMC, BLS, SEC adapters; reactivating deactivated seed sources | a later sprint completing Roadmap Phase 2 |
| Three-condition assignment rule enforcement (PRB-003) | Roadmap Phase 4 |
| Embedding model source decision + ADR (TD-003) | human decision, then architect - before Phase 4 |
| Review surface for `proposed` candidates | Roadmap Phase 7 |
| `raw_output` retention policy | human decision, then Phase 10 |
| Cost/rejection-rate observability; batch replay after a prompt bump | Roadmap Phase 10 |
| Escalating a task from Haiku to Sonnet | architect, on recorded rejection-rate evidence (ADR-0016) |

## Wave 0 Checklist

These checkboxes are checked ONLY by a human, as the act of approval - the
agent proposes them unchecked and never checks them itself. Only a full set of
checked items = a green light for `engineer` (`governance`).

- [x] Approve **ADR-0015** (monthly LLM cost ceiling $10 MVP / $50 product;
      spend scales with documents not cycles; no batch on the live path; no
      prompt caching in MVP) - set its status to `Accepted`.
- [x] Approve **ADR-0016** (Haiku 4.5 `claude-haiku-4-5-20251001` as the default
      extraction model, amending ADR-0010's tier mapping; Sonnet becomes an
      evidence-driven escalation) - set its status to `Accepted`, and accept the
      extraction-quality risk it records.
- [x] Confirm the sprint branch (`sprint/first-llm-slice`).
- [x] Confirm the scope inventory (D-S002-02), including the two new modules
      `llm/` and `extraction/`.
- [x] Confirm the binding design decisions (D-S002-04), in particular: no
      candidate table, a terminal verdict is never auto-retried, and
      `EVENTS_EXTRACTED` changes meaning.
- [x] Confirm the correctness/quality gate (D-S002-05).
- [x] Confirm the review-record process change (D-S002-06) - reviews posted on
      the PR, squash merge kept.
- [x] Confirm the out-of-scope list (D-S002-07), in particular that the
      remaining Phase 2 adapters stay deferred.
- [x] Confirm follow-on ownership (D-S002-08).
- [x] Set `SPRINT_002.md` to `Status: Approved`.

Approved by: folga33 (user, in-conversation approval)
Approved date: 2026-08-19
