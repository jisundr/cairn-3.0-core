# Archiving closed task folders

Used by `/cairn-triage` step 5, `/cairn-doctor` step 8 and `tasks/setup.md`.

## Setting

Read `- Path:` under `## Archive` in `.harness/workflow.md`. Section or key absent → the default, `docs/tasks/.archived/`. A path that is absolute, contains `..`, or is `docs/tasks/` itself is invalid: no moves are offered, and doctor flags it.

The section, as setup writes it:

```
## Archive
Closed task folders move here from `docs/tasks/` when `/cairn-triage` archives them, each after a yes.
- Path: <dir>/
```

The path keeps its trailing slash.

## Close date

Read from the log body of the folder's `STATE.md`, below the frontmatter: the date of the latest log line containing the whole word `done`, `closed`, `complete` or `merged`, any case. No such line → the last log line's date. No log lines → the folder is not archivable; the folder-name date and file mtime are not used. A parent's close date is the newest across the parent and its sub-task folders.

## Archivable

A top-level `docs/tasks/<name>/` that triage step 3 classed Ready to close, whose close date plus one calendar month is on or before today. Today is `date -u +%F`, not triage's anchor date. When the next month has no matching day, use its last day (Jan 31 → Feb 28 or 29). A parent moves with its sub-tasks; a sub-task folder is not offered on its own.

## Move

1. List the archivable folders with their close dates, plus a count of Ready to close folders left alone because they closed under one month ago.
2. Ask about each folder separately; no answer → no.
3. On a yes: `mkdir -p <archive>`, which also creates the default folder on the first move. If `<archive>/<name>` already exists, skip the folder and say so. Else `mv docs/tasks/<name> <archive>/<name>`.
4. Nothing is renamed, no `STATE.md` is edited, and no git command runs.
5. Report what moved and how to move it back: `mv <archive>/<name> docs/tasks/`.

## Doctor

Print `archive: <path> (configured|default)`, then one of: `missing` when a configured path does not exist, `not created yet` when the default does not exist, `invalid` when the path is invalid.
