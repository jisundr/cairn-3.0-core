# Decomposing a request that spans multiple areas

List actionables as things you could start on — "add the login form," not "implementation" or "testing."

Each actionable should be independently nameable: someone reading just its name should know what file or area it touches.

Group by submodule or area when the request spans more than one — that's the same condition that sets `path: escalated` via `cairn:start`'s escalation trigger.

Keep the list short enough to scan. Five to eight items is a signal to fold some together, not to keep splitting further.

The list itself carries no ordering, dependencies, or phase names — that's the escalated path's `planner`, not scope resolution.

When a task is too big for one PR or one context window, make it a parent folder and split it into numbered sub-task folders (`01-<kind>-slug/`, `<kind>` per `cairn:scope`'s Escalated path), each with its own `STATE.md` and `REQUIREMENTS.md`. Sub-tasks run in parallel; add `depends_on` (a sibling's number, or `parent` for work that follows the enclosing folder's own scope) to a sub-task's `STATE.md` only where one truly needs another's result, and fix any shared schema or API in the parent's `REQUIREMENTS.md` first, or make it an earlier sub-task the rest depend on. Compare sibling `paths` before writing anything: two sub-tasks whose paths overlap are merged, or one takes a `depends_on`. Without worktree isolation (no submodules), also treat files touched only by commit convention — `plugin.json`, `CHANGELOG.md` — as an implicit overlap even though no sub-task lists them: give one sub-task, via `depends_on` on the rest, sole ownership of that bump, per `cairn:shared`. Each sub-task restates `out_of_scope` in its own `STATE.md`. Create the parent's `EPIC.md` in the same pass as the first numbered folder, one row per sub-task — see `cairn:shared`'s Task folder section for its shape and who keeps it current. The no-dependencies rule above is for the actionable list inside one task, not for splitting into sub-task folders.

**Sequence heads-up.** Once the sub-task folders and `EPIC.md` are written, and before the first `planner` dispatch, show the user one line per sub-task in run order: each after everything it depends on, ties by number, so order can differ from numbering. Build it from each `depends_on` and the reason the overlap check found; nothing new is written to disk.

```
01 drawer-activity: parallel
02 relative-last-touched: after 01, same TaskDrawer.tsx
06 sequence-heads-up: after 01, plugin.json/CHANGELOG bump chain
05 session-version: after 06, plugin.json/CHANGELOG bump chain
```

No `depends_on` reads `parallel`; otherwise `after NN` (or `after parent`) with the reason: overlapping `paths`, a shared schema or API, or the convention-file bump. It rides the requirements approval that follows the split, per `reference/requirements-approval.md`, so approving the requirements approves the order; a correction edits `depends_on` before any `planner` runs. When a later pass adds, merges or drops a sub-task or edits a `depends_on`, show the refreshed list once, with that change's approval or its report, not before each dispatch. Unattended runs skip it; `EPIC.md` holds the order.

Before dispatching an agent for a sub-task, bind the task pointer to that sub-task's folder — and to the parent's folder for the parent's own scope — per `cairn:start`'s `reference/dispatch-pointer.md`.
