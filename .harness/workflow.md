> This repo's rules, for anyone working in it: people, Claude, or another AI tool. A rule here can add or tighten a check; with cairn installed, it can't remove one cairn already runs.

## Branching
- Direct commits to `main`, no feature branches observed

## Commits / PR
- One artifact per commit + its `docs/REGISTRY.md` line (if it adds an agent) + `CHANGELOG.md` entry — never a sweep
- `CHANGELOG.md` is main-thread-owned by convention — no agent can write repo root (`scribe` is restricted to `docs/`)
- Bump `plugin/.claude-plugin/plugin.json` version on every commit, including docs-only — the marketplace re-syncs a consuming project's install on version change, not on content diff, so an un-bumped change never reaches installs. Patch for docs/fixes, minor for a new capability.
- A `mission-control` change lands as its own commit in the root submodule, pushed. Then register it here as a separate commit: bump the gitlink, run `python tools/sync_mission_control.py` to refresh `plugin/mission-control/`, bump the version, add the `CHANGELOG.md` entry

## Gates
- `python tools/budget.py` clean after every file; `python tools/sync_mission_control.py --check` clean at phase end
- Phase-end: `budget.py` + `pytest tools/` + `for s in plugin/hooks/*.sh; do "$s" --selftest; done` + `budget.py --report`
- No mandate language (MUST/ALWAYS/NEVER/MANDATORY/NON-NEGOTIABLE) in shipped artifacts
