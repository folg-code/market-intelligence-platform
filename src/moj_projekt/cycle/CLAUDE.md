# cycle/

Responsibility: one 5-minute processing cycle (ADR-0004) - ingest, extract,
and the remaining passthrough stages.

## Conventions specific to this module

- Per-source ingest failures and per-document extract transport failures
  are isolated inside the stage callable; they must not raise out to
  `run_cycle`. The cycle still `SUCCEEDED`. Budget exhaustion is the
  same class of degradation: the cycle succeeds, Documents stay
  `COLLECTED`.
- Extract records document transport failures on `CycleRun.source_outcomes`
  keyed by document id. The budget guard records under
  `llm_budget_approaching` / `llm_budget_ceiling` (see `domain/budget.py`);
  no new CycleRun column.
- An empty extract work queue must not call `LLMClient.complete`
  (ADR-0015 clause 2). That is asserted against `FakeLLMClient.call_count`.
- The budget guard is consulted before each call. Period spend is the UTC
  calendar month of `CycleRun.started_at` (the injected cycle clock), not
  `datetime.now()`. In-cycle flushed `LLMRun` rows count; one call may
  still overshoot the ceiling (the per-cycle cap is the blast radius).
- `EVENTS_EXTRACTED` means a terminal verdict was reached, not that Event
  rows exist (D-S002-04 clause 3). Documents skipped for budget stay
  `COLLECTED` and resume when the period rolls over.

## Gotchas

- `ExtractionService` writes only after the client returns, so catching
  around `extract()` isolates transport failures without savepoints.
  Persistence failures after a successful `extract()` still fail the
  stage and roll back the whole stage unit of work.
- Default `run_once` uses `FakeLLMClient` with an empty-events payload
  until T011 wires `AnthropicClient`. That default is a terminal verdict,
  so it advances Documents; tests that need Events inject the recorded
  fixture client.
- Cost uses `input_tokens` / `output_tokens` against the `llm/models.py`
  rate table. Cache counters are recorded but not billed (no cache rates).

## Tests

- Unit tests inject `Clock` + `FakeLLMClient` (or a raising double).
- Integration tests against the live database, same as ingest.
