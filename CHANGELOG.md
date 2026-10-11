# Changelog

## 3.0.0 - 2026-10-11

cairn 3.0 keeps the workflow of 2.0 and adds a learning loop: rules carry the evidence they came from and the condition they apply under, corrections you make are queued as rule candidates, and nothing is written to your `.harness/` without your approval. A 2.0 repo upgrades with its `.harness/` untouched.

### Upgrading from 2.0

1. Your `.harness/` needs nothing. Every rule file works as written and cairn does not rewrite it.
2. `/cairn-mc`, its hooks and mission-control are unchanged and stay in this repository for 3.0.0.
3. Install 3.0 from this repository. The marketplace keeps its name `cairn-marketplace`, so uninstall 2.0 first:
   ```
   /plugin uninstall cairn@cairn-marketplace
   /plugin marketplace remove cairn-marketplace
   /plugin marketplace add jisundr/cairn-3.0-core
   /plugin install cairn@cairn-marketplace
   ```
4. What 3.0 adds: rules with an evidence line and an `applies when:` trigger; `/cairn-doctor` states for each rule (verified, stale, unverifiable, legacy, malformed); corrections queued under `.cairn/proposals/` and reviewed in `/cairn-retro`, where approval is always yours; `STATE.md` frontmatter published as schema 1 with a validator.
5. A rule without an evidence line is legacy. Doctor reports it and exits 0, and cairn never rewrites it. Add evidence when a rule is next edited, or leave it.
6. The first session after the update prints `cairn updated 0.51.16 -> 3.0.0` once.
7. `/cairn-teardown` removes the marker and `.cairn/` and leaves your rules.
8. Companion plugins (cairn-meter, cairn-board, cairn-kb) arrive after 3.0 with their own note.

### What changed

- Epic 01: core seeded from cairn 2.0 with the budget gate restored in CI.
- Epic 02: `STATE.md` frontmatter published as schema 1 (`docs/schemas/state-v1.md`), with `tools/state_schema.py` to validate it; 2.0 files validate unchanged.
- Epic 03: rule format with evidence and `applies when:`, rules-check in `/cairn-doctor`, delta edits and a staleness check in `/cairn-retro`.
- Epic 04: correction signals recorded at session end (`signals.sh`, `proposals.py`) and presented in one batch next session; text that looks like a credential is dropped before it is stored.
- Epic 07: all 12 skills of 2.0 reviewed and kept (`docs/skill-review.md`), the upgrade test, the release procedure (`.harness/reference/release.md`), and this release.

### Checks on the release commit

- `python tools/budget.py` exits 0; 9 soft-cap warnings (the same 9 as on main before this epic), no errors.
- `python -m pytest tools/`: 486 passed.
- Every hook `--selftest` passes; `tools/sync_mission_control.py --check` is clean.
- `python tools/upgrade_check.py`: a 2.0 `.harness/` is byte-identical after the 3.0 hooks and scripts; 25 legacy rules reported, 0 malformed, exit 0.

### Earlier versions

The 2.0 history (0.x to 0.51.16) is in cairn-2.0 at [`a63d818`](https://github.com/jisundr/cairn-2.0/blob/a63d818/CHANGELOG.md), and in this repository's seed commit.
