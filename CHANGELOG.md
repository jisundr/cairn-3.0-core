# Changelog

## 3.2.0 - 2026-10-13

cairn 3.2 lets each project choose where closed task folders are archived. `/cairn-setup` proposes an existing archive folder or the default `docs/tasks/.archived/` and records the choice in `.harness/workflow.md`; `/cairn-triage` then offers to move closed task folders there, each one only after you say yes. Nothing moves on its own, and an existing `.harness/` upgrades untouched.

### Upgrading from 3.1

Update the plugin; there are no steps and no files to change. Without an `## Archive` section in `.harness/workflow.md`, the default `docs/tasks/.archived/` applies, and it is created only when you confirm your first move.

### What changed

- `/cairn-setup` looks under `docs/` for an existing archive folder (task folders are not candidates), proposes it or the default, and on your answer appends an `## Archive` section with a `- Path:` line to `.harness/workflow.md`. No answer writes nothing, and a re-run changes nothing.
- `/cairn-triage archive`, or asking after the report, offers to move Ready to close folders whose close date in `STATE.md` is at least one calendar month old. Each folder is asked about separately and moved with a plain `mv`, keeping its name, `STATE.md` and drafts, so a move can be undone. Triage steps 1 to 4 are otherwise read-only as before.
- Triage and `/cairn-doctor` skip the archive folder when scanning task folders. Doctor prints the configured path and reports it as `missing`, `not created yet` or `invalid`.
- The archive path is checked before any move: letters, digits, `.`, `_`, `-` and `/` only, strictly under `docs/`, and never `.git`, `.claude`, `.github` or an existing task folder.
- Rule checks and `/cairn-retro` treat the `## Archive` section like Gates and Release: its `- Path:` line is not reported as a legacy rule, and retro proposes no rules into it.
- Docs: the mission-control `CLAUDE.md` and `README.md` drop stale 2.0 and scaffold text, and the README is synced with 3.1.

### Known gaps

- The mission-control dashboard still lists task folders moved to the archive folder.
- The close date is the latest `STATE.md` log line that mentions done, closed, complete or merged, else the last log date, so a loosely worded log line can make a folder look older than it is.
- Setting up an archive folder can push `.harness/workflow.md` past its 30-line cap.

### Checks on the release commit

Measured on macOS (Darwin), after the last edit before the release commit. CI's own runs on Ubuntu are not quoted here; every number below is macOS-local.

- `python3 tools/budget.py` exits 0 with 11 soft-cap warnings (the same 11 as 3.1.0, with `cairn-triage.md` now at 2041 B and `cairn-doctor.md` at 1964 B against their 1500 B soft cap, and the always-loaded total at 2590 B against its 2500 B soft cap) and no errors.
- `python3 -m pytest tools/`: 492 passed.
- Hook selftests: all five scripts pass. `claude plugin validate . --strict` passes.

## 3.1.0 - 2026-10-12

cairn 3.1 adds architecture decision records. When a session settles an architectural choice, `/cairn-retro` offers it as an ADR candidate, and on your approval `scribe` writes it to `docs/decisions/` in a short fixed structure, so the reason behind a boundary or constraint outlives the task that produced it. Nothing is written without your approval, and an existing `.harness/` upgrades untouched.

### Upgrading from 3.0

Update the plugin; there are no steps and no files to change. Your `.harness/` is untouched, and `docs/decisions/` is created only when you approve your first ADR.

### What changed

- New skill `cairn:adr` defines the ADR structure: Status (proposed, accepted or superseded by NNNN), Context, Decision, Consequences and Alternatives considered. ADRs are numbered in sequence as `docs/decisions/NNNN-title.md`, and superseding one edits only the old file's Status line.
- `scribe` writes ADRs through `cairn:adr`. It still writes only under `docs/` and still creates nothing you did not ask for; the first ADR in a repo creates `docs/decisions/` only after you approve it.
- `/cairn-retro` offers an architectural decision from the session as an ADR candidate in the same approve, edit or drop step as rule edits. When `docs/decisions/` does not exist yet, it says approval creates it. Retro itself writes nothing for an ADR.
- The branching rule in cairn's own `.harness/workflow.md` now says feature branch and pull request, matching `CONTRIBUTING.md`.

### Checks on the release commit

Measured on macOS (Darwin), after the last edit before the release commit. CI's own runs on Ubuntu are not quoted here; every number below is macOS-local.

- `python3 tools/budget.py` exits 0 with 11 soft-cap warnings (9 on 3.0.0, plus `cairn-retro.md` at 1937 B against its 1500 B soft cap and the always-loaded total at 2538 B against its 2500 B soft cap) and no errors; both new warnings are under the hard caps (2048 B and 3000 B).
- `python3 -m pytest tools/`: 491 passed.
- Hook selftests: all five scripts pass. `claude plugin validate . --strict` passes.

## 3.0.0 - 2026-10-11

