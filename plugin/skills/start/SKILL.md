---
name: start
description: Entry point, loaded once per session. Resolves the .harness/ gate, scope, path, and attendance.
---

# cairn:start

## Harness gate

One `Glob .harness/**/*.md` call, once per task; hold the result — never re-glob mid-task.

- **Present** — read what the current step needs, proceed. Skip rules whose `applies when` misses the task's `paths` or kind (`task-assets/assets/rule-format.md`).
- **Partial** — proceed with what's there. A missing individual file skips silently.
- **Absent** — don't proceed with cairn's workflow. Say cairn works from the project's own `.harness/`, and offer `/cairn-setup`, once. Declined: stand down for the session, no asking, no writes. Keep working on the request without cairn.

## Local preferences

Also covered by the glob: `.harness/local/preferences.md`, classified per `/cairn-doctor` (active / ignored-by-ceiling / unrecognised). Dispatch prompts carry only active values, not the file or path. Active `prefer-path` feeds the path choice. Active `model` lines bound each cairn agent's `Agent()` `model` param, not prompt text (a no-op for `subagent_type: "fork"`). Pick from the role's list: most capable for escalated or code-writing work, lightest for small or read-only work; with no or mixed signals, `model default` if in that list, else the first entry. A role with no line takes `model default`; neither → dispatch unchanged.

Absent, or old form (per `/cairn-doctor`) — before the first agent dispatch, offer `/cairn-setup --local`'s model step, once. Declined → stand down for the session, as above.

## Scope resolution

On cold resume — `STATE.md` holds a scope record but this session has none — read its frontmatter as the active record, per `reference/resume.md`; no interview, no `cairn:scope`.

Otherwise, resolve scope — invoke `Skill(skill: "cairn:scope")` — when any of these is true:

1. First substantive request.
2. Goal or area outside the active record.
3. Underspecified: no object, no done condition, or unnamed files.
4. More than ~3 actionables not already in the record.
5. User invalidates scope ("actually, let's…", "scrap that").
6. Cold resume, no record to restore.

Otherwise, continue — most messages: a refinement inside scope, an answer, an instruction you can act on, or conversation. A slight extension of scope: amend the record directly.

**Scope record**, under 400 B:

```yaml
goal: <one sentence>
paths: [<dirs or globs in scope>]
done_when: <checkable condition>
out_of_scope: [<explicitly excluded>]
source: <doc, if any>
path: default | escalated
```

Continuity test: request fits `paths`, serves `goal`, keeps `done_when`? Yes → continue; no → resolve again.

Default path: held in the main thread, nothing written to disk. Escalated path: written to the task folder's `STATE.md`.

## Path choice

| Path | Flow | Budget |
|---|---|---|
| Default | `builder` → `reviewer` → PR | ≤ 40k tokens |
| Escalated | requirements (approved) → `planner` (approved) → `builder` → `reviewer` → PR, with `STATE.md` | ≤ 150k tokens |

Escalate when the change spans more than one submodule, alters a published contract (API, schema, or event), or can't be described in two sentences.

A change touching `docs/` also dispatches `scribe`; `builder` never writes there.

Before each escalated dispatch: bind the task pointer per `reference/dispatch-pointer.md`, brief per `reference/manifest-brief.md`; load order per `reference/context-layers.md`. A status question reads the task's `STATE.md` frontmatter, derived stage, the manifest only if needed, no note.

## Delegating investigation

Main-thread reading costs context. One file settles it — read it. More than one — delegate: `Explore`, or `general-purpose` where `Explore` isn't offered.

## Attendance

| Mode | Posture |
|---|---|
| Interactive | Questions answered as they come. |
| Attended | Auto-accepted; human still answers. |
| Unattended | Escalated only; default-and-flag; stops at a terminal state in `key_info`. See `reference/unattended.md` |
