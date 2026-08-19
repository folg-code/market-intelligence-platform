# extraction/

Responsibility: parse raw model output and judge it with deterministic
rules. Persistence and LLM calls live in the extraction service (T008),
not here.

## Conventions specific to this module

- The validator never mutates or repairs model output; it only judges.
- It never constructs an `Event` - that is the extraction service's job,
  and only on `accepted`.
- Verdicts are `CandidateStatus`, never raw strings.
- Thresholds come from `ValidationConfig`, not from literals in rule bodies.
- Import schema artifacts from `moj_projekt.llm.artifacts`, never from
  `moj_projekt.llm` (that package `__init__` imports the Anthropic client).

## Gotchas

- Schema `minLength: 1` still accepts whitespace-only `type`/`title`;
  those fail the Event-invariant rule, not schema v1.
- A known merge field (`facts_and_claims` and siblings) is reported as
  `merged_facts_and_claims`, not as a generic schema violation, so the
  two hard rules stay distinguishable.
- `proposed` means schema-valid but below auto-accept confidence. Hard-rule
  failures are always `rejected`, even when confidence is also low.
- Empty `events` is `accepted` (a document with no economic development).

## Tests

Unit only; no database, HTTP, or SDK. One test per hard/soft rule plus a
table-driven pass case. `tests/unit/test_extraction_boundary.py` asserts
this package imports no SQLAlchemy, httpx, or Anthropic SDK.
