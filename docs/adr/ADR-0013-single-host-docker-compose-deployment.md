# ADR-0013 - Deployment target: local machine or a single VPS via Docker Compose

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The source discovery document never addressed hosting;
`ARCHITECTURE_FOUNDATIONS.md` section 13 flagged it as blocking, because it
determines secrets handling, backup strategy, and whether the 5-minute cycle can
be a long-running process (ADR-0011 depends on the answer).

Constraints:

- Single-user system, no multi-tenancy, no HA requirement, no external
  availability commitment.
- Two runtime components only: the application (API + scheduler + processing)
  and PostgreSQL with the pgvector extension (ADR-0014).
- The user must be able to run the system on their own machine for development
  and, when useful, leave it running unattended somewhere.

## Decision

- **The deployment unit is a Docker Compose stack on a single host** - the
  user's local machine during development, optionally a single small VPS for
  unattended running. The same Compose file serves both; only environment
  configuration differs.
- **Two services**: `app` (FastAPI + APScheduler + the processing cycle, one
  container) and `db` (PostgreSQL with pgvector, official image, named volume
  for data).
- **No managed cloud services, no Kubernetes, no multi-service orchestration**
  in MVP.
- **Configuration and secrets come from the environment** (`.env` file, not
  committed; `.env.example` committed). The only secret at MVP is the Anthropic
  API key. No secrets manager.
- **Backup is a documented `pg_dump` procedure** against the named volume, with
  restore exercised at least once (Roadmap Phase 10 completion criterion). Not
  automated infrastructure - a documented, tested manual procedure.
- **Database migrations run as an explicit step**, not implicitly on application
  startup, so a bad deploy cannot half-migrate a running system.
- **The app container is stateless**; all durable state is in the database
  volume. Losing the container loses nothing.

## Consequences

### Positive

- Development and "production" are the same shape, so a class of environment
  drift bugs simply does not exist.
- Onboarding and disaster recovery are both "clone, set `.env`, `compose up`,
  restore dump".
- Cost is a single small VPS or nothing at all.
- Bounded operational surface matches the anti-scale stance (Vision section 18)
  and ADR-0005's single-store shape.

### Negative

- **No high availability.** Host down = system down; a missed maintenance window
  means missed cycles (ADR-0011's coalescing limits the damage to freshness, not
  data).
- Backups are only as good as the human running them - the most likely real
  failure mode of this decision.
- Vertical scaling only; the pgvector index and LLM concurrency share one box.
- Secrets in a `.env` file on a host are adequate for one user and one key, and
  would not be adequate for anything more.

### Neutral / Trade-offs

- If the system ever leaves single-user use, hosting is the first decision to
  revisit - it does not constrain the application's internal structure, so the
  change is contained.
- Whether the VPS is exposed to the public internet (and therefore what protects
  the dashboard) is a separate question, deliberately not answered here.

## Alternatives Considered

### Option A - Managed container platform (Fly.io / Render / Cloud Run) with a managed Postgres

- Pros: managed backups, TLS, restarts, less host maintenance.
- Cons: recurring cost; pgvector availability varies by provider tier; a
  long-running in-process scheduler fits awkwardly with scale-to-zero and
  multi-instance defaults (would risk duplicate cycles, undermining ADR-0011).
- Reason rejected: pays money and complexity for availability guarantees a
  single-user research tool does not need, and fights the single-process shape.

### Option B - Kubernetes

- Pros: standard, portable.
- Cons: enormous operational surface for two containers.
- Reason rejected: obviously disproportionate.

### Option C - Bare-metal install (no containers), systemd + local PostgreSQL

- Pros: no Docker layer; slightly lower resource use.
- Cons: environment drift between the developer's Windows machine and a Linux
  VPS; pgvector installation becomes a manual per-host chore.
- Reason rejected: the containerized parity is worth more than the saved layer,
  particularly given a Windows development host.

### Option D - Local-only, no remote option at all

- Pros: simplest; no secrets leave the machine.
- Cons: the machine must stay awake for the 5-minute cycle to keep producing a
  morning brief.
- Reason rejected: not chosen as a restriction - the same Compose stack supports
  both, so nothing is lost by allowing the VPS case.

## Follow-up

- Decide how the dashboard is protected when reachable beyond localhost (single
  static credential, reverse-proxy basic auth, or network restriction) - still
  **open**; required before any non-local exposure.
- Write the backup/restore procedure into `docs/reference/WORKFLOWS.md` and
  exercise it (Phase 10).
- Decide the retention policy for document bodies and LLM `raw_output`, which
  drives volume sizing - still **open**.

## Related

- ADR-0005 (single PostgreSQL store; one process plus one database)
- ADR-0011 (in-process scheduler assumes a single long-running instance)
- ADR-0014 (pgvector must be present in the database image)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` sections 2, 9
