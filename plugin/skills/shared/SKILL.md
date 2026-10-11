---
name: shared
description: STATE.md conventions and how to run the harness's verification commands. Shared by planner, builder and reviewer.
---

# cairn:shared

## STATE.md

A task folder's `STATE.md` has two parts. **Frontmatter** is the state read on resume: scope record, `key_info`, `flags`. Fields stay under 200 chars, the block under 1,024 B (`tools/budget.py` enforces both). `key_info` holds current facts and the next step, overwritten as work moves. Between a finished doc and the user's go-ahead it reads `awaiting requirements approval` (`cairn:scope`) or `awaiting plan approval` (`planner`); approval overwrites it with `approved` plus the next step (`cairn:scope`'s reuse check needs it). `flags` only grows, never pruned: a decision log, not a to-do list. The final step asks one consolidated question. There is no `phase` field: the stage follows from what exists (first match: has sub-tasks -> parent tasks until all are done, then done; merged PR or `key_info` done -> done; `key_info` blocked -> blocked; `awaiting … approval` -> awaiting approval; a `review` folder -> in review; no `PLAN.md`, or a `research` folder -> scoping; `key_info` names review -> in review; fresh heartbeat or plan not merely `approved` -> building; else planned). Merged: `gh pr list --head <folder-name> --state merged --json number -q 'length'`; else `key_info` decides. **The body** below the closing `---` is an append-only log, one line per event, `YYYY-MM-DD HH:MM:` UTC (`date -u`), never edited or read on resume; open it to explain.

## Task folder

`docs/tasks/YYYY-MM-DD-HHMM-<kind>-slug/` (kinds per `cairn:scope`'s Escalated path), holding `REQUIREMENTS.md` and `STATE.md` — a `review` folder has `DRAFT.md` in place of requirements, per `review-pr`'s `reference/draft-template.md`; `PLAN.md` follows requirements. Working outputs (briefs, mockups, findings) sit loose in the same folder, or in a named subfolder when several cluster. A task too big for one PR splits into numbered sub-task folders (`01-<kind>-slug/`) inside it, each with its own `REQUIREMENTS.md`, `STATE.md`, branch and restated `out_of_scope`; only that sub-task's session writes them. A follow-on goal sourced from a doc in an existing folder nests there as its next sub-task, not a new top-level folder (a doc inside a sub-task nests inside it), per `cairn:scope` step 0. Sub-tasks run in parallel unless one names `depends_on`. Without worktree isolation (single-repo projects) they share one tree, where files touched only by convention (`plugin.json`, `CHANGELOG.md`) collide unlisted in any `paths`; give one sub-task sole ownership of that bump via `depends_on` on the rest.

A parent with sub-tasks also gets `EPIC.md`, per `reference/epic.md`.

## Running verification

Read `workflow.md`'s `## Gates` section and `environment.md`'s typed preconditions from the already-resolved harness. Run each via `Bash`. Failure semantics are uniform: a check whose command can't run counts as failed, and a line that can't be parsed also counts as failed — no silent-skip tier. A `[blocking]` failure stops the task; a `[warning]` failure doesn't.

Also measure the active task's `STATE.md` frontmatter — its own task folder, not `source` (which may point elsewhere, e.g. a standalone `docs/requirements/*.md`) — with `awk '{print} NR>1&&/^---$/{exit}' STATE.md | wc -c`, which counts from the opening `---` through the closing one, or the whole file if there is no closing one. Over 1,024 B counts as a `[warning]` failure: name the file and its size, do not stop the task.

## Reference

| File | Load when |
|---|---|
| reference/security-checklist.md | Reviewing a diff — check it against these categories alongside whatever the review already covers. |
| reference/fix-lanes.md | Tagging a diff review's own reuse/simplification/efficiency findings, for human triage. |
| reference/epic.md | Creating sub-tasks, or moving one to its next stage. |
| reference/marker-task.md | A `SubagentStart` hook named your marker file and you hold a sub-task folder. |