cairn 3.0 keeps the workflow of 2.0 and adds a learning loop: rules carry the evidence they came from and the condition they apply under, corrections you make are queued as rule candidates, and nothing is written to your `.harness/` without your approval. A 2.0 repo upgrades with its `.harness/` untouched: cairn never rewrites your `.harness/` without your approval, and an approved edit adds or replaces one line.

### Upgrading from 2.0

1. Your `.harness/` needs nothing. Every rule file works as written. cairn never rewrites your `.harness/` without your approval; an approved edit adds or replaces one line, and files are never regenerated.
2. `/cairn-mc`, its hooks and mission-control are unchanged and stay in this repository for 3.0.0.
3. Install 3.0 from this repository. The marketplace keeps its name `cairn-marketplace`, so uninstall 2.0 first:
   ```
   /plugin uninstall cairn@cairn-marketplace
   /plugin marketplace remove cairn-marketplace
   /plugin marketplace add jisundr/cairn-3.0-core
   /plugin install cairn@cairn-marketplace
   ```
4. What 3.0 adds: rules with an evidence line and an `applies when:` trigger; `/cairn-doctor` states for each rule (verified, stale, unverifiable, legacy, malformed); corrections queued under `.cairn/proposals/` and reviewed in `/cairn-retro`, where approval is always yours; `STATE.md` frontmatter published as schema 1 with a validator.
5. A rule without an evidence line is legacy. Doctor reports it and exits 0, and cairn never rewrites it without your approval. Add evidence when a rule is next edited, or leave it.
6. The first session after the update prints `cairn updated 0.51.16 -> 3.0.0` once. That notice is hook output, which reaches Claude as context, so you see it only if Claude relays it. It ends with "Run /cairn-setup or /cairn-doctor to refresh harness state."; the advice is optional, and `/cairn-setup` on an existing harness only inserts or annotates lines you approve.
7. `/cairn-teardown` removes the marker and `.cairn/` and leaves your rules.
8. `STATE.md` files from 2.0 validate unchanged when their frontmatter stays within the 1,024 B cap and they have `goal` and `key_info`. Three things produce an error, each with a one-line fix: frontmatter over 1,024 B (trim fields, or move detail below the closing `---`); no frontmatter (add the opening and closing `---`); `goal` or `key_info` missing (add the key). See `docs/schemas/state-v1.md`.
9. cairn 3.0 documents Python 3.11 (CI runs 3.11). `python3` is needed by `/cairn-mc`, by the rules check in `/cairn-doctor` and by the proposals queue (through `signals.sh`); without it the learning loop is silent, because the hooks exit 0.
10. Companion plugins (cairn-meter, cairn-board, cairn-kb) are planned after 3.0, with no date. mission-control remains in this repository for 3.0.0.

### What changed

- `/cairn-setup`, `/cairn-retro` and `/cairn-doctor` work with rules that carry the evidence they came from and an `applies when:` condition; doctor reports each rule as verified, stale, unverifiable, legacy or malformed, and retro proposes delta edits and checks staleness.
- `STATE.md` frontmatter is published as schema 1 (`docs/schemas/state-v1.md`) with `tools/state_schema.py` to validate it.
- Corrections you make are recorded at session end as proposals, presented in one batch in `/cairn-retro` next session; text that looks like a credential is dropped before it is stored, and nothing is applied without your approval.
- A budget gate (`tools/budget.py`) runs in CI and keeps the always-loaded footprint under its ceiling.
- A release procedure (`.harness/reference/release.md`, run by `/cairn-release`) and an upgrade test (`tools/upgrade_check.py`) that runs a 2.0 harness through the 3.0 scripts and checks it comes out byte-identical.
- All 12 skills of 2.0 were reviewed and kept (`docs/skill-review.md`).

### Checks on the release commit

Measured on macOS (Darwin), after the last edit before the release commit. CI's own runs on Ubuntu are not quoted here; every number below is macOS-local.

- `python3 tools/budget.py` exits 0 with 9 soft-cap warnings (the same 9 as on main) and no errors; always-loaded total 2472 B of 3000 B.
- `python3 -m pytest tools/`: 491 passed.
- Hook selftests pass: `allow-plugin-read.sh` 0 failed, `session-start.sh` 3 passed, `signals.sh` 5 passed, `stop-mc.sh` 4 passed, `subagent-marker.sh` 0 failed. `tools/sync_mission_control.py --check` is clean.
- `python3 tools/upgrade_check.py` on the committed 2.0 fixture: byte-identical after `session-start.sh`, `signals.sh`, `rules-check.py` and `state_schema.py` ran over it; 25 legacy rules, 0 malformed, exit 0. `stop-mc.sh`, `subagent-marker.sh`, `allow-plugin-read.sh`, `proposals.py apply` and `mark`, `/cairn-setup`, `/cairn-retro` and `--doctor` are not covered by CI.

### Earlier versions

The 2.0 history (0.x to 0.51.16) is in cairn-2.0 at [`a63d818`](https://github.com/jisundr/cairn-2.0/blob/a63d818/CHANGELOG.md), and in this repository's seed commit.
