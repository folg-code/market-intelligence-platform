# Architecture Decision Records

An index of architectural decisions. Each row links to one ADR.

| ADR | Title | Status |
|---|---|---|
| [ADR-0001](ADR-0001-semantic-narrative-identity.md) | Narrative identity is a semantic `canonical_key`, not a cluster hash | Accepted |
| [ADR-0002](ADR-0002-llm-candidate-validation-layer.md) | LLM outputs are candidates behind a deterministic validation layer | Accepted |
| [ADR-0003](ADR-0003-mandatory-evidencepack.md) | Every material narrative carries a versioned EvidencePack with independent-source counting | Accepted |
| [ADR-0004](ADR-0004-single-five-minute-cadence.md) | One 5-minute processing cycle; no multi-cadence scheduling in MVP | Accepted |
| [ADR-0005](ADR-0005-postgresql-fastapi-alerting.md) | PostgreSQL as the single store and FastAPI as the alert/read path; no message broker | Accepted - amended by ADR-0014 |
| [ADR-0006](ADR-0006-instrument-impact-over-sentiment.md) | Explicit NarrativeInstrumentImpact replaces a generic sentiment score | Accepted |
| [ADR-0007](ADR-0007-llm-run-audit-record.md) | Every material LLM run is persisted as an append-only audit record with input references | Accepted |
| [ADR-0008](ADR-0008-no-standalone-claim-fact-model.md) | Facts and claims stay embedded in the Event extraction result; no Claim/Fact graph | Accepted |
| [ADR-0009](ADR-0009-override-states-and-audit.md) | Three-level override state with `user_locked` protection, and an append-only human audit trail | Accepted |
| [ADR-0010](ADR-0010-anthropic-claude-tiered-models.md) | Anthropic Claude as the LLM provider, with tiered model selection (Haiku / Sonnet / Opus) | Accepted |
| [ADR-0011](ADR-0011-in-process-apscheduler.md) | In-process APScheduler drives the 5-minute cycle; no worker or broker process | Accepted |
| [ADR-0012](ADR-0012-server-rendered-dashboard-jinja-htmx.md) | Server-rendered dashboard: FastAPI + Jinja2 + HTMX; SPA is a staged later step | Accepted |
| [ADR-0013](ADR-0013-single-host-docker-compose-deployment.md) | Deployment target: local machine or a single VPS via Docker Compose | Accepted |
| [ADR-0014](ADR-0014-pgvector-for-narrative-candidate-matching.md) | pgvector in scope for MVP: embedding-based narrative candidate matching (amends ADR-0005) | Accepted |

Statuses: `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, `Rejected`.

Amendment note: ADR-0014 **amends** ADR-0005 rather than superseding it. Every
decision in ADR-0005 (single PostgreSQL store, alerts as rows, FastAPI read
path, polling, no broker) stands unchanged; ADR-0014 only adds the `pgvector`
extension to the same instance. ADR-0005's text is deliberately left untouched,
per the `adr` skill.

## Decisions still open (need a human decision, then an ADR)

- **Embedding model source** for narrative candidate matching (ADR-0014
  follow-up). Anthropic provides no embeddings API; a local open-weight model or
  a second paid API are the realistic options. A paid dependency requires
  explicit human approval.
- **Dashboard access protection** once the deployment is reachable beyond
  localhost (ADR-0013 follow-up).
- **Retention policy** for document bodies and LLM `raw_output` (ADR-0005,
  ADR-0013 follow-ups).
- **Monthly LLM cost ceiling** (ADR-0010 follow-up).

For the ADR format itself, see the `adr` skill.
