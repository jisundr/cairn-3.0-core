# STATE.md frontmatter, schema 1

The contract for the frontmatter of a task folder's `STATE.md`. It is the one file other tools read to learn what a task is and where it stands. The executable form is `tools/state_schema.py`; its tests pin this document to `mission-control/tasks.py` and `tools/budget.py`.

## Scope

- Covers the frontmatter block (between the opening and closing `---`) of `docs/tasks/<folder>/STATE.md`.
- Does not cover the body below the closing `---`: an append-only log, one dated line per event, never read on resume.
- Does not cover `DRAFT.md`, which a `review` folder holds instead and which has no frontmatter.
- Prose source for the rules below: `plugin/skills/shared/SKILL.md`, `plugin/skills/start/reference/unattended.md` and `plugin/skills/scope/reference/decomposition.md`.

## Grammar

- The file opens with a line `---` and the block closes at the next line `---`. Without both, a reader sees no frontmatter.
- Each line is a flat `key: value`. Keys match `[A-Za-z_][A-Za-z0-9_]*`. There is no nesting and no YAML anchors.
- A scalar may be wrapped in one pair of matching single or double quotes; the quotes are stripped.
- A list is a flow list on one line, `[a, b]`, or a block list, the key with an empty value followed by `- item` lines. Commas inside quoted items do not split. `[]` is the empty list.
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
| `depends_on` | list | no | Sub-tasks only: sibling numbers such as `01`, or `parent` for work that follows the enclosing folder's own scope. |
| `key_info` | string | yes | Current facts and the next step, overwritten as work moves. |
| `flags` | list | no | Decision log. Only grows, never pruned. |

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

A STATE.md written under cairn 2.0 validates unchanged: no `schema` key reads as 1, and only `goal` and `key_info` are required. No rewrite is needed. The gaps, none of them failures:

- `depends_on` was used in practice before it was documented here; it is now a listed optional field.
- `key_info` was free-form; the reserved markers above describe the strings tools already matched.
- Files lack `schema`. Optional edit: add `schema: 1` as the first key. Nothing breaks if it is left out.

A file that is missing `goal` or `key_info`, has an unclosed frontmatter block, or is over 1,024 bytes was already outside the 2.0 rules and does not validate. Fix it by adding the missing field, closing the block with `---`, or trimming the fields.

## Reference reader

```
python tools/state_schema.py PATH...
```

`PATH` is a `STATE.md` or a directory searched for `STATE.md` files (folders named `_template` are skipped unless named directly). Exit 0 means no errors, 1 means at least one error. The same module exposes `parse(text)` and `validate(text, name)` for callers that want findings as data.
