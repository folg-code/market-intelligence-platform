# ADR-0014 - pgvector in scope for MVP: embedding-based narrative candidate matching

Status: Accepted - Amends ADR-0005 (does not supersede it)
Date: 2026-08-17
Owners: architect
Approved by:

## Context

`DOMAIN_MODEL.md` section 8 named narrative candidate matching - "does this
event belong to an existing `canonical_key`, or does it justify a new
narrative?" - as **the single largest modelling risk**, and the Roadmap calls
Phase 4 the make-or-break phase. ADR-0005's follow-up explicitly deferred the
question: "decide whether narrative candidate matching requires a vector
extension - if so, that is a separate ADR, since it changes the database
requirement."

The naive alternative is to hand the LLM the full list of existing
`canonical_key`s on every candidate and ask it to pick. That degrades in a
predictable way: as the key registry grows, the prompt grows, cost grows, and
recall falls exactly when the system starts having enough history to be useful.
The failure mode is fragmentation - the same interpretation recurring under a
new key - which directly breaks the Vision's continuity promise and ADR-0001's
durable identity.

The human owner has decided not to defer this: embedding-based matching is in
scope from the MVP.

## Decision

- **The `pgvector` extension is in scope for MVP**, enabled inside the same
  PostgreSQL instance that ADR-0005 established as the single system of record.
- **Narrative candidate matching is a two-stage process:**
  1. **Retrieve** - embedding similarity over stored narrative identity
     embeddings returns a small set of plausible existing narratives
     (top-k, above a similarity floor).
  2. **Decide** - the LLM judges the retrieved shortlist against the
     three-condition assignment rule (same economic mechanism, similar
     instrument exposure, updates the same market interpretation), and the
     deterministic validation layer (ADR-0002) turns that judgement into
     `accepted` / `proposed` / `rejected`.
- **Similarity never decides identity.** A vector score may narrow the field and
  may block a match (below the floor), but it may never on its own create,
  assign, or rename a narrative. Narrative identity remains the semantic
  `canonical_key` of ADR-0001; the embedding is a derived retrieval index, not
  the identity.
- **Embeddings are recomputable derived data.** They are versioned with the
  model that produced them, and a model change means a re-embedding pass, never
  a data migration of domain meaning. Losing the embedding column costs a
  rebuild, not information.
- **No separate vector database service, no separate search cluster.**

### Why an extension is compatible with ADR-0005's "single store" principle

ADR-0005's decision is about **components and consistency boundaries**, not
about a list of permitted PostgreSQL features. Its stated benefits are: one
backup, one migration path, one transaction boundary, and the ability to write
a state change and its consequences atomically.

- `pgvector` is loaded into the *same* PostgreSQL instance. It adds a column
  type and index types - not a process, not a port, not a network hop, not a
  second thing to deploy, monitor, or back up.
- Embeddings are written in the **same transaction** as the narrative row they
  describe, so the store cannot drift out of sync with itself.
- `pg_dump` of that database still contains everything (the extension itself is
  a prerequisite of the image, exactly like the PostgreSQL version is).

A standalone vector database would have broken all of that: a second service to
run and back up, a cross-store consistency problem with no shared transaction,
and a new failure mode where a narrative exists but its vector does not (or
vice versa). That is the distinction - **ADR-0005 forbids additional
infrastructure components, not additional capabilities of the one component it
chose.** Only the required extension list changes: `pgvector` joins whatever
else the schema needs.

## Consequences

### Positive

- Narrative matching stays viable as the key registry grows: prompt size stays
  bounded by top-k, not by the number of narratives ever created.
- Directly attacks the highest-risk phase early, with the storage shape in place
  from Phase 1 rather than retrofitted during Phase 4.
- Retrieval is auditable: the candidate shortlist and its scores are recordable
  alongside the `LLMRun` (ADR-0007), so "why was this event matched here?"
  includes "and what else was considered".
- Same backup, same migrations, same transaction as everything else.

### Negative

- **A new hard infrastructure prerequisite:** the PostgreSQL image must ship
  pgvector, and any host or managed provider must support it (constrains
  ADR-0013's alternatives).
- An **embedding model becomes a second model dependency** with its own version,
  cost/latency profile, and re-embedding burden. Anthropic does not provide an
  embeddings API, so the embedding source is necessarily a different vendor or a
  local model - see Follow-up; this is **open** and needs a human decision
  before Phase 4.
- Similarity thresholds are tuning parameters with a real failure mode in each
  direction: too high fragments narratives, too low over-merges distinct ones.
  Both are expensive to detect after the fact.
- Extra schema surface (vector column, index, embedding version) plus an index
  maintenance concern as the table grows.

### Neutral / Trade-offs

- Index choice (exact scan vs HNSW/IVFFlat) is deliberately deferred: at MVP
  narrative counts an exact scan is fine, and an index can be added later
  without changing the query.
- Embedding dimension is fixed by the chosen model and is therefore part of the
  migration - changing models later means a column change plus a re-embedding
  pass. Acceptable for derived data.
- The same mechanism may later help syndication/independence detection
  (`DOMAIN_MODEL.md` section 8), but that is not decided here.

## Alternatives Considered

### Option A - Defer embeddings; LLM-only matching against the full key registry (the previous plan)

- Pros: no new extension, no embedding model, simplest Phase 1 schema.
- Cons: cost and recall degrade with registry size; the degradation is gradual
  and shows up as narrative fragmentation, which is the exact product failure
  the Vision is built to avoid.
- Reason rejected: the human owner chose to address the largest modelling risk
  now rather than after it has produced bad data.

### Option B - A standalone vector database (Qdrant / Weaviate / Chroma as a service)

- Pros: purpose-built, richer filtering and index options at scale.
- Cons: a second service, a second backup, cross-store consistency with no
  shared transaction, and a genuine violation of ADR-0005's component decision.
- Reason rejected: gains only matter at scale this system explicitly refuses to
  target; costs land immediately.

### Option C - Lexical/trigram similarity in PostgreSQL (`pg_trgm`, full-text search)

- Pros: already available, no embedding model at all.
- Cons: matches wording, not meaning - and the whole point of a `canonical_key`
  is that the same interpretation recurs in different words.
- Reason rejected: solves the wrong problem; would produce confident, wrong
  matches.

### Option D - Embeddings computed and held in application memory

- Pros: no extension.
- Cons: rebuilt on every restart, not queryable, not backed up, not consistent
  with the narrative rows.
- Reason rejected: derived data still deserves to live with the data it derives
  from.

## Follow-up

- **Open (needs a human decision before Phase 4):** the embedding model source.
  Anthropic offers no embeddings API, so the realistic options are a locally-run
  open-weight model (no vendor, no per-token cost, one more container-side
  dependency) or a second paid API. A new paid dependency requires explicit
  human approval regardless of size (`governance`) - it is deliberately not
  chosen here.
- Define what text is embedded for a narrative's identity (canonical key +
  economic mechanism + market interpretation is the working proposal) and for an
  incoming candidate - settle during Phase 4 design, not Phase 1.
- Set and record the top-k and similarity floor as configuration, and log the
  retrieved shortlist with each matching `LLMRun`.
- Add the pgvector requirement to the Docker Compose database image (Sprint 001).

## Related

- ADR-0005 (single PostgreSQL store - **amended by this ADR**: extension list
  only)
- ADR-0001 (semantic `canonical_key` remains the narrative identity)
- ADR-0002 (the validation layer still finalizes every match)
- ADR-0007 (retrieval shortlist recorded with the LLM run)
- ADR-0013 (database image must ship pgvector)
- `docs/vision/DOMAIN_MODEL.md` sections 3, 8
