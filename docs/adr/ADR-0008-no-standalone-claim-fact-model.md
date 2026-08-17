# ADR-0008 - Facts and claims stay embedded in the Event extraction result; no standalone Claim/Fact graph

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The product requires epistemic separation between what a document states as
observed fact and what a source asserts or interprets. The fully general
solution is a provenance graph with first-class Claim and Fact entities, each
linked to sources, supporting/contradicting relations, and confidence.

Vision section 5 states that for MVP, facts and claims remain embedded in the
event extraction result rather than becoming full standalone tables - "this
preserves epistemic separation without overbuilding a full claim graph".
Section 11 and section 18 repeat the exclusion.

## Decision

- The `Event` entity carries `extracted_facts` and `source_claims` as
  **structured, separate fields inside the extraction result**. They are never
  merged into one list, and a claim is never promoted to a fact by the
  extractor.
- **No standalone `Claim` or `Fact` entity, table, or graph exists in MVP.**
- Evidence references in EvidencePack and NarrativeInstrumentImpact point at
  **Documents and Events** (and at facts within an event's extraction result),
  not at independent claim nodes.
- The structured shape of `extracted_facts` / `source_claims` is versioned
  (`output_schema_version`, ADR-0007) so that a later extraction to standalone
  entities is a migration, not a re-derivation from raw text.

## Consequences

### Positive

- Removes the single largest source of over-engineering from the MVP: the claim
  graph and its resolution/contradiction machinery.
- Epistemic separation - the property the product actually needs - is preserved
  at negligible cost.
- Traceability still terminates at an immutable Document.

### Negative

- The same real-world fact asserted in two Events is duplicated; deduplication
  and cross-event contradiction detection are not possible in general.
- `contradiction_signals` on a Narrative will be coarse (narrative-level rather
  than claim-level).
- Query patterns like "every source that asserted X" are not directly supported.

### Neutral / Trade-offs

- Keeping the embedded structure well-typed and versioned is what preserves the
  option to promote it later; unstructured free text would forfeit that.
- Promoting to standalone entities post-MVP would require a superseding ADR.

## Alternatives Considered

### Option A - Full Claim/Fact provenance graph from the start

- Pros: proper deduplication, claim-level contradiction detection, richest
  provenance.
- Cons: large build cost, requires claim identity resolution (an unsolved
  problem of its own), delays the first vertical slice substantially.
- Reason rejected: explicit non-goal (Vision sections 5, 11, 18).

### Option B - One undifferentiated `statements` list per Event

- Pros: simplest possible extraction schema.
- Cons: destroys the fact/claim distinction that the trust rules depend on.
- Reason rejected: contradicts Vision section 9's required epistemic
  categories.

### Option C - Facts as a standalone table, claims embedded

- Pros: partial deduplication of the most reusable half.
- Cons: asymmetric model with most of the identity-resolution cost and only part
  of the benefit.
- Reason rejected: half a claim graph is the worst of both.

## Follow-up

- Define the versioned schema for `extracted_facts` and `source_claims`,
  including per-item source attribution and epistemic category.
- Revisit post-MVP if contradiction detection proves too coarse at the narrative
  level.

## Related

- ADR-0003 (EvidencePack references Documents/Events)
- ADR-0007 (schema versioning of extraction output)
- `docs/vision/DOMAIN_MODEL.md` (Event)
