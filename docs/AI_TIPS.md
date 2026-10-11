# AI tips and tricks

Notes from personal experience working with AI coding agents.

## 1. Watch your instruction file size

**Description**
Always do evals and test, and monitor the size of your instruction files (CLAUDE.md, agent/skill files, etc.). Bloated instructions get loaded into every session whether they're needed or not, and can blow up your usage limit.

**Examples**
In cairn 2.0, every file an agent might load into context has a hard byte/line cap, checked by a script (`tools/budget.py`) instead of relying on memory or convention:
- Agent bodies, `SKILL.md` files, command files, hook scripts, and harness files each get their own soft/hard size limit — e.g. an agent body warns past 3000 B and fails past 4096 B.
- Agent/skill/command *descriptions* are loaded into every session regardless of use, so their combined total gets its own separate ceiling (2500 B soft / 3000 B hard).
- The same script flags leftover `TODO`/placeholder text, mandate language (`MUST`, `ALWAYS`, `NEVER`) that bloats instructions without adding enforcement, and other structural issues.
- `tools/test_budget.py` has a test per rule, so the check itself doesn't silently regress.
- `tools/budget.py --report` writes `docs/BUDGET.md`, a ledger of every governed file's size and remaining headroom.

**How to do it**
1. Decide which instruction files are always-loaded (descriptions, top-level CLAUDE.md) vs. on-demand (skill/reference bodies) — always-loaded content needs a tighter budget since it costs you on every session.
2. Put a real, enforced number on each category instead of "keep it short" — a cap the AI can check, not a vibe.
3. Write a script or test that measures against that number, and run it after every change to instructions, not just at review time.
4. Pair each cap with a one-line reason ("this loads into every session") so a human reading it understands why the limit exists, not just that it exists.

## 2. Don't let the AI read all instructions at once

**Description**
Not every instruction is needed for every task. Loading everything up front wastes context and budget on content that's irrelevant to what's actually being asked — load only what the current step needs, when it needs it.

**Examples**
cairn 2.0 is built around this idea end to end:
- In a consuming project, cairn leaves a single marker line in that project's `CLAUDE.md` — nothing else. The rest (`.harness/architecture.md`, `standards.md`, etc.) is only read when a skill actually needs it.
- Inside a skill, `SKILL.md` stays small and holds a "Load when" table instead of the full content, e.g. `plugin/skills/review-pr/SKILL.md` points to `reference/draft-template.md` with the note "Drafting findings ... the format to present" — that reference file is only pulled in at that step, not at skill start.
- `tools/budget.py` enforces this split by checking skill *reference* files are actually named in their skill's "Load when" table (an orphaned reference file that's never linked is flagged as a bug — content sitting in the repo but not reachable on demand).

**How to do it**
1. Split instructions into an always-loaded shell (short: what this is, when to use it, where the rest lives) and on-demand detail (the actual how-to, examples, edge cases).
2. Use a lookup table or index in the shell file that names each on-demand file and the specific moment to load it — a human or agent should be able to tell *when* to load something without opening it first.
3. Check that every piece of on-demand content is actually referenced from an index somewhere — unlinked detail files are dead weight that either never loads (wasted work writing it) or gets loaded blindly (defeats the point).
