# Project Management

## 1. Purpose

How this project plans, tracks, and closes work. Not a replacement for
architecture documentation, and not an operational task board.

## 2. Planning Hierarchy

```text
Vision -> Roadmap -> Phases -> Sprint -> Tasks / PRs
```

## 3. Sources of Truth

| Area | Source of truth |
|---|---|
| Product direction | `docs/vision/PRODUCT_VISION.md` |
| Architecture direction | `docs/vision/ARCHITECTURE_FOUNDATIONS.md`, `docs/vision/DOMAIN_MODEL.md` |
| Binding decisions | `docs/adr/` |
| Roadmap direction | `docs/planning/ROADMAP.md` |
| Current state | `docs/planning/CURRENT_STATUS.md` |
| Sprint scope and acceptance | `docs/planning/sprints/SPRINT_XXX.md` |
| Operational task status (todo/doing/done) | The Issues/Projects tracker once one exists; until then, the `Status` column in the sprint table is the interim record |
| Problems | `docs/planning/PROBLEM_REGISTRY.md` (created on first entry) |
| Ideas | `docs/planning/IDEA_INBOX.md` (created on first entry) |
| Technical debt | `docs/planning/TECHNICAL_DEBT.md` (created on first entry) |

## 4. Work Categories

`Epic`, `Feature`, `Bug`, `Research`, `Architecture`, `Technical Debt`,
`Documentation`, `Maintenance`.

## 5. Definition of Ready

A task may enter a sprint's Task Breakdown only when all of the following hold:

- [ ] The goal is clear and stated in one sentence.
- [ ] Scope and out-of-scope are described.
- [ ] Acceptance criteria exist and are checkable.
- [ ] Dependencies (on other tasks, on decisions) are known and listed.
- [ ] Relevant documents/ADRs are referenced.
- [ ] Expected tests or validations are described.
- [ ] It is small enough to be one coherent PR (target 100-400 lines of
      meaningful change, per `git-workflow`).

## 6. Definition of Done

- [ ] Acceptance criteria are met.
- [ ] Tests/validations performed proportionally to the risk.
- [ ] Lint, type-check, and tests pass.
- [ ] Documentation and ADRs updated where the change requires it.
- [ ] Known limitations recorded (`TECHNICAL_DEBT.md` / `PROBLEM_REGISTRY.md`).
- [ ] The PR is open against the sprint branch and reviewed - the agent does not
      merge its own PR.

## 7. Sprint Rules

- One sprint, one main goal.
- Scope is bounded and coherent; out of scope is explicit.
- Work moves in vertical slices - a thin complete capability, not an
  architectural layer.
- The sprint document is opened as `Status: Planned` and only a human sets it to
  `Approved`, by checking off the Wave 0 Checklist (`governance`).
- The Review section records what actually happened; it never rewrites the plan.

## 8. Project-specific Rules

1. An implementation may not rely on an ADR whose status is still `Proposed` -
   the reviewer treats that as a Critical finding.
2. A new paid dependency, any change touching secrets, or any production infra
   change requires explicit human approval, regardless of size.
3. Vocabulary drift (`sentiment_score`, "prediction", "signal", "forecast"
   appearing in code) is logged as technical debt, not silently accepted.
