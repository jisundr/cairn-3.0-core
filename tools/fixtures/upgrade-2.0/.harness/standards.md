> This repo's rules, for anyone working in it: people, Claude, or another AI tool. A rule here can add or tighten a check; with cairn installed, it can't remove one cairn already runs.

## Naming
- Docs specs: `docs/specs/YYYY-MM-DD-<slug>.md`, gitignored scratch
- Skill/agent/command names: lowercase-with-dashes
- Commit subjects: imperative mood, short, one artifact per commit

## Error handling
- Hooks: `set -uo pipefail`, silent `exit 0` on any missing dependency/field — advisory, never blocking
- Unknown/unpriced data reports `"unknown"`/`null`, never a silently-partial number

## Testing
- Python: `pytest`, `tmp_path`-based fixtures, one `test_*.py` per module
- Shell: every `.sh` requires `--selftest`, enforced by `tools/budget.py`

## Logging
- None by design — advisory-only philosophy, no logging framework

## Size caps
- Caps live as constants in `tools/budget.py` (source of truth); measured sizes land in `docs/BUDGET.md`. When something won't fit: move detail to `reference/*.md`, replace prose with a script, or cut the behavior and say so — never split a file just to dodge the number.
- Raising a cap: state the artifact + current/needed size + what was tried, then stop and ask. Never raise one on your own authority.
