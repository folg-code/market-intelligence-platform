# Idea Inbox

## 1. Purpose

Directions worth thinking about before they are worth doing. An idea here has
been considered seriously enough to write down, but is **not** a commitment, not
a plan, and not a binding decision.

This file exists so that exploratory analysis has somewhere to live other than a
chat transcript. An idea that survives contact with reality graduates: it becomes
an ADR (binding decision), a roadmap phase, a sprint task, or a
[`PROBLEM_REGISTRY.md`](PROBLEM_REGISTRY.md) entry. An idea that dies is marked
`REJECTED` with the reasoning kept, so the same discussion does not get had twice
from scratch.

Boundaries against the sibling registries:

- Something **wrong or unknown** about the system as built -> `PROBLEM_REGISTRY.md`
- A shortcut **knowingly accepted** -> `TECHNICAL_DEBT.md`
- A decision **already made** and binding -> `docs/adr/`
- A direction **worth evaluating later** -> here

An idea is not a `Proposed` ADR. A `Proposed` ADR is a decision the project
intends to make and is awaiting approval on (ADR-0015 and ADR-0016 were
`Proposed` for hours, not months). An idea may never become anything.

## 2. Statuses

```text
RAW              captured, not yet analysed
EXPLORED         analysed; no action taken and none currently warranted
TRIGGERED        a decision trigger has fired; needs a real decision now
PROMOTED         became an ADR, a roadmap phase, or a sprint task
PARKED           deliberately deferred to a named point in time
REJECTED         considered and declined; reasoning retained
```

## 3. Horizon

When the idea could plausibly matter. This is not a schedule.

```text
NOW
NEXT_SPRINT
MVP
POST_MVP
SPECULATIVE
```

## 4. Idea Entry Template

```markdown
## IDEA-XXX - Title

Status:
Horizon:
Domain:
Raised By:
Raised:
Last Updated:

### Description
### Motivation
### Analysis
### Arguments For
### Arguments Against
### Current Recommendation
### Decision Triggers
### Related Documents
### Related ADRs
```

## 5. Active Ideas

### IDEA-001 - Replace external LLM providers with a self-hosted or self-trained model

```text
Status:       EXPLORED
Horizon:      POST_MVP (with one NOW component - see Current Recommendation)
Domain:       Architecture / LLM boundary
Raised By:    human owner
Raised:       2026-08-19
Last Updated: 2026-08-19
```

#### Description

Whether the project should stop depending on an external LLM provider
(currently Anthropic, per ADR-0010 and ADR-0016) and instead run - or train -
its own model.

"Own model" covers four distinct undertakings, which must not be discussed as
one:

| Variant | Assessment |
|---|---|
| A. Foundation model trained from scratch | Not viable. Millions of dollars, thousands of GPUs, a research team. Out of scope permanently. |
| B. Fine-tuning an open-weight model (Qwen, Llama, Mistral) on this task | Viable. LoRA on a 7-14B model is tens of dollars per run. Requires training data. |
| C. Self-hosting an open-weight model without fine-tuning | Viable and simplest. Usually what "cutting off external providers" means in practice. |
| D. Small task-specific models (NER, topic classifier, embeddings) | Viable, cheap, and **already partly planned** - the embedding-model-source decision is open and blocks Phase 4. |

Only B, C and D are worth further thought.

#### Motivation

Raised as a strategic question about provider independence, not in response to a
failure. Related live facts at the time of raising:

- Sonnet 5's introductory pricing ($2/$10 per MTok) expires 2026-08-31.
- Models are retired on a schedule; a future migration off
  `claude-haiku-4-5-20251001` will force re-validation of every prompt.
- S002-T011 is blocked on obtaining an API key - a concrete, if minor,
  illustration of external dependency.

#### Analysis

**Economics - this is the decisive part.**

Current spend is roughly $4.50/month (Haiku 4.5, ~900 documents/month), against
the $10/month MVP ceiling set in ADR-0015.

| Item | Cost |
|---|---|
| RTX 3090 24GB (used) | ~$700-900 one-off |
| RTX 4090 24GB | ~$1600-2000 one-off |
| Electricity, under load | ~5 GPU-hours/month of real work ≈ $0.50/month |
| Electricity, idle | GPU sitting in a machine already running 24/7 for the cycle ≈ $3-6/month (estimate at ~$0.20/kWh) |

Hardware payback against a $4.50/month bill is approximately **440 months**.
Even against the $50/month product ceiling from ADR-0015 it exceeds three years,
by which point the card is obsolete.

Worse: the **idle** power draw alone ($3-6/month) is comparable to the entire
current API bill. At this volume, self-hosting is not cheaper - it is more
expensive, before counting a single hour of engineering time.

**The cost argument for self-hosting does not exist at ~900 documents/month.**
It inverts only at roughly 10-50x the current volume.

**Quality.** The product is not the plumbing; it is the content of
`economic_mechanism` and `market_interpretation`. A well-quantised 14B model
handles structured extraction acceptably, but economic reasoning requires world
knowledge and multi-step inference, where the gap to a frontier model is
material rather than cosmetic. The highest-risk specific failure is blurring
`extracted_facts` against `source_claims` (ADR-0008) - smaller models routinely
conflate "the Fed raised rates" with "an analyst expects the Fed to raise
rates", and that distinction is where the system's credibility lives.

