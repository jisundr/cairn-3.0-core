# Classifying `.harness/local/preferences.md` lines

- A line that would relax, skip, or disable something one of the four team files requires, or a stage cairn's own path always runs (`builder`, `reviewer`) → **ignored by ceiling**, naming the conflicting file/section or "cairn's own path".
- `model <agent> = <model>[, <model>…]` (the models that role may use; one entry pins it), `<agent>` one of `builder`/`planner`/`reviewer`/`scribe`/`research`, each `<model>` one of `sonnet`/`opus`/`haiku`/`fable`, commas with optional spaces, not caught above → **active**. Any entry outside that model set makes the whole line unrecognised.
- `model default = <model>`, exactly one model from that set (`default` is reserved, not an agent) for any role with no line of its own, not caught above → **active**. A list here is unrecognised.
- `prefer-path = default` or `= escalated`, not caught above → **active**.
- A recognised key (`token-ceiling`, `narration`, `optional-pass`) not caught above → **active**.
- Anything else → **unrecognised**.

**Old form:** at least one active `model <agent>` line, none listing more than one model, and no active `model default` line. Its lines stay active as pins; `/cairn-doctor` names it and `cairn:start` offers the update.
