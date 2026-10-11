---
description: Sorts task folders.
---

Read-only; never writes or blocks. Per-folder facts: `/cairn-doctor` step 8.

1. **Scan** — `Glob` `docs/tasks/**/STATE.md` (not `Grep`: `docs/tasks/` is gitignored), skipping `_template/`. Read each one's `key_info` and last `YYYY-MM-DD:` log line; none → folder-name date. No `STATE.md` (an older `review` folder, `DRAFT.md` only): one trailing line.
2. **Branching** — `.harness/workflow.md`'s `## Branching` says commits go straight to main or no feature branches → direct-commit. Section absent → not.
3. **Classify** — first match wins:
   - **Needs attention now** — `needs-human` or `stalled` in `key_info` (`unattended.md` Ending).
   - **Awaiting approval** — `awaiting requirements approval`/`awaiting plan approval` in `key_info`.
   - **Ready to close** — whole-word `done`/`close(d)`/`complete`, any case, as `key_info`'s own status, not history or negated. Not direct-commit: or `gh pr list --head <folder-name> --state merged --json number -q 'length'` = `1`; output other than `0`/`1` → go by `key_info`. Direct-commit or `research` folder: skip `gh`. A folder with sub-task folders (own `STATE.md`) also needs every one Ready to close, deepest first; any such folder not Ready to close falls through, dated by the newest last log date among it and them.
   - **Still in progress** — last log date within 14 days of the newest across all folders.
   - **Looks abandoned** — older than that.
4. **Report** — five headings in that order, "none" if empty; name the anchor date. One line per folder, sub-tasks indented: name, deciding marker or last log date, and for Ready to close whether `key_info` or `gh` decided. No full `key_info`.