**The architecture already mitigates this more than is obvious.** Under
ADR-0002 no model output is truth: the deterministic validator returns
`accepted`/`proposed`/`rejected` and rejections are persisted. A weaker model
therefore shows up as a **higher rejection rate, not as corrupted data**. The
degradation is measurable rather than silent - an unusually favourable property
for evaluating this idea empirically.

**The fine-tuning bootstrap problem.** Variant B needs 1k-10k labelled examples
in this project's schema. The standard route is distillation: run the frontier
model, keep validator-accepted outputs as gold labels, fine-tune on those. So
escaping the API requires first using it heavily. At ~900 documents/month,
accumulating 10k naturally takes about a year.

**The audit trail is already the dataset.** `LLMRun` records input references,
`raw_output`, `parsed_output`, `validation_status` and `validation_errors` in
the same transaction as the decision (ADR-0007). Every row is an
(input, output, verdict) triple - which is exactly a distillation corpus and
exactly an evaluation set. This means **waiting costs nothing and yields the
data that turns this from a philosophical question into an empirical one.**

**Engineering cost.** Realistically 3-6 weeks of focused work for a serving
stack, quantisation, prompt re-tuning for a different model, an evaluation
harness, and monitoring - a sprint or two taken from a product that has no
dashboard, no alerts, and no working narrative yet.

#### Arguments For

- **Provider independence** - immune to price changes, model retirement, rate
  limits, and safety-classifier refusals. Refusals are not hypothetical for a
  system reading news about sanctions or attacks on financial infrastructure.
- **Reproducibility, and this one is strong for this project specifically.**
  ADR-0007 exists to answer "why did the system decide this, on this date".
  Self-hosted weights are pinned permanently - a checksum, not a vendor promise.
  ADR-0010 forbids the `latest` alias precisely to prevent model drift; a local
  model eliminates that class of risk entirely rather than merely bounding it.
- **Data locality** - marginal today (public news), but it would matter if
  trader notes or position data ever entered the pipeline.
- **No per-call cost**, which removes the budget guard (S002-T010) as a
  constraint on how often the pipeline may think.

#### Arguments Against

- **No cost saving at this scale** - hardware payback is ~440 months; idle power
  alone roughly equals the current bill.
- **Quality gap on exactly the reasoning the product sells**, with
  facts-vs-claims separation as the specific danger.
- **3-6 weeks of engineering** diverted from unbuilt product surface.
- **Fine-tuning depends on the provider it aims to replace** (distillation), and
  the corpus needs about a year to accumulate at current volume.
- **Permanent pinning cuts both ways** - a frozen local model never improves,
  in a field that is still moving quickly.
- **New operational burden**: GPU drivers, CUDA, quantisation, OOM debugging -
  against ADR-0013's deliberately minimal single-host deployment.

#### Current Recommendation

Do not cut over. Three moves instead:

1. **Keep the external API for extraction.** $4.50/month against a ~37-year
   payback is not a problem worth solving.
2. **Go local for embeddings now.** The embedding-model-source decision is
   already open and already blocks Phase 4. `bge-small` / `all-MiniLM` class
   models run on CPU, cost nothing per call, and remove a dependency outright.
   This is the part of "cutting off" that is free and unambiguously correct -
   and it also settles the `vector(384)` placeholder recorded in TD-003.
3. **Add a `LocalLLMClient` adapter only when a trigger fires.** The client port
   and `FakeLLMClient` already exist from S002-T006, so this is days of work,
   not a rebuild. Because ADR-0002 records rejections, both backends can be run
   over the same documents and **compared on rejection rate** - an experiment,
   not a bet.

The end state this points at is a hybrid, which is simply ADR-0010's existing
tiering with a local tier added: small local models for Tier A (entities, topic
classification, embeddings - high volume, low stakes), frontier API for Tier B/C
(economic mechanism, market interpretation - low volume, high stakes).

#### Decision Triggers

Any of these moves this entry to `TRIGGERED`:

- Document volume grows ~10x or more (Phases 4-6 add per-*narrative* LLM work on
  top of per-*document* work, so this is plausible rather than remote).
- A hard data-privacy requirement appears - e.g. trader notes or position data
  entering the pipeline.
- Repeated safety-classifier refusals on legitimate market content.
- The $50/month product ceiling in ADR-0015 is breached.
- The pinned model is deprecated and prompt re-validation proves expensive.

#### Related Documents

- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` sections 5 and 7
- `docs/planning/TECHNICAL_DEBT.md` - TD-003 (`vector(384)` placeholder)
- `docs/planning/CURRENT_STATUS.md` section 8 - the open embedding-model-source
  decision

#### Related ADRs

- ADR-0002 (candidate/validation layer - the reason quality loss would be
  measurable rather than silent)
- ADR-0007 (LLM run audit record - the reason the corpus already exists)
- ADR-0010 (Anthropic as provider; pinned model IDs)
- ADR-0013 (single-host Docker Compose deployment)
- ADR-0014 (pgvector; the embedding-model-source follow-up)
- ADR-0015 (cost ceiling: $10 MVP / $50 product)
- ADR-0016 (Haiku 4.5 as the default extraction model)

## 6. Graduated and Rejected Ideas

None yet.

## 7. Update Rules

- Add an entry when a direction is discussed seriously enough that re-deriving
  the reasoning later would be wasteful.
- Update `Last Updated` and `Status` when a trigger fires or the analysis
  changes materially.
- On graduation, set `PROMOTED`, move the entry to section 6, and link the ADR,
  roadmap phase, or task it became.
- On rejection, set `REJECTED`, move it to section 6, and keep the reasoning -
  the point of the record is to avoid rehearsing the same argument.
