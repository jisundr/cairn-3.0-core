# tasks.json, schema 1

The contract for `.cairn/export/tasks.json`: the task list, each task's phase, and which sessions worked on it. Core is its only writer. Readers such as cairn-board use it without parsing task folders themselves. The executable form is `plugin/skills/task-assets/assets/tasks-export.py`; `tools/test_tasks_export.py` pins its output to `docs/schemas/state-v1.md` parsing and to `mission-control/tasks.py` column precedence.

## Scope

- Covers `<project>/.cairn/export/tasks.json` and the marker addition below.
- Does not cover `usage.json`, which cairn-meter writes to the same folder and documents in its own repo.
- Does not cover the ledger `.cairn/task-sessions.jsonl`. It is private to core and may change in any release.

## Location and writes

- Path: `<project>/.cairn/export/tasks.json`, UTF-8, one JSON object.
- Written by core's `Stop` hook (`hooks/export-tasks.sh`) in a project whose `CLAUDE.md` carries the cairn marker. The hook runs on every session end, so a reader sees state as of the last finished turn.
- Written atomically (temp file in the same folder, then rename); a reader never sees a partial file. When nothing but `generated` would change, the file is left as it is, so `generated` is the time of the last change, not of the last run.
- `.cairn/` gitignores itself.

## Top level

| Key | Type | Meaning |
|---|---|---|
| `schema` | int | Schema version, `1`. |
| `generated` | string | UTC ISO time, `YYYY-MM-DDTHH:MM:SSZ`. |
| `project` | string | Absolute path of the project root. |
| `tasks` | list | One entry per task folder, ordered by `folder`. |

## Task

| Key | Type | Meaning |
|---|---|---|
| `folder` | string | Project-relative posix path, for example `docs/tasks/2026-10-11-0910-build-x` or `docs/tasks/<parent>/01-build-y`. |
| `parent` | string or null | `folder` of the enclosing task folder, or null for a top-level task. Only the immediate parent. |
| `kind` | string | `build`, `research` or `review`, from the folder name; `build` when the name carries no kind. |
| `goal` | string | `goal` from `STATE.md`; for a `DRAFT.md`-only folder, its first non-empty line without leading `#`. Empty string when absent. |
| `key_info` | string | `key_info` from `STATE.md`; for a `DRAFT.md`-only folder, its last non-empty line. Empty string when absent. |
| `phase` | string | One of `scoping`, `awaiting_approval`, `planned`, `building`, `in_review`, `blocked`, `done`, `parent_tasks`. See below. |
| `needs_attention` | bool | `key_info` contains `needs-human` or `stalled`. |
| `last_log` | string or null | Date, with time when the line has one, of the last dated line in the `STATE.md` log: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`. Null when there is no such line, and always null for a `DRAFT.md`-only folder. |
| `sessions` | list | Sessions that worked on this task, ordered by `started`. |

A session entry is `{session_id, started, ended}`: the session's id and UTC ISO times (`YYYY-MM-DDTHH:MM:SSZ`). A session appears once per task: `started` is its earliest and `ended` its latest recorded time on that task. A session that touched several tasks appears under each. A task nobody recorded has `[]`.

Fields follow `state-v1.md`: the frontmatter grammar, the reserved `key_info` markers and the 200-character field cap are read the same way, and a value is copied as written, not trimmed.

## Phase

Derived from files only, first match wins, the order `cairn:shared` and `mission-control/tasks.py` use:

1. `done`: `key_info` names `done`, `close`, `closed` or `complete` as a whole word.
2. `blocked`: `key_info` names `blocked` as a whole word.
3. `awaiting_approval`: `key_info` contains `awaiting requirements approval` or `awaiting plan approval`.
4. `in_review`: `kind` is `review`.
5. `scoping`: `kind` is `research`, or the folder has no `PLAN.md`.
6. `in_review`: `key_info` names `review` or `reviewer` as a whole word.
7. `building`: `key_info` does not begin with `approved`.
8. `planned`: otherwise.

A folder with sub-tasks overrides the result: `parent_tasks` until every direct child is `done`, then `done`.

Not used, so a reader may add them: a merged-PR check (`gh`), and the active markers in `~/.claude/cairn/active/`. A folder whose PR merged but whose `key_info` does not say so reads as its file-derived phase here.

## Excluded folders

- Any path with a `_template` segment.
- Folders under the configured archive folder: `- Path:` under `## Archive` in `.harness/workflow.md`, default `docs/tasks/.archived/`, validated by the rules in `plugin/skills/task-assets/assets/tasks/archive.md`. An invalid path excludes nothing, and the default does not apply in that case.
- A folder holding neither `STATE.md` nor `DRAFT.md` is not a task.

## Marker addition

Core's subagent markers, `~/.claude/cairn/active/<session_id>--<agent_id>.active`, gain two keys. A marker is now `{project, task, schema, started}`:

| Key | Type | Meaning |
|---|---|---|
| `project`, `task` | string | As before: the project path and the task folder (project-relative). |
| `schema` | int | `1`. |
| `started` | string | UTC ISO time the subagent started. |

Readers ignore unknown keys, and a marker without `schema` or `started` is an older marker, still valid. Presence of the file is still the activity signal, and a marker older than four hours is dead.

## Reader guidance

- **Missing file:** core has not exported for the project yet, or is not installed. Show an empty state that names core; do not fail.
- **Larger `schema` than known:** read best-effort and say so.
- **Cost per task:** sum `cost_usd` over the task's sessions in `usage.json`, matched on `session_id`.
  - A session that appears under several tasks is shown as `shared` for each; its cost is not split.
  - A task with any session whose `cost_usd` is null, or with a session missing from `usage.json`, shows `unknown`.
  - Never show a partial sum as if it were complete.
- **Active:** a task is active when a live marker names it; the export carries no activity flag.

## Compatibility and change policy

- Adding an optional field keeps `schema: 1`.
- Renaming or removing a field, changing a field's type, or changing what a `phase` value means bumps the version to 2.
- Adding a `phase` value is a change in meaning for readers that switch on it; it bumps the version.
- Readers ignore unknown keys.
- Core writes `schema` first in the file.
