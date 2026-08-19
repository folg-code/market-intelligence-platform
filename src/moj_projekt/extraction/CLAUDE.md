# extraction/

Responsibility: parse raw model output, judge it with deterministic rules,
and (in the extraction service) persist the verdict's consequences.

## Conventions specific to this module

- The validator never mutates or repairs model output; it only judges.
- Only `service.py` constructs an `Event`, and only on `accepted`.
- Verdicts are `CandidateStatus`, never raw strings.
- Thresholds come from `ValidationConfig`, not from literals in rule bodies.
- Prefer `moj_projekt.llm.artifacts` for schema loading. `moj_projekt.llm`
  lazy-loads `AnthropicClient`, but this package still must not import
  the Anthropic SDK (enforced by the boundary test).
- The service takes an injected `Clock`, `LLMClient`, and `ValidationConfig`.
  The caller owns the `UnitOfWork`; the service flushes via repositories
  and does not commit.
- `LLMRun` is always written in that unit of work. Event rows are written
  only for `accepted` (including a well-formed empty `events` array, which
  is accepted with zero Event rows).

## Gotchas

- Schema `minLength: 1` still accepts whitespace-only `type`/`title`;
  those fail the Event-invariant rule, not schema v1.
- A known merge field (`facts_and_claims` and siblings) is reported as
  `merged_facts_and_claims`, not as a generic schema violation, so the
  two hard rules stay distinguishable. Identical wording in both
  `extracted_facts` and `source_claims` is not a merge (ADR-0008).
- `proposed` means schema-valid but below auto-accept confidence. Hard-rule
  failures are always `rejected`, even when confidence is also low.
- Empty `events` is `accepted` (a document with no economic development).
- `clock.now()` is required for `LLMRun.created_at`; `datetime.now()` /
  `utcnow()` are still forbidden.
- `input_reference_ids` stores the persisted Document UUID as a string so
  it resolves to `documents.id` without a prefix convention.
- Candidate mechanism / interpretation stay on `LLMRun.parsed_output`.
  They are not Event columns.

## Tests

Validator: unit only; no database, HTTP, or SDK. One test per hard/soft
rule plus a table-driven pass case.
Service: unit tests for prompt rendering and `LLMRun` field assembly;
integration tests against the live database for each verdict plus
failure-injection atomicity.
`tests/unit/test_extraction_boundary.py` asserts this package imports no
SQLAlchemy, httpx, or Anthropic SDK. Event construction is allowed in
`service.py` only.
