# Technical Debt

## 1. Purpose

Knowingly-accepted implementation shortcuts. Technical debt is not every
missing feature and not every problem - unresolved problems belong in
[`PROBLEM_REGISTRY.md`](PROBLEM_REGISTRY.md).

An entry belongs here only when all four hold:

1. the shortcut was accepted knowingly,
2. the limitation is understood,
3. the system works correctly within the stated boundaries,
4. the repayment condition is known.

This file was created at the close of Sprint 001 and backfilled with the debt
that sprint accepted (see `sprints/SPRINT_001.md` section 9).

## 2. Statuses

```text
ACCEPTED
PLANNED_REPAYMENT
IN_PROGRESS
REPAID
OBSOLETE
```

## 3. Priority

```text
CRITICAL
HIGH
MEDIUM
LOW
```

## 4. Debt Entry Template

```markdown
## TD-XXX - Title

Status:
Priority:
Domain:
Introduced:
Target Review:
Owner:

### Accepted Shortcut
### Reason
### Consequences
### Safe Operating Boundary
### Repayment Trigger
### Repayment Direction
### Related Problems
### Related Tasks
```

## 5. Accepted Technical Debt

### TD-001 - The forbidden-vocabulary check misses a forbidden word inside a separator-less identifier

```text
Status:        ACCEPTED
Priority:      LOW
Domain:        Tests / vocabulary discipline
Introduced:    2026-08-18 (Sprint 001, S001-T008, commit 1ad9f17)
Target Review:  when a forbidden term actually slips through review
Owner:         unassigned
```

#### Accepted Shortcut

`tests/unit/test_domain_vocabulary.py` matches `sentiment_score`,
`prediction`, `signal`, and `forecast` as whole tokens after splitting
identifiers on snake_case/camelCase boundaries. A forbidden word buried in an
identifier with no separator at all - `postsignal_flag`, `signaled_at` - is not
flagged. The test asserts this behaviour explicitly (lines 116-117).

#### Reason

The checker went through two failure modes in one task. Substring matching
produced a false positive on the domain model's own required field
`Narrative.contradiction_signals` (`DOMAIN_MODEL.md` section 3). The
word-boundary fix that replaced it over-corrected and stopped catching genuine
compounds such as `signal_strength`. Token-based matching is the version that
gets both of those right. Tightening further - back toward substring matching -
reopens the `contradiction_signals` false positive, which is worse: a checker
that cries wolf on required vocabulary gets disabled.

#### Consequences

A developer who deliberately or accidentally writes `postsignal` evades the
automated check. Human review remains the only gate for that shape.

#### Safe Operating Boundary

Correct for every naming convention actually used in this codebase - all
identifiers are snake_case or camelCase, so every real forbidden usage would be
tokenized and caught.

#### Repayment Trigger

A forbidden term reaching `main` in a separator-less identifier, or the
codebase adopting a naming style that concatenates words.

#### Repayment Direction

Add an explicit deny-list of known-good exceptions (`contradiction_signals`)
and then tighten matching to substring, rather than loosening tokenization.

#### Related Documents

- `docs/vision/DOMAIN_MODEL.md` section 7; root `CLAUDE.md` (vocabulary rule).

#### Related Tasks

- S001-T005 (test introduced), S001-T008 (both fixes).

---

### TD-002 - `EvidencePack.market_evidence` must-be-empty is enforced in the domain layer only

```text
Status:        ACCEPTED
Priority:      MEDIUM
Domain:        Domain / persistence
Introduced:    2026-08-18 (Sprint 001, S001-T007)
Target Review: when market data enters the roadmap (Post-MVP track item 4)
Owner:         unassigned
```

#### Accepted Shortcut

`EvidencePack.__post_init__` rejects a non-empty `market_evidence`
(`src/moj_projekt/domain/evidence_pack.py:75`). The `evidence_packs` table has
the column but no CHECK constraint backing that rule - unlike the other
`EvidencePack` invariants (`independent_source_count <= source_count`,
`evidence_version >= 1`, no-UPDATE trigger), which all have DB-level backstops.

#### Reason

A deliberate, reviewed call, not an oversight. Every other invariant in
migration `0003` is permanent. This one is not: ADR-0003 makes market evidence
valid data as soon as a market data feed exists, so a DB constraint added now
would have to be dropped by a later migration. The rule is a temporary MVP
condition - "there is no market data yet" - not a domain invariant, and the
deterministic market-language validator
(`ARCHITECTURE_FOUNDATIONS.md` section 6) is the real enforcement of the
product promise it protects.

