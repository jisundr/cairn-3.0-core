---
description: Drafts harness updates from this session's evidence, for you to confirm.
---

Reads this session's conversation and queued signals, never the codebase (that's `/cairn-setup`).

1. No `.harness/` (none of the four files present) → say there is nothing to refine, point at `/cairn-setup`, stop.
2. Queued signals in `.cairn/proposals/`: list them per `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/proposals.md`. Then look back over this session for: a correction given twice, a wrong assumption about the stack, workflow or environment, an undocumented command or convention, a repeated failure a rule would have caught, an architectural decision (alternatives weighed, lasting consequences). Skip what the harness covers.
3. Read the four harness files. For each candidate, show it plus typed evidence and an `applies when:` trigger per `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/rule-format.md` (a session-only note becomes `correction:` dated today), map it to the matching file and section, ask approve / edit / drop each. A decision is an ADR candidate (title, one-line decision, alternatives; no `docs/decisions/` yet → say approval creates it), not a rule: no `rule-format.md` or `proposals.py`.
4. Queued items go through `proposals.py apply` once approved or edited, or `proposals.py mark ... dropped`. Other lines per `rule-format.md`: add one bullet under the matching section, or replace exactly one line (a legacy line may gain annotations; show before and after) — never a new file, section or rewrite. A file already at its line cap (40/40/30/30) is reported, not overflowed. An approved ADR is not written here: state it was approved (with `docs/decisions/` if absent) and ask the main thread to dispatch `scribe` with `cairn:adr`.
5. Any harness file changed → regenerate `docs/BUDGET.md` as `/cairn-setup` does.
6. Nothing to propose (ADR candidates count) → say so in one line, stop.
