# ADR-0005 - PostgreSQL as the single store and FastAPI as the alert/read path; no message broker

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

Vision section 16 specifies the MVP alert channel literally as
`Alert -> PostgreSQL -> FastAPI -> Dashboard alert feed`, and only in-app alerts
are required. Section 18 lists Kafka as an explicit non-goal; section 20 defers
Kafka to "Advanced Infrastructure - only when real throughput or decoupling
requirements justify it".

The system's data is heterogeneous: relational core entities, semi-structured
LLM payloads, append-only audit logs, and evidence snapshots. The tempting shape
is a polyglot store (relational + document store + queue).

## Decision

- **PostgreSQL is the single system of record** for Documents, Events,
  Narratives, EvidencePacks, instrument impacts, alerts, LLM runs, and audit
  entries. Semi-structured payloads (raw metadata, raw/parsed LLM output,
  evidence items) use JSONB rather than a second database.
- **Alerts are rows**, written by the processing cycle in the same transaction
  as the state change that triggered them.
- **FastAPI serves the read path** for the dashboard (brief, narratives,
  exposure, alert feed) and the human-override write path.
- **The dashboard polls**; no WebSocket/SSE push in MVP - a 5-minute cadence
  does not justify a push transport.
- **No message broker, no queue service, no distributed workers.**

## Consequences

### Positive

- One store means one backup, one migration path, one transaction boundary -
  and the alert can be written atomically with its cause, which is exactly what
  makes alert deduplication and audit reliable.
- Drastically lower operational surface for a single-user system.
- The whole system can run as one process plus one database in development.

### Negative

- Coupling: a database outage takes down ingestion, processing, and the UI
  together.
- Polling wastes a little work and caps alert freshness at the poll interval
  (irrelevant at a 5-minute cadence, would matter if the cadence tightened).
- JSONB is schemaless - drift in LLM payload shape is not caught by the database
  and must be caught by schema validation in code (ADR-0002).
- Scaling beyond one node is not addressed; deliberately.

### Neutral / Trade-offs

- Long-running processing and API serving may share a process or be split; that
  is a deployment decision, not an architectural one, and depends on the still
  **open** hosting decision.
- Retention of large `raw_output` and document bodies inside PostgreSQL will
  need a policy eventually.

## Alternatives Considered

### Option A - Kafka (or another broker) between pipeline stages

- Pros: decoupling, replay, natural fan-out to future delivery channels.
- Cons: substantial operational cost; no throughput requirement anywhere near
  justifying it; replay is already achievable via immutable Documents plus LLM
  run records.
- Reason rejected: explicit non-goal (Vision section 18), deferred to post-MVP
  track 7.

### Option B - Polyglot persistence (PostgreSQL + a document store)

- Pros: better ergonomics for unstructured payloads.
- Cons: two stores, cross-store consistency, no atomic "state change + alert".
- Reason rejected: JSONB covers the need; atomicity is worth more than
  ergonomics here.

### Option C - Redis/pubsub or an in-memory queue for alerts

- Pros: instant delivery.
- Cons: alerts become non-durable and separable from their cause, weakening
  audit.
- Reason rejected: the alert feed is an auditable record, not a transient
  notification.

## Follow-up

- Decide hosting/deployment target and whether API and worker share a process
  (**open**).
- Decide migration tooling.
- Decide whether narrative candidate matching requires a vector extension - if
  so, that is a separate ADR, since it changes the database requirement.

## Related

- ADR-0004 (alerts generated inside the processing cycle)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` sections 2, 8, 11
