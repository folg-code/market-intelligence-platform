# ADR-0009 - Three-level override state with `user_locked` protection, and an append-only human audit trail

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The system continuously recomputes narrative state from new evidence. Without a
protection model, any human correction is overwritten by the next processing
cycle - and the Vision's quality gate "manually rejected mappings do not
silently return" fails.

The naive protection model (a boolean "locked" flag that freezes the object) is
wrong for this product: Vision section 17 states that override must **not** mean
"stop observing the world".

## Decision

**Override states** (on Narratives and on NarrativeEvent assignments):

- `none` - the system may change the decision automatically.
- `user_preferred` - the user's value is preferred; automated changes require a
  stronger justification and are surfaced rather than applied silently.
- `user_locked` - the system **must not** automatically change the protected
  domain decision.

**Binding semantics:**

- Under `user_locked`, the pipeline keeps ingesting, extracting, scoring, and
  **alerting**. What changes is only the *write path*: an automated conclusion
  affecting the protected decision is persisted as a `proposed` candidate
  (ADR-0002), never as a silent update.
- Protection is scoped to the **specific decision** overridden (e.g. one
  rejected event-to-narrative assignment), not to the whole narrative.
- A rejected assignment does not silently return; a later automated
  re-assignment surfaces as a proposal.
- Changing a `user_locked` decision is Tier C - LLM-initiated changes are
  forbidden outright.

**MVP human controls:** watch, mute, rename display title, mark irrelevant,
mark invalid, reject event assignment, restore/undo override. Post-MVP: merge,
split, edit relations, change `canonical_key`, episode management.

**Audit:** every human correction writes an append-only `AuditEntry` with
`actor`, `action`, `target_id`, `previous_value`, `new_value`, `timestamp`,
`reason`. `previous_value` records the state actually replaced. Undo/restore is
itself an audited action, not a deletion of history.

## Consequences

### Positive

- The user's corrections are durable, which is what makes the system trustable
  over weeks rather than minutes.
- The system remains honest: it still tells the user when evidence contradicts
  their override, instead of going quiet.
- Full reconstruction of "who changed what, when, and why" - the human-side
  counterpart to ADR-0007.

### Negative

- Every automated write path must consult override state - a cross-cutting
  check that is easy to forget in a new code path. Needs to be enforced at a
  single choke point rather than sprinkled.
- Proposals accumulate if the user ignores them; needs a review surface and
  possibly an expiry policy.
- Three states are more nuance than a boolean and need clear UI language.

### Neutral / Trade-offs

- `user_preferred` semantics ("stronger justification") require concrete
  thresholds - currently undefined and deliberately conservative until measured.
- Audit storage grows, but human corrections are low-volume by nature.

## Alternatives Considered

### Option A - Boolean locked flag that freezes the object

- Pros: trivially simple.
- Cons: freezing stops observation and alerting on the locked narrative -
  explicitly forbidden by Vision section 17.
- Reason rejected: contradicts the stated override semantics.

### Option B - Last-write-wins, no override state

- Pros: no protection logic at all.
- Cons: the next cycle undoes every human correction; the Vision quality gate
  fails outright.
- Reason rejected: fatal to the product's trust model.

### Option C - Every automated change becomes a proposal (human approves all)

- Pros: maximum user control.
- Cons: turns a 5-minute automated pipeline into a manual review queue.
- Reason rejected: contradicts Vision section 8 (most decisions should be
  auto-accepted by deterministic rules).

## Follow-up

- Define the single choke point through which all automated writes consult
  override state.
- Define what "stronger justification" means for `user_preferred`.
- Define the proposal review surface in the dashboard and any expiry policy.

## Related

- ADR-0002 (proposals are the candidate mechanism)
- ADR-0007 (LLM run audit - the machine-side counterpart)
- `docs/vision/DOMAIN_MODEL.md` section 6
