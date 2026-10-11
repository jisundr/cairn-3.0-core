---
name: start
description: Entry point, loaded once per session. Resolves the .harness/ gate, scope, path, and attendance.
---

# cairn:start

## Harness gate

One `Glob .harness/**/*.md` call, once per task; hold the result — never re-glob mid-task.

- **Present** — read what the current step needs, proceed.
- **Partial** — proceed with what's there. A missing individual file skips silently.
- **Absent** — don't proceed with cairn's workflow. Say cairn works from the project's own `.harness/`, and offer `/cairn-setup`, once. If declined, stand down for the session: no more asking, no writes. Keep working on the request normally, without cairn.

## Local preferences

Also covered by the glob: `.harness/local/preferences.md`, classified per `/cairn-doctor` (active / ignored-by-ceiling / unrecognised). Dispatch prompts carry only active values — never the file or its path; no agent reads it. Active `prefer-path` feeds the path choice. Active `model` lines bound the `model` param of each cairn agent's `Agent()` call, not prompt text (a no-op for `subagent_type: "fork"`). Pick from the role's list: its most capable model for escalated or code-writing work, its lightest for small or read-only work; with no strong signal or mixed signals, `model default` if in that list, else the first entry. A role with no line takes `model default`; neither → dispatch unchanged.

Absent, or old form (per `/cairn-doctor`) — before the first agent dispatch, offer `/cairn-setup --local`'s model step, once. Declined → stand down for the session, as in the Harness gate; nothing persists, so a later session re-evaluates.

## Scope resolution

On cold resume — `STATE.md` holds a scope record but this session has none — read its frontmatter as the active record, per `reference/resume.md`; no interview, no `cairn:scope`.

Otherwise, resolve scope — invoke `Skill(skill: "cairn:scope")` — when any of these is true:

1. First substantive request.
2. Goal or area outside the active record.
3. Underspecified: no object, no done condition, or unnamed files.
4. More than ~3 actionables not already in the record.
5. User invalidates scope ("actually, let's…", "scrap that").
6. Cold resume, no record to restore.

Otherwise, continue — most messages: a refinement inside scope, an answer to your question, an instruction you can already act on, or conversation. A request that only slightly extends scope: amend the record directly.

**Scope record**, under 400 B:

```yaml
goal: <one sentence>
paths: [<dirs or globs in scope>]
done_when: <checkable condition>
out_of_scope: [<explicitly excluded>]
source: <doc, if any>
path: default | escalated
```

Continuity test: request fits `paths`, serves `goal`, doesn't change `done_when`? Yes → continue; no → resolve again.

Default path: held in the main thread, nothing written to disk. Escalated path: written to the task folder's `STATE.md`.

## Path choice

| Path | Flow | Budget |
|---|---|---|
| Default | `builder` → `reviewer` → PR | ≤ 40k tokens |
| Escalated | requirements (approved) → `planner` (approved) → `builder` → `reviewer` → PR, with `STATE.md` | ≤ 150k tokens |

Escalation trigger, verbatim: escalate when the change spans more than one submodule, alters a published contract (API, schema, or event), or can't be described in two sentences.

A change touching `docs/` also dispatches `scribe` — `builder` never writes there.

Before each escalated dispatch, bind the task pointer per `reference/dispatch-pointer.md`.

## Delegating investigation

Resolving an open question or scope ambiguity in the main thread costs whatever it reads there. One file settles it — read it. More than one — delegate: `Explore`, or `general-purpose` where `Explore` isn't offered.

## Attendance

| Mode | Posture |
|---|---|
| Interactive | Questions answered as they come. |
| Attended | Auto-accepted; human still answers. |
| Unattended | Escalated only; default-and-flag; stops at a terminal state in `key_info`. See `reference/unattended.md` |
