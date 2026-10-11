# STATE.md frontmatter, schema 1

The contract for the frontmatter of a task folder's `STATE.md`. It is the one file other tools read to learn what a task is and where it stands. The executable form is `tools/state_schema.py`; its tests pin this document to `mission-control/tasks.py` and `tools/budget.py`.

## Scope

- Covers the frontmatter block (between the opening and closing `---`) of `docs/tasks/<folder>/STATE.md`.
- Does not cover the body below the closing `---`: an append-only log, one dated line per event, never read on resume.
- Does not cover `DRAFT.md`, which a `review` folder holds instead and which has no frontmatter.
- Prose source for the rules below: `plugin/skills/shared/SKILL.md`, `plugin/skills/start/reference/unattended.md` and `plugin/skills/scope/reference/decomposition.md`.

## Grammar

- The file opens with a line `---` and the block closes at the next line `---`. Without both, a reader sees no frontmatter.
- Each line is a flat `key: value`. Keys match `[A-Za-z_][A-Za-z0-9_]*`. There is no nesting and no YAML anchors. Nesting is not detected: an indented `key: value` line is read as a top-level key.
- A scalar may be wrapped in one pair of matching single or double quotes; the quotes are stripped.
- A list is a flow list on one line, `[a, b]`, or a block list, the key with an empty value followed by `- item` lines. Commas inside quoted items do not split. `[]` is the empty list. A value wrapped in `[ ]` is always read as a list, so text that merely starts with `[` and ends with `]` becomes a list too.
- A line that fits none of these is ignored by readers, not fatal.
- A key given with an empty value and no list items after it is an empty field; readers may see it as an empty list.

## Fields

| Key | Type | Required | Meaning |
|---|---|---|---|
| `schema` | int | no | Schema version. Absent reads as 1. |
| `goal` | string | yes | One line: what the task achieves. |
| `paths` | list | no | Files or globs in scope. |
| `done_when` | string | no | The observable finish condition. |
| `out_of_scope` | list | no | What the task deliberately excludes. |
| `source` | string | no | Where the request came from: a doc path or reference. |
| `path` | string | no | The route the task took; `escalated` for task folders. |
| `depends_on` | list (scalar deprecated) | no | Sub-tasks only: sibling numbers such as `01`, or `parent` for work that follows the enclosing folder's own scope. |
| `key_info` | string | yes | Current facts and the next step, overwritten as work moves. |
| `flags` | list (scalar deprecated) | no | Decision log. Only grows, never pruned. |

An empty `goal` or `key_info` (`goal:` with nothing after it, or `[]`) is a warning, not an error: the shipped templates carry them empty. A missing one is an error.

Unknown keys are legal. Readers ignore them; the validator reports a warning so a typo is visible.

## Reserved `key_info` markers

Other tools match on `key_info` text, so these strings keep their meaning.

| Marker | Match | Meaning | Read by |
|---|---|---|---|
| `awaiting requirements approval` | substring | A requirements doc waits for the user's go-ahead. | mission-control (awaiting approval column), scope |
| `awaiting plan approval` | substring | A plan waits for the user's go-ahead. | mission-control, planner, scope |
| `approved` | leading word, any case | Approval given; the plan is not started. Followed by the next step. | mission-control (planned vs building), scope reuse check |
| `needs-human` | substring | An unattended run hit a fork it cannot settle; the question follows. | mission-control (needs attention), unattended runs |
| `stalled` | substring | The retry cap was hit without a passing review. | mission-control, unattended runs |
| `done` | whole word, any case (also `close`, `closed`, `complete`) | Finished. | mission-control, triage, resume |
| `blocked` | whole word, any case | Cannot proceed. | mission-control, triage |
| `review` / `reviewer` | whole word, any case | Work is in review. | mission-control, triage |

A `key_info` that starts with `approved` reads as planned until work begins and the builder overwrites it.

## Limits

- Each field stays under 200 characters.
- The frontmatter block stays under 1,024 bytes. `tools/budget.py` warns above 800 bytes and fails above 1,024.
- The validator applies the same figures; its tests compare them to the budget gate so they cannot drift apart.

## Compatibility and change policy

- Adding an optional field keeps `schema: 1`.
- Renaming or removing a field, changing a field's type, or changing what a reserved marker means bumps the version to 2.
- Readers ignore unknown keys. A reader that meets a larger `schema` than it knows reads on a best-effort basis and says so.
- Writers add `schema: 1` as the first key of new files. Both `_template/STATE.md` copies do.

## 2.0 files

A STATE.md written under cairn 2.0 validates unchanged when its frontmatter stays within the 1,024 B cap and it has `goal` and `key_info`: no `schema` key reads as 1, and only those two are required. No rewrite is needed; the forms below produce warnings, never errors.

Real 2.0 files that do not meet that bar get an error. Each has a one-line fix:

- Frontmatter over 1,024 B: trim the long fields, or move detail into the body below the closing `---`.
- No frontmatter (the file does not open with `---`, or the block is never closed): add the opening and closing `---` lines around the `key: value` lines.
- `goal` or `key_info` missing: add the key, with one line of text.

- `depends_on` and `flags` written as a scalar instead of a list. Deprecated. Rewrite to the list form:
  - `depends_on: 03` becomes `depends_on: [03]`
  - `depends_on: 01, 02, 03, 05` (comma-separated) becomes `depends_on: [01, 02, 03, 05]`
  - `depends_on: none` or `depends_on: —` (em dash) becomes `depends_on: []`, or drop the key
  - `flags: some text` becomes `flags: [some text]`
- `depends_on` was used in practice before it was documented here; it is now a listed optional field.
- `key_info` was free-form; the reserved markers above describe the strings tools already matched.
- Files lack `schema`. Optional edit: add `schema: 1` as the first key. Nothing breaks if it is left out.
- Over-long fields and blocks between 800 and 1,024 bytes warn; see Limits.

The errors above are the complete list for a 2.0 file, plus shapes 2.0 did not use: a `schema` that is not a positive integer, `paths`, `out_of_scope` or another non-deprecated list field given as a scalar (write `[a, b]`), and a scalar field given as a non-empty list.

## Reference reader

```
python tools/state_schema.py PATH...
```

`PATH` is a `STATE.md` or a directory searched for `STATE.md` files (folders named `_template` are skipped unless named directly). Exit 0 means no errors, 1 means at least one error, 2 means no `STATE.md` was found or no path was given. The same module exposes `parse(text)` and `validate(text, name)` for callers that want findings as data.
