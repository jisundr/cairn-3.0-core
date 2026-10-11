---
name: scope
description: Resolves scope when cairn:start's checklist fires; interviews only if vague, decomposes only if multi-area.
---

# cairn:scope

Turn the request into a scope record — most of the time this needs no interview.

## Default flow

0. If the request points at an existing doc — `docs/requirements/*.md`, or any doc inside a `docs/tasks/*/` folder (its `REQUIREMENTS.md`, a `findings.md`, a `comparison.md`) — rather than describing the work directly, read it first: `goal` and `done_when` come from what the request itself asks for, else the doc's Goals and Success criteria, else its folder's `goal` and `done_when`; `paths` from whatever files or areas it names, and record its path as `source`. For a doc inside `docs/tasks/*/`: if that folder's stage isn't done (per `cairn:shared`) and the goal fits its `goal` and `out_of_scope`, that folder is the task folder. Otherwise the goal becomes its next numbered sub-task, `0N-<kind>-slug/` (N = highest existing number + 1), per `reference/decomposition.md` — never a new top-level folder. A doc inside a sub-task folder applies this to that sub-task, so new work nests one level deeper. A sub-task that follows the enclosing folder's own work records `depends_on: parent`. No such doc → skip to 1.
1. From the request and conversation so far, name: `goal` (one sentence), `paths` (dirs or globs), `done_when` (checkable condition), `out_of_scope` (explicit exclusions — omit if none).
2. Apply `cairn:start`'s escalation trigger to set `path: default` or `path: escalated`. If the call is genuinely unclear — it could plausibly read as one submodule or several, or "two sentences" would mean dropping something material — ask via `AskUserQuestion` instead of guessing.
3. State the resolved record back in one line and continue. A resolution that produces no new information costs one sentence, not an interview.

```yaml
goal: <one sentence>
paths: [<dirs or globs>]
done_when: <checkable condition>
out_of_scope: [<explicit exclusions>]
source: <requirements doc it was resolved from, if any>
path: default | escalated
```

## Escalated path

Name the folder `docs/tasks/YYYY-MM-DD-HHMM-<kind>-slug/`: the current local date and time, a `<kind>`, then a short kebab-case slug from `goal` (e.g. `2026-09-22-0600-build-add-oauth-login`). `<kind>` is `research` (a question, a brainstorm, or digesting an external source — no code implied), `build` (requirements → plan → build → PR), or `review` (a PR/MR review thread, named and created by `review-pr`, not here). It records how the thread started and is never renamed. Create it with two standard files. `STATE.md` is the record above as frontmatter, per `cairn:shared`. At that same point — folder created, or an existing one bound per step 0 — write the session's task pointer `~/.claude/cairn/active/$CLAUDE_CODE_SESSION_ID.json` via `Bash` (creating the `active/` directory first if needed): `{"project": "<cwd>", "task": "<folder path relative to cwd>"}`; skip silently if that env var is empty. Subagent hooks read it to name the task; it does not itself mark the card active. `REQUIREMENTS.md` is reused only if the folder already has one and it's approved (`key_info` says so); otherwise write or finish it per `reference/requirements-approval.md` — the full `cairn:requirements` shape, groomed and approved before continuing. Default path: the record stays in the main thread; nothing is written to disk.

## Reference

| File | Load when |
|---|---|
| reference/vague-request.md | You cannot name `goal`, `paths`, or `done_when` without guessing. |
| reference/decomposition.md | The request spans more than one submodule, or implies more than about three discrete actionables. |
| reference/requirements-approval.md | Escalated path, writing or finishing `REQUIREMENTS.md`. |