#### Consequences

Any write path that bypasses the domain type - a raw SQL fix-up, a future bulk
import - could store market evidence without the rule firing.

#### Safe Operating Boundary

All writes go through `SqlAlchemyEvidencePackRepository`, which constructs the
domain object; there is no bulk-import path. Nothing in the MVP produces market
evidence at all.

#### Repayment Trigger

Two directions, whichever comes first: a non-domain write path to
`evidence_packs` appears (add the CHECK), or a market data feed lands (remove
the rule entirely, per ADR-0003).

#### Repayment Direction

If market data is still absent when a second write path appears, add
`CHECK (jsonb_array_length(market_evidence) = 0)` in a migration and delete it
again when the feed arrives.

#### Related ADRs

- ADR-0003; `ARCHITECTURE_FOUNDATIONS.md` section 6.

#### Related Tasks

- S001-T007.

---

### TD-003 - `identity_embedding` dimension is a placeholder chosen before the embedding model

```text
Status:        ACCEPTED
Priority:      MEDIUM
Domain:        Persistence / narrative identity
Introduced:    2026-08-18 (Sprint 001, S001-T008)
Target Review: at the embedding-model-source decision (Roadmap Phase 4)
Owner:         unassigned
```

#### Accepted Shortcut

`narratives.identity_embedding` is `vector(384)`, with
`NARRATIVE_EMBEDDING_DIMENSION = 384` documented at the point of use in both
`persistence/models.py` and migration `0004`. 384 matches common small local
open-weight sentence-embedding models, which is the direction ADR-0014 leans -
but the embedding model source is still an open decision.

#### Reason

pgvector requires a fixed dimension at column-creation time, and the schema was
being built a phase ahead of the embedding work. The sprint plan called this
out in advance (S001-T008 dependency note and the sprint risk table) and
required the placeholder to be documented rather than the column deferred.

#### Consequences

If the eventual model emits a different dimension, the column must be altered
and every stored embedding recomputed.

#### Safe Operating Boundary

Cheap by construction: embeddings are derived data that retrieve and rank but
never decide identity (ADR-0001/ADR-0014), the column is nullable, and no row
has an embedding yet. A change is a migration plus a re-embedding pass, not
data loss.

#### Repayment Trigger

The embedding-model-source decision (`CURRENT_STATUS.md` section 8) being made.

#### Repayment Direction

Confirm the model's dimension; if it is not 384, alter the column and re-embed
in the same migration wave, before any matching logic depends on stored
vectors.

#### Related ADRs

- ADR-0001, ADR-0014.

#### Related Tasks

- S001-T008.

---

### TD-004 - `NarrativeInstrumentImpact` keeps no assessment history

```text
Status:        ACCEPTED
Priority:      LOW
Domain:        Persistence / impact
Introduced:    2026-08-18 (Sprint 001, S001-T009)
Target Review: Roadmap Phase 6
Owner:         unassigned
```

#### Accepted Shortcut

One row per `(narrative_id, instrument)`, replaced in place by
`upsert()` (`INSERT ... ON CONFLICT DO UPDATE`). A re-assessment overwrites the
previous one; there is no versioned history the way `EvidencePack` has
`evidence_version`.

#### Reason

A documented judgment call. `DOMAIN_MODEL.md` specifies "one current assessment
per (narrative, instrument)" and gives this entity none of the versioning
language it gives `EvidencePack`. Building history that no requirement asks for
would be over-modelling, which the sprint's own risk table warned against.

#### Consequences

"How did this narrative's NQ direction change over the last three days?" is not
answerable from `narrative_instrument_impacts` alone.

#### Safe Operating Boundary

Acceptable while impact assessments are not yet produced automatically and no
requirement asks for impact history. Note that the reasoning behind each
assessment is not lost even so: every material assessment will carry its
`LLMRun` and `evidence_refs`, and `llm_runs` is append-only.

#### Repayment Trigger

A product requirement for impact history or drift analysis (Phase 6 or the
post-MVP research platform), or an alert type that needs to compare an
assessment against its predecessor.

#### Repayment Direction

Add an `assessment_version` and switch `upsert()` to insert-new-version, in the
same shape as `EvidencePack`.

#### Related ADRs

- ADR-0006.

#### Related Tasks

- S001-T009.

---

## 6. Debt Review Rules

Review debt:

- at a sprint retrospective,
- before the end of a phase,
- before adding a related abstraction,
- when a repayment trigger fires,
- when debt starts threatening correctness.
