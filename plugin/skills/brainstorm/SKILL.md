---
name: brainstorm
description: Explores an idea too unformed to scope (scope's vague path, or on request) and names a doc for scribe to write.
---

# cairn:brainstorm

Reached when naming `goal`/`paths`/`done_when` would mean guessing even after `cairn:scope`'s narrow questions — a new project, a subsystem with no existing flow, or an idea the user hasn't fully formed yet.

## Steps

1. Ask one question at a time via `AskUserQuestion` — the problem, who it's for, what "done" would look like. Prefer multiple-choice when there's a short list of plausible answers. Stop as soon as a one-sentence `goal` and a checkable `done_when` are nameable — usually two to four questions, not a full interview.
2. Only if a genuine choice remains among competing approaches — not a detail you could infer — propose two to three, lead with a recommendation and why, and get a pick. Skip this step entirely when there's one clear path.
3. Once the idea is nameable, name which document would help decide or record it, matching what `scribe` already writes — offer, don't write:
   - The problem or its audience is still unclear → `cairn:requirements`.
   - A design decision is worth recording before building → `cairn:spec`.
   - One clear path, nothing left to decide → no doc; hand back directly.
   State the recommendation in one line; dispatch `scribe` only if the user wants it written now.
4. Hand back a scope record — `goal`, `paths`, `done_when`, `out_of_scope` — to `cairn:scope`, which finishes resolution (escalation trigger, stated record) as normal.
