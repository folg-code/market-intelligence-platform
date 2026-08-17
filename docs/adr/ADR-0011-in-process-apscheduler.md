# ADR-0011 - In-process APScheduler drives the 5-minute cycle; no worker or broker process

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

ADR-0004 fixes a single 5-minute processing cadence; ADR-0005 rules out a
message broker and distributed workers. Neither decides the *mechanism* that
fires the cycle - `ARCHITECTURE_FOUNDATIONS.md` section 13 left this open
(APScheduler in-process vs Celery/RQ + beat vs system cron vs an orchestrator
such as Airflow/Prefect).

Constraints from the existing decisions:

- Exactly one recurring job in MVP (the cycle), plus the Morning Brief job (on
  demand + a configurable schedule) - two schedules, not a DAG.
- The cycle must be idempotent, resumable, and **non-overlapping**: a slow cycle
  must not be joined by the next tick (Foundations section 4).
- No broker, no queue service, no distributed workers (ADR-0005).
- Deployment is a single machine (ADR-0013).

## Decision

- **APScheduler runs in-process, inside the FastAPI application**, started on
  application startup and stopped on shutdown.
- **Two jobs only**: the 5-minute processing cycle, and the Morning Brief job
  (schedulable plus manually triggerable).
- **Overlap is prevented at the scheduler level** (`max_instances=1`) and
  additionally at the data level by a cycle run record - the cycle's idempotency
  is not allowed to depend on the scheduler behaving correctly.
- **Every cycle writes a run record** (start, end, per-stage outcome, per-source
  outcome, failure reason). The run record, not scheduler logs, is the audit
  surface.
- **`coalesce=True` with a bounded misfire grace**: after a downtime window the
  system runs one catch-up cycle, not a backlog of missed ticks. The cycle
  processes whatever is new since the last successful run, so missed ticks lose
  freshness, never data.
- **The cycle is invocable directly** (a CLI/entrypoint calling the same code
  path), so it is testable and re-runnable without the scheduler.
- **No separate worker process, no broker, no external orchestrator** in MVP.

## Consequences

### Positive

- One deployable process for API + scheduling + processing: matches the single
  Docker Compose service shape of ADR-0013 and the ADR-0005 "one process plus
  one database" development story.
- No serialization boundary between the scheduler and the cycle - jobs are
  plain function calls, so the domain code stays infrastructure-free
  (Foundations principle 1) and directly unit-testable.
- Schedule changes are code/config in one repo, not an operator-managed crontab
  or an orchestrator UI whose state lives outside version control.

### Negative

- **Schedule state is tied to process lifetime.** A restart during a cycle
  aborts it; recovery depends on the cycle being genuinely resumable, which
  becomes a hard requirement rather than a nice property.
- API request load and cycle work share a process (and, for synchronous work,
  a GIL). A long LLM-bound cycle can degrade dashboard responsiveness; at
  single-user scale this is acceptable but it is a real coupling.
- Scaling out later means removing the scheduler from the API process - a
  known, contained change, but a change nonetheless.
- No built-in retry/backoff semantics beyond what we implement ourselves.

### Neutral / Trade-offs

- Job store: in-memory is sufficient for two fixed schedules (they are
  re-registered on startup); a persistent job store is unnecessary and would
  add migration surface for no benefit.
- If cycle duration ever approaches the 5-minute interval, the response is
  narrower per-cycle scoping (Roadmap Phase 10 risk), not a second cadence -
  that would supersede ADR-0004.

## Alternatives Considered

### Option A - Celery / RQ with a beat scheduler

- Pros: mature retry/backoff, task-level visibility, horizontal scale.
- Cons: requires a broker (Redis/RabbitMQ) - directly contrary to ADR-0005 -
  plus a second process type to run, deploy, and monitor.
- Reason rejected: buys distributed-execution capability that a single-user MVP
  with one recurring job has no use for.

### Option B - System cron (or a Compose sidecar running cron)

- Pros: trivially simple; survives application restarts; process isolation
  between the API and the cycle.
- Cons: schedule lives outside the application and outside version control;
  per-run process startup cost; overlap prevention and run recording must be
  built anyway; Windows/Linux development parity is poor.
- Reason rejected: worse observability and worse local-development story for no
  architectural gain.

### Option C - An orchestrator (Airflow / Prefect / Dagster)

- Pros: excellent DAG visibility, retries, backfills.
- Cons: an entire additional platform for two jobs and no DAG.
- Reason rejected: operational surface out of all proportion to the workload;
  violates YAGNI (Foundations principle 4).

### Option D - A plain `asyncio` loop with `sleep`

- Pros: zero dependency.
- Cons: we would re-implement misfire handling, coalescing, overlap prevention,
  and graceful shutdown - badly.
- Reason rejected: APScheduler is a small, well-understood library that already
  solves exactly this.

## Follow-up

- Define the cycle run record's schema alongside the cycle skeleton (Phase 2).
- Decide the Morning Brief default schedule (a product setting, not an
  architectural one) - still **open**.
- Revisit if cycle duration exceeds ~60% of the interval (Phase 10).

## Related

- ADR-0004 (single 5-minute cadence)
- ADR-0005 (no broker, no distributed workers)
- ADR-0013 (single-host Docker Compose deployment)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` sections 2, 4, 9
