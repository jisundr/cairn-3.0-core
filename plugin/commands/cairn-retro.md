---
description: Drafts harness updates from this session's evidence, for you to confirm.
---

Reflects on this session's conversation only — never the codebase, that's `/cairn-setup`'s job.

1. No `.harness/` (none of the four files present) → say cairn has nothing to refine without one, point at `/cairn-setup`, stop. Writes nothing.
2. Look back over this session for: a correction given more than once, a wrong assumption about the stack/workflow/environment you had to walk back, an undocumented command or convention that turned out to matter, a repeated failure a documented rule would have caught. Skip anything already correctly captured in the harness.
3. Read the four harness files. For each candidate, show it plus typed evidence and an `applies when:` trigger per `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/rule-format.md` (a session-only note becomes `correction:` dated today), map it to the matching file and section, ask approve / edit / drop.
4. Confirmed lines, written per `rule-format.md`: add one bullet under the matching section, or replace exactly one line (a touched legacy line may gain annotations in the same replace; show before and after) — never a new file, section or rewrite. A file already at its line cap (40/40/30/30) is reported, not overflowed.
5. Any file changed → regenerate `docs/BUDGET.md` (line count, cap, headroom per file), same as `/cairn-setup`.
6. Nothing to propose → say so in one line, stop.
