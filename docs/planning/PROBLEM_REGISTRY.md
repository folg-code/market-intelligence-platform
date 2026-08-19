# Problem Registry

## 1. Purpose

Observed problems, risks, inconsistencies, and unknowns. A problem may lead to
research, an ADR, a bug fix, an epic, or technical debt - it is not itself a
feature request. Knowingly-accepted shortcuts belong in
[`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md), not here.

This file was created at the close of Sprint 001 and backfilled with the
problems that sprint surfaced (see `sprints/SPRINT_001.md` section 9).

## 2. Statuses

```text
OPEN
UNDER_INVESTIGATION
DECISION_REQUIRED
PLANNED
MITIGATED
RESOLVED
DEFERRED
REJECTED
```

## 3. Severity

```text
CRITICAL
HIGH
MEDIUM
LOW
```

## 4. Problem Entry Template

```markdown
## PRB-XXX - Title

Status:
Severity:
Domain:
Owner:
Discovered:
Last Updated:

### Description
### Evidence
### Impact
### Possible Directions
### Decision or Resolution Criteria
### Related Documents
### Related ADRs
### Related Tasks
```

## 5. Active Problems

### PRB-002 - Two seeded Tier 2 sources have no live feed, so every cycle records them as failed

```text
Status:       OPEN
Severity:     MEDIUM
Domain:       Ingestion / source registry
Owner:        unassigned
Discovered:   2026-08-18 (Sprint 001, S001-T012)
Last Updated: 2026-08-19
```

#### Description

The Source registry seeds six sources, but only Bloomberg Markets has a working
public RSS feed behind it. The Reuters and Associated Press `feed_url` values in
the seed data are not live public feeds, and the Tier 1 sources (Fed/FOMC, BLS,
SEC EDGAR) have no adapter at all yet. Running a full cycle therefore always
produces per-source failures alongside the successful Bloomberg ingest.

#### Evidence

- `src/moj_projekt/persistence/seed_data/sources.py` (six seeded sources).
- `src/moj_projekt/ingestion/rss.py` - one concrete adapter.
- `CURRENT_STATUS.md` section 9 already records this as a known risk.

#### Impact

Failure isolation works as designed - the cycle still succeeds - but the
`CycleRun.source_outcomes` baseline is permanently noisy, which erodes the
signal value of "a source failed" once real drift starts happening. It also
means the seed registry currently overstates what the system can actually
ingest.

#### Possible Directions

- Build the remaining adapters (Roadmap Phase 2 completion) and correct the
  feed URLs at the same time.
- Or mark sources without an adapter as inactive in the registry until an
  adapter exists, so the cycle does not attempt them.

#### Decision or Resolution Criteria

Resolved when a clean cycle over the seeded registry produces no expected
failures - every seeded source either ingests successfully or is explicitly
inactive.

#### Related Tasks

- S001-T010 (seed), S001-T012 (first adapter). Next: Roadmap Phase 2 completion.

---

### PRB-003 - The three-condition narrative assignment rule is not enforced anywhere

```text
Status:       OPEN
Severity:     MEDIUM
Domain:       Domain / narrative identity
Owner:        unassigned
Discovered:   2026-08-18 (Sprint 001, S001-T008)
Last Updated: 2026-08-19
```

#### Description

`DOMAIN_MODEL.md` section 5 states that an Event may be assigned to an existing
Narrative only when all three conditions hold: the same economic mechanism,
similar affected instruments/exposures, and the same interpretation being
updated. `narrative_events` persists assignments (composite PK
`(narrative_id, event_id)`, confidence, rationale, LLMRun reference) but nothing
in code or in the database checks the rule itself.

This was correct for Sprint 001 - the sprint was persistence-only and the rule
is a matching-logic concern - but it is a genuine gap, not a resolved item, and
it is the core of the roadmap's highest-risk phase.

#### Evidence

- `src/moj_projekt/domain/narrative_event.py:7` and
  `tests/unit/test_domain_narrative_event.py:3` both state explicitly that the
  rule is not enforced here.
- `docs/reference/ARCHITECTURE_OVERVIEW.md` records the same gap.
- `docs/vision/DOMAIN_MODEL.md` sections 5 and 7 (aggregate invariant table).

#### Impact

None today - nothing creates assignments yet. From Phase 4 onward, an
unenforced rule is the difference between stable narrative identity and either
over-merging or fragmentation, which ADR-0001/ADR-0014 identify as the
make-or-break product risk.

#### Possible Directions

- Enforce it in the candidate/validation layer (ADR-0002) rather than as a DB
  constraint - the conditions are semantic, not relational.
- Decide during Phase 4 planning whether a rejected assignment is a `rejected`
  candidate with a stored rationale (preferred, per ADR-0002) or a hard error.

#### Decision or Resolution Criteria

Resolved when no code path can persist a `NarrativeEvent` without the rule
having been evaluated, and the evaluation outcome is itself stored.

#### Related ADRs

- ADR-0001, ADR-0002, ADR-0014.

#### Related Tasks

- S001-T008 (persistence only). Next: Roadmap Phase 4.

---

### PRB-004 - `cycle_runs` has no database guard against re-updating a terminal row

```text
Status:       OPEN
Severity:     LOW
Domain:       Cycle / persistence
Owner:        unassigned
Discovered:   2026-08-18 (Sprint 001, S001-T011 review)
Last Updated: 2026-08-19
```

#### Description

`CycleRun` rows move from a running state to exactly one terminal state. The
repository's `update()` has no database-level guard preventing an
already-terminal row from being updated again - unlike the immutability and
append-only triggers used elsewhere in the schema (`documents`,
`evidence_packs`, `llm_runs`, `audit_entries`).

#### Evidence

- Migration `0006_create_cycle_run.py` (partial unique index for overlap
  prevention, no terminal-state trigger).
- Recorded as a non-blocking S001-T011 review follow-up in `CURRENT_STATUS.md`
  section 9.

#### Impact

Inert today: only `cycle/run_cycle.py` writes `CycleRun` rows, and it writes
one terminal state per run. It becomes a real risk if a retry, a resume path,
or a second writer is added.

#### Possible Directions

- A `BEFORE UPDATE` trigger rejecting updates to rows already in a terminal
  status, in the same pattern as the existing triggers.

#### Decision or Resolution Criteria

Address before any code path can write a `CycleRun` more than once (retry,
resume, or observability backfill). Roadmap Phase 10 at the latest.

#### Related ADRs

- ADR-0011.

#### Related Tasks

- S001-T011.

---

## 6. Resolved Problems

### PRB-001 - A local `.env` can leak into the unit suite and break `test_missing_password_is_rejected`

```text
Status:       RESOLVED (2026-08-19)
Severity:     MEDIUM
Domain:       Developer environment / test isolation
Owner:        unassigned
Discovered:   2026-08-18 (Sprint 001, hit repeatedly during T007, T008, T009)
Last Updated: 2026-08-19
```

#### Description

A `.env` file is required locally to run integration tests against the compose
database. On developer machines where a pytest dotenv plugin is installed
(globally or in the active interpreter), that `.env` is loaded into the process
environment before tests run. `tests/unit/test_settings.py::test_missing_password_is_rejected`
then failed: it constructed `Settings(_env_file=None)` expecting a
`ValidationError` for the missing password, but `POSTGRES_PASSWORD` was already
in `os.environ`, so `Settings` validated successfully. `_env_file=None` defends
only against pydantic-settings reading the file.

#### Resolution

S002-T003: `test_missing_password_is_rejected` now `monkeypatch.delenv`s
`POSTGRES_PASSWORD` (matching the sibling HOST test). `tests/conftest.py`
autouse-clears every `POSTGRES_*` variable for unit tests (skips
`integration`-marked tests and anything under `tests/integration/`);
integration tests still see the ambient environment. The trap is noted in
`WORKFLOWS.md`. The CI `.env`-file workaround remains but is no longer
load-bearing for this unit test.

#### Related Documents

- `docs/reference/WORKFLOWS.md`, `.env.example`, `.github/workflows/ci.yml`

#### Related Tasks

- S001-T003 (settings), S001-T013 (CI workaround); closed by S002-T003.

---

### PRB-005 - The planning registries did not exist while agents were told to use them

```text
Status:       RESOLVED (2026-08-19)
Severity:     LOW
Domain:       Process / documentation
Owner:        tech-writer
Discovered:   2026-08-18 (Sprint 001)
Last Updated: 2026-08-19
```

#### Description

`PROJECT_MANAGEMENT.md` section 6 (Definition of Done) requires known
limitations to be recorded in `TECHNICAL_DEBT.md` / `PROBLEM_REGISTRY.md`, and
`DOMAIN_MODEL.md` section 7 names `TECHNICAL_DEBT.md` as the place where an
occurrence of forbidden vocabulary must be logged. Neither file existed for the whole of Sprint 001, so accepted
limitations were scattered across PR bodies and `CURRENT_STATUS.md` section 9
instead of living in one place.

#### Resolution

Both registries were created at Sprint 001 close from the `planning` skill's
templates and backfilled with the four technical-debt entries and four open
problems the sprint produced (this file and `TECHNICAL_DEBT.md`).

#### Remaining gap (not a problem, noted for the next planning pass)

`docs/planning/README.md` and `docs/planning/IDEA_INBOX.md` from the `planning`
skill's file list still do not exist. `IDEA_INBOX.md` is created on first entry
by convention, so its absence is expected; the planning index is not.

#### Related Documents

- `docs/planning/PROJECT_MANAGEMENT.md` sections 3 and 6.
