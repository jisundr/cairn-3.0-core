> This repo's rules, for anyone working in it: people, Claude, or another AI tool. A rule here can add or tighten a check; with cairn installed, it can't remove one cairn already runs.

## Branching
- Direct commits to `main`, no feature branches observed

## Commits / PR
- One artifact per commit + its `docs/REGISTRY.md` line (if it adds an agent) — never a sweep. Version and `CHANGELOG.md` change on release only via `/cairn-release`, not per commit
- `mission-control/` is a plain directory in core (no submodule): edit it, run `python tools/sync_mission_control.py` to refresh `plugin/mission-control/`; both copies are excluded from the budget gate

## Gates
- `python tools/budget.py` clean after every file; `python tools/sync_mission_control.py --check` clean at phase end
- Phase-end: `budget.py` + `pytest tools/` + `for s in plugin/hooks/*.sh; do "$s" --selftest; done` + `budget.py --report`
- No mandate language (MUST/ALWAYS/NEVER/MANDATORY/NON-NEGOTIABLE) in shipped artifacts

## Release
Cutting a release: follow the Procedure file, and get an explicit yes before pushing a tag or creating a release.
- Branch: main
- Host CLI: gh
- Procedure: .harness/reference/release.md
