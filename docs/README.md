# Documentation map

| Path | What lives there | Durability |
|---|---|---|
| `MVP_Vision_Architecture_Decisions.md` | Historical discovery record - the original combined vision + architecture brain-dump. Kept for provenance; superseded as the working source of truth by the files below. | frozen |
| `vision/PRODUCT_VISION.md` | Who the product is for, the problem, principles, non-goals, success definition | durable |
| `vision/ARCHITECTURE_FOUNDATIONS.md` | Tech stack, guiding principles, processing model, LLM boundaries, evidence rules, constraints, quality priorities | durable |
| `vision/DOMAIN_MODEL.md` | Bounded contexts, entities, value objects, aggregates, ubiquitous language | durable |
| `adr/` | One file per binding architectural decision, indexed in `adr/README.md` | append-only |
| `planning/ROADMAP.md` | Phases, dependencies, completion criteria - direction, not a schedule | reviewed per phase |
| `planning/PROJECT_MANAGEMENT.md` | How work is planned, Definition of Ready / Done, sources of truth | rarely changes |
| `planning/CURRENT_STATUS.md` | Snapshot: where the project stands right now | updated at each phase/sprint change |
| `planning/sprints/` | Sprint scope, task breakdown, Wave 0 decisions | per sprint |
| `reference/ARCHITECTURE_OVERVIEW.md` | The component picture as it actually is | updated continuously |
| `reference/MODULE_MAP.md` | Code layout, module responsibilities, dependency direction | updated continuously |
| `reference/WORKFLOWS.md` | How to set up and run things (created in Sprint 001, task S001-T014) | updated continuously |

Also at the repo root: `CLAUDE.md` - project-specific coding conventions, loaded
automatically in every session.

Approval state: everything under `vision/`, all ADRs, `ROADMAP.md`, and
`sprints/SPRINT_001.md` were approved by the user in-conversation on
2026-08-17 (see `planning/CURRENT_STATUS.md` section 6). Documents under
`reference/` are descriptive and need no approval.
