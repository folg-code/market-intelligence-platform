# ADR-0012 - Server-rendered dashboard: FastAPI + Jinja2 + HTMX; SPA is a staged later step

Status: Accepted
Date: 2026-08-17
Owners: architect
Approved by:

## Context

The Vision fixes the dashboard's *sections* (section 14: Current Brief, Active
Narratives, NQ/BTC/GOLD Exposure, Material Changes / Alert Feed) and the core
navigation (brief -> narrative -> evidence -> source document), but not the
technology. `ARCHITECTURE_FOUNDATIONS.md` section 13 left this open.

Relevant constraints:

- Single user, one deployment, no auth model beyond protecting the deployment.
- The alert feed **polls**; no push transport in MVP (ADR-0005).
- Explicit UI non-goals: charts, orderflow, heatmaps, settings UI, economic
  calendar UI (Vision section 6).
- The interaction surface is small: read views, navigation drill-down, and a
  handful of override actions (watch, mute, rename, mark irrelevant/invalid,
  reject assignment, undo).
- Introducing a second language and a JS build toolchain into the repo is a
  standing cost paid by every future change, not a one-time setup cost.

## Decision

- **The MVP dashboard is server-rendered: FastAPI + Jinja2 templates, with HTMX
  for partial updates** (alert-feed polling, drill-down panels, override actions
  that swap a fragment rather than reload a page).
- **One application, one language, one process.** No Node build step, no bundler,
  no separate frontend deployment. CSS is hand-written or a single vendored
  stylesheet.
- **Read models are shaped server-side.** Templates render prepared view models;
  they do not contain domain logic (Foundations principle 1).
- **JSON endpoints are written where they are genuinely useful** (e.g. the alert
  feed poll), but a complete public JSON API is *not* a goal of MVP - the HTML
  path is the product surface.
- **A move to React/SPA is the acknowledged upgrade path, explicitly staged for
  later** - not MVP, and not automatically the next step after MVP. The trigger
  is evidence, not a schedule: when dashboard interactivity outgrows what HTMX
  handles comfortably (rich client-side state, heavy filtering/sorting across
  large narrative sets, live charting, drag/drop or multi-panel workspace
  behaviour). That move would get its own ADR superseding this one.

## Consequences

### Positive

- The entire MVP stays one Python codebase - matching the single-process
  deployment (ADR-0011, ADR-0013) and keeping the whole system runnable with one
  command.
- No API-contract maintenance between a backend and a frontend; the read path
  and its rendering evolve together, which suits a phase where the *shape* of a
  narrative view is still being discovered.
- Polling an HTML fragment is the natural fit for a 5-minute cadence and needs
  no client-side state machine.
- Cheap to throw away: the templates are the least valuable artifact in the repo,
  so the eventual SPA migration discards little.

### Negative

- **Rich interactivity has a ceiling.** Anything with substantial client-side
  state becomes awkward in HTMX, and the failure mode is gradual (template and
  fragment sprawl) rather than obvious.
- Server-side rendering couples presentation to the request cycle: a slow query
  or a busy cycle shows up as a slow page, with no client-side skeleton to hide
  it.
- No component model - shared UI pieces are Jinja includes/macros, which offers
  weaker guarantees against duplication than a component framework.
- A future SPA migration will need the JSON API that this decision deliberately
  does not build up front.

### Neutral / Trade-offs

- Keeping view-model construction in a dedicated read-model layer (rather than
  inside templates) is what makes the later SPA migration a re-render rather
  than a rewrite; that layering is a deliberate hedge and is worth its small
  cost now.
- Accessibility and styling remain hand-rolled; acceptable for a single known
  user.

## Alternatives Considered

### Option A - React (or another SPA framework) from the start

- Pros: no migration later; strongest interactivity ceiling; clean API boundary.
- Cons: second language, build toolchain, separate deploy artifact, and an API
  contract to maintain - all before we know what the dashboard should even
  look like; roughly doubles the surface of Phase 7.
- Reason rejected: too much fixed cost for a single-user MVP whose UI non-goals
  exclude nearly everything an SPA is good at. Recorded as the anticipated later
  step instead.

### Option B - Server-rendered templates with no HTMX (full page reloads)

- Pros: simplest possible thing.
- Cons: a polling alert feed that reloads the whole page is genuinely worse to
  use, and override actions would lose scroll position and context.
- Reason rejected: HTMX is a single script tag; the ergonomics gain is large and
  the cost is near zero.

### Option C - Streamlit / Dash / another dashboard framework

- Pros: fastest path to something on screen.
- Cons: fights the Vision's specific layout and drill-down navigation; awkward
  for write actions (overrides) with audit semantics; introduces its own server
  model alongside FastAPI.
- Reason rejected: the dashboard is the product surface, not an internal tool -
  its structure is specified and must be followed exactly.

## Follow-up

- Establish the read-model layer boundary when Phase 7 starts, so templates stay
  logic-free and an SPA migration stays cheap.
- Decide how the deployment is protected (single-user auth / network-level
  restriction) - still **open**, see ADR-0013 follow-up.
- Revisit this ADR when a dashboard requirement genuinely needs client-side
  state; a superseding ADR, not an amendment.

## Related

- ADR-0005 (FastAPI read path, polling, no push transport)
- ADR-0011 (single process hosting both API and scheduler)
- ADR-0013 (single-host Docker Compose deployment)
- `docs/vision/PRODUCT_VISION.md` sections 3, 6
