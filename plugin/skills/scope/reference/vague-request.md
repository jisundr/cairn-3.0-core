# Interviewing a vague request

Ask one question at a time via `AskUserQuestion` — not a list of everything you might want to know.

Order questions by what unblocks the most:

1. The target — what or where the request is actually about, if that's unclear.
2. The done condition — what "finished" looks like, checkably.
3. The paths or files — only if still unclear once the target and done condition are named.

Stop as soon as `goal`, `paths`, and `done_when` are all nameable. That's usually one to three questions, not a full interview.

Prefer multiple-choice questions when there's a short list of plausible answers; open-ended when there isn't. If an answer is itself vague, ask a narrower follow-up rather than repeating the same question.

If `goal` still isn't nameable after narrowing — a new project, a subsystem with no existing flow to change, or the user hasn't fully formed the idea yet — invoke `Skill(skill: "cairn:brainstorm")` instead of continuing to ask narrower questions.

Dispatched unattended: don't interview — `cairn:brainstorm` is itself interactive and unreachable here. Name the most conservative, most reversible `goal`, `paths`, and `done_when` directly and append one `flags` line naming the assumption, per `cairn:start`'s `reference/unattended.md`. If `goal` still isn't nameable even conservatively, write `needs-human` to `STATE.md`'s `key_info` with what's missing and stop.
