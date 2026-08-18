# Market Intelligence Platform

Evidence-backed market narrative intelligence for a single discretionary trader:
detects material narratives from official and news sources, explains them, and
assesses impact on NQ / BTC / GOLD - with full traceability.

## Commands

The toolchain lands in Sprint 001 (task S001-T002/T014); once
`docs/reference/WORKFLOWS.md` exists it is the single source for setup, compose,
migrations, seeding, running one cycle, and running checks. Do not duplicate
those commands here.

## Coding conventions for this project

Only what sets this project apart - not general Python/FastAPI knowledge.

- **LLM output is never truth.** Every model result goes through the
  deterministic validation layer and comes out `accepted` / `proposed` /
  `rejected`. No code path writes a domain decision straight from a model
  response (ADR-0002).
- **Every material LLM call writes an `LLMRun`** with `provider`, `model`,
  `model_version`, `prompt_version` and input *references* (not just a hash),
  in the same unit of work as the decision it produced (ADR-0007, ADR-0010).
- **Pinned model IDs only** - never a floating "latest" alias (ADR-0010).
- **Documents are immutable.** A changed page becomes a new Document; nothing
  overwrites collected content.
- **Domain code imports no infrastructure.** `domain/` must not import
  SQLAlchemy, httpx, or the Anthropic SDK - there is a test asserting this.
  Persistence is reached through repository interfaces.
- **The clock is injected.** No `datetime.now()` / `utcnow()` in domain or cycle
  code; the pipeline is time-sensitive and must be testable.
- **Migrations only.** Schema changes go through Alembic; no `create_all()`, and
  migrations never run on application startup (ADR-0013).
- **Derived data is not identity.** Embeddings and similarity scores retrieve,
  rank, or block - they never decide. Narrative identity is the semantic
  `canonical_key` (ADR-0001, ADR-0014).
- **Vocabulary is binding.** Use the terms in `docs/vision/DOMAIN_MODEL.md`
  section 7 exactly. `sentiment_score`, "prediction", "signal", and "forecast"
  are forbidden in code and docs - their appearance is logged as technical debt.
- **Market-pricing language is forbidden** while there is no market data feed;
  a deterministic post-generation validator enforces this, not a prompt
  (`ARCHITECTURE_FOUNDATIONS.md` section 6).
- **Value objects, not raw strings.** Instrument, tier, validity, lifecycle,
  direction, horizon, override state and candidate status are typed - never bare
  `str`.
- **A failing source must not fail the cycle.** Ingestion errors are isolated
  per source and recorded in the CycleRun record.

## Per-task delivery loop

Every Sprint 001+ task follows this loop, in this order, with no step skipped:

```text
engineer (one task, one PR, task branch off the sprint branch)
  -> tester    (independent verification against acceptance criteria - re-run
                claims live, don't trust the engineer's self-report)
  -> reviewer  (quality/process/ADR compliance - Approve or Request Changes;
                on Request Changes, back to engineer on the same branch, then
                re-verify with tester + reviewer before proceeding)
  -> tech-writer (sync README / reference docs / CURRENT_STATUS / the sprint
                  task table to what was actually merged - not deferred to
                  sprint close)
  -> human approval, then merge into the sprint branch
```

`tech-writer` runs after every merged task, not only at sprint close - this
was skipped for S001-T002..T006 in one session and had to be caught up in a
single retroactive pass; don't repeat that. Sprint close still gets its own
larger documentation/retro pass on top of this per-task sync.

### Mechanical gates are pre-commit + CI's job, not tester/reviewer's

Pre-commit hooks (`ruff check`, strict `mypy`, hygiene checks on every
commit; the DB-free unit suite on every push) and CI (the same lint/type-check
plus the full unit+integration suite against a live pgvector service, on
every push/PR) are the mechanical quality gates. `tester` and `reviewer` do
not re-run `ruff check`/`mypy`/the unit-test suite themselves as routine
verification - they confirm CI is green for the exact commit under review
(not stale, not from an earlier force-push), then spend their effort on what
those gates cannot see: acceptance criteria against a live database
(triggers, constraints, migrations, idempotency, concurrency), ADR/
architecture compliance, and whether tests genuinely assert the claimed
invariants rather than merely achieving line coverage.

If CI is not green, not yet finished, or its result can't be confirmed for
the reviewed commit, `tester`/`reviewer` fall back to re-running the
mechanical checks themselves - the point is to cut *routine* duplication, not
to trust an unverified CI badge.

## More

Full documentation: [docs/README.md](docs/README.md)
