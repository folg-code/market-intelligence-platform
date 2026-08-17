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

## More

Full documentation: [docs/README.md](docs/README.md)
