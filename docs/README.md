# docs

Index of this repo's own documentation — for developing cairn, not for a consuming project's `.harness/`.

| File | What it is |
|---|---|
| [`REGISTRY.md`](REGISTRY.md) | Justification for every tool an agent's frontmatter grants. Checked by `tools/budget.py`, never loaded by the model. |
| [`BUDGET.md`](BUDGET.md) | Generated size/load-class report for every budgeted artifact. Regenerate with `python tools/budget.py --report`. |
| [`AI_TIPS.md`](AI_TIPS.md) | Notes from experience working with AI coding agents — the practices this repo's own discipline is built on. |
| [`PRODUCT.md`](PRODUCT.md) | cairn's own product doc — users, positioning, brand commitments, evidence. Written/updated by impeccable's `init` (`<!-- impeccable:product-schema -->`); mission-control is mentioned only as one shipped feature, not the doc's subject. |
| [`DESIGN.md`](DESIGN.md) | The mission-control dashboard's design system (React/Tailwind app at `plugin/mission-control/frontend/src`). Stays flat in `docs/` (not a subfolder): impeccable's own discovery (`context.mjs`) only finds `PRODUCT.md`/`DESIGN.md` directly in `docs/`, not nested. |
| [`skill-review.md`](skill-review.md) | The 3.0 review of every carried-over skill against the budget gate: size, load class, verdict, reason. |
| [`schemas/`](schemas/) | Published contracts other tools read. `state-v1.md` is the STATE.md frontmatter schema; `tools/state_schema.py` validates against it. `tasks-v1.md` is the `.cairn/export/tasks.json` schema core writes for companion plugins; `plugin/skills/task-assets/assets/tasks-export.py` writes it, tested by `tools/test_tasks_export.py`. |
| [`../plugin/skills/task-assets/assets/rule-format.md`](../plugin/skills/task-assets/assets/rule-format.md) | The rule format: `evidence:` and `applies when:` annotations, legacy rules, how doctor and `--select` read them. Single source, shipped in the plugin; `plugin/skills/task-assets/assets/rules-check.py` is its checker, tested by `tools/test_rules_check.py`. |
| [`../plugin/skills/task-assets/assets/proposals.md`](../plugin/skills/task-assets/assets/proposals.md) | Queued rule proposals: the `.cairn/proposals/` file contract and the review steps `/cairn-retro` follows. `proposals.py` beside it records, lists, applies and drops; tested by `tools/test_proposals.py`. |

## `specs/`

Gitignored scratch (`YYYY-MM-DD-topic.md`) — design notes written before a non-trivial change, local only. Absent on a fresh clone.

## `tasks/`

Gitignored (`docs/tasks/*`) — a `STATE.md` and `REQUIREMENTS.md` per escalated task, `docs/tasks/YYYY-MM-DD-HHMM-<kind>-slug/` (`<kind>` is `research`, `build`, or `review`), written by `cairn:scope`/`planner` and never committed; a `review` folder holds `review-pr`'s `DRAFT.md` instead. `_template/` and `.gitkeep` are the two tracked exceptions: `_template/` is the reference for a task's own files — including `DRAFT.md` for `review` folders — copied in by `/cairn-setup`.
