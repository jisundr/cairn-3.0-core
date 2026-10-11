# CLAUDE.md — working on cairn itself

This file guides work **on this repo** (building the cairn plugin). It is not the marker block cairn writes into a *consuming* project's `CLAUDE.md` — that's a separate, ≤ 400 B template at `plugin/skills/task-assets/assets/claude-md-marker.md`.

The plugin itself lives in `plugin/` — `.claude-plugin/marketplace.json` points there, so an install copies only that folder. Everything else at the root (`docs/`, `tools/`, `.harness/`, `CHANGELOG.md`) is for developing cairn and never ships.

## What cairn is

cairn 2.0 is a Claude Code plugin carrying a lean, on-demand, non-invasive development workflow: it leaves one marker line in a consuming project's `CLAUDE.md`, reads everything else on demand, does nothing until the project's `.harness/` has told it how the project works, and can be removed without a trace.

## Source of truth

`.harness/*.md` (architecture, standards, environment, workflow) holds this repo's development rules; `docs/REGISTRY.md` justifies each agent's tool grants. This file summarizes the parts that recur on every commit.

## Discipline for every change

- **One artifact per commit**, plus its `docs/REGISTRY.md` line (if it adds an agent) and its `CHANGELOG.md` entry. Never a sweep across many files.
- **Bump `plugin/.claude-plugin/plugin.json`'s version on every commit**, docs-only included — a consuming project's plugin install re-syncs on version change, not on content diff, so an un-bumped change never reaches it. Minor for a new capability, patch for everything else.
- **Run the gate after every file**: `python tools/budget.py`. Fix findings before writing anything else.
- **Chain a scripted edit to its commit.** When a multi-occurrence rename or similar edit runs via a script rather than `Edit`, chain the edit step and the `git commit` with `&&` (or `set -e`) so a failed edit can never still produce a commit — a shell that keeps going past a failed step is how an empty, misleading commit lands.
- **No mandate language** (`MUST`, `ALWAYS`, `NEVER`, `MANDATORY`, `NON-NEGOTIABLE`, a `HARD REQUIREMENTS` heading) in `plugin/agents/`, `plugin/skills/`, `plugin/commands/`, or `plugin/hooks/`. Say how a rule is enforced instead — e.g. "`reviewer` has no `Write` tool."
- **No scaffolding for later.** If nothing loads a file today, don't write it. No `TODO`/`TBD`/`FIXME`/`<placeholder>` in shipped artifacts.

## Phase gate

At the end of each build phase, run and paste the results of:

```
python tools/budget.py
python -m pytest tools/
for s in plugin/hooks/*.sh; do "$s" --selftest; done
python tools/budget.py --report && tail -5 docs/BUDGET.md
```

If any step fails, fix it before starting the next phase.

<!-- cairn:start -->
If the `cairn` plugin is available in this session, use it for development work in this repo — start with the `cairn:start` skill. If it is not available, ignore this block; nothing in it applies.
<!-- cairn:end -->
