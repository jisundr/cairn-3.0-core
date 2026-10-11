# docs

Index of this repo's own documentation — for developing cairn, not for a consuming project's `.harness/`.

| File | What it is |
|---|---|
| [`REGISTRY.md`](REGISTRY.md) | Justification for every tool an agent's frontmatter grants. Checked by `tools/budget.py`, never loaded by the model. |
| [`BUDGET.md`](BUDGET.md) | Generated size/load-class report for every budgeted artifact. Regenerate with `python tools/budget.py --report`. |
| [`AI_TIPS.md`](AI_TIPS.md) | Notes from experience working with AI coding agents — the practices this repo's own discipline is built on. |
| [`PRODUCT.md`](PRODUCT.md) | cairn's own product doc — users, positioning, brand commitments, evidence. Written/updated by impeccable's `init` (`<!-- impeccable:product-schema -->`); mission-control is mentioned only as one shipped feature, not the doc's subject. |
| [`DESIGN.md`](DESIGN.md) | The mission-control dashboard's design system (React/Tailwind app at `plugin/mission-control/frontend/src`) — carries the landing page's Lockfile world (`marketing/DESIGN-landing.md`) into the live dashboard. Stays flat in `docs/` (not a subfolder): impeccable's own discovery (`context.mjs`) only finds `PRODUCT.md`/`DESIGN.md` directly in `docs/`, not nested. |
| [`marketing/`](marketing/) | The public GitHub Pages landing page: `DESIGN-landing.md` (design system), `index.html` (source), `assets/` (images). Deployed by `.github/workflows/pages.yml` on push, not the classic branch-source method. |
| [`portfolio/`](portfolio/) | External-evaluation material: `PORTFOLIO.md` (case study) and `INTERVIEW-STORIES.md` (STAR narratives). |

## `specs/`

Gitignored scratch (`YYYY-MM-DD-topic.md`) — design notes written before a non-trivial change, local only. Absent on a fresh clone.

## `tasks/`

Gitignored (`docs/tasks/*`) — a `STATE.md` and `REQUIREMENTS.md` per escalated task, `docs/tasks/YYYY-MM-DD-HHMM-<kind>-slug/` (`<kind>` is `research`, `build`, or `review`), written by `cairn:scope`/`planner` and never committed; a `review` folder holds `review-pr`'s `DRAFT.md` instead. `_template/` and `.gitkeep` are the two tracked exceptions: `_template/` is the reference for a task's own files — including `DRAFT.md` for `review` folders — copied in by `/cairn-setup`.
