# ADR-0003 - Every material narrative carries a versioned EvidencePack with independent-source counting

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The product's differentiator is that conclusions are auditable and that
evidential strength is not faked by volume. Vision section 9 states the core
rules; section 19 makes "syndicated articles do not count as independent
evidence" a quality gate; section 5 specifies the EvidencePack fields.

News flow is dominated by syndication: one wire report reproduced across a dozen
outlets. A naive `source_count` would make a single-origin story look
overwhelmingly confirmed.

## Decision

1. **Every material narrative must have exactly one current EvidencePack.** A
   narrative without one may not appear in a Brief, an instrument impact
   assessment, or an alert.
2. **EvidencePack is an immutable, versioned snapshot** (`evidence_version`,
   `generated_at`). Rebuilds create a new version; old versions are retained for
   audit.
3. **`independent_source_count` is computed and stored separately from
   `source_count`,** and it is the count used by downstream confidence and
   validation rules. Documents deriving from one originating report count once.
4. **Every evidence item is traceable** to a Document (directly, or via an Event
   that traces to Documents).
5. **Evidence is partitioned by domain** - official / media / social / market -
   and `market_evidence` is empty in MVP. Empty `market_evidence` forbids
   market-pricing language downstream (enforced by a deterministic
   post-generation check, not by prompt instruction).
6. **Gaps are explicit:** `missing_evidence` and `evidence_gaps` are populated,
   not left null, so uncertainty is visible rather than implied.

## Consequences

### Positive

- Makes the Vision's quality gates mechanically checkable rather than
  aspirational.
- Versioned packs let the system answer "what did we know when we said that?"
- The independent-source rule directly protects against the most common failure
  mode of news-driven systems.

### Negative

- Determining independence is genuinely hard and will be imperfect (wire
  detection, publisher relationships, near-duplicate text).
- Pack rebuild cost on every cycle for every touched narrative; requires
  change-scoped rebuilds rather than full recomputation.
- Storage grows with every version.

### Neutral / Trade-offs

- "Material" needs a definition; it is currently an open question in
  `DOMAIN_MODEL.md` section 8.
- A conservative independence heuristic will understate confirmation - accepted
  deliberately: underclaiming is the correct failure direction for this product.

## Alternatives Considered

### Option A - Compute evidence on the fly at read time

- Pros: no storage, always current.
- Cons: no audit trail of what the system believed at conclusion time;
  expensive and non-reproducible.
- Reason rejected: destroys auditability, the product's primary quality
  attribute.

### Option B - Single `source_count` with a syndication penalty factor

- Pros: much simpler.
- Cons: collapses a structural distinction into a fudge factor; unexplainable to
  the user.
- Reason rejected: Vision section 19 requires independence as a hard gate, not a
  weighting.

### Option C - Full Claim/Fact provenance graph

- Pros: maximum fidelity of provenance.
- Cons: large build cost.
- Reason rejected: explicitly out of scope - see ADR-0008.

## Follow-up

- Choose the independence-detection mechanism (publisher graph, wire/byline
  detection, near-duplicate similarity, or a combination).
- Define "material narrative".
- Define retention for superseded EvidencePack versions.

## Related

- ADR-0002 (validation layer consumes these counts)
- ADR-0008 (facts/claims stay embedded in Event)
- `docs/vision/ARCHITECTURE_FOUNDATIONS.md` section 6
