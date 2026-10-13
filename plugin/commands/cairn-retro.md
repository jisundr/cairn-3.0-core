---
description: Drafts harness updates from this session's evidence, for you to confirm.
---

Reads this session and queued signals, never the codebase (that's `/cairn-setup`).

1. No `.harness/` → say there is nothing to refine, point at `/cairn-setup`, stop.
2. List queued signals (`.cairn/proposals/`) per `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/proposals.md`. Then scan this session for a twice-given correction, a wrong assumption about stack, workflow or environment, an undocumented command or convention, a repeated failure, an architecture decision.
3. Read the harness files. Show each candidate with evidence and an `applies when:` trigger per `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/rule-format.md` (a session-only note becomes `correction:` dated today) and its target section — approve / edit / drop? A decision is an ADR candidate (title, decision, options), not a rule.
4. Queued items: `proposals.py apply` once approved or edited, `proposals.py mark ... dropped` otherwise. Other lines per `rule-format.md`: add one bullet or replace one line (show before and after); never a new file or section. A file at its line cap (40/40/30/30) is reported, not exceeded. An approved ADR is not written here: say so (`docs/decisions/` is created if absent), have the main thread dispatch `scribe` with `cairn:adr`.
5. Harness file changed → regenerate `docs/BUDGET.md` per `/cairn-setup`.
6. Nothing to propose (ADR candidates count) → say so, stop.
