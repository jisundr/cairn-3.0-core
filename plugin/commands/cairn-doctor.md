---
description: Read-only health check of version, marker, harness, roster and local prefs.
---

Read-only. Never writes, never blocks. Local-layer rules: `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/local-layer-classification.md`.

1. **Plugin** — read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, report `version`.
2. **Marker** — root `CLAUDE.md` present and contains `<!-- cairn:start -->`? Report yes/no.
3. **Harness** — for each of `architecture.md`, `standards.md`, `environment.md`, `workflow.md` under `.harness/`: present or absent.
4. **`.cairn/`** — present or absent; if present, `sessions.log` line count and its last line (skip anything else found there without asserting what it is).
5. **Roster** — `.harness/BUDGET.roster.md` present? Report it stale (pre-`0.2.1` naming) and say to rename it to `.roster.txt` by hand. Does not rename it itself.
6. **Local layer** — `.harness/local/preferences.md` absent → say so, stop. Else classify every line per the local-layer rules above (ignored by ceiling / active / unrecognised); say whether the file is in the old form (per those rules) and, if so, that `/cairn-setup --local` updates it. This is the only place any of it is ever said — nothing about the local layer surfaces during a normal task.

7. **Dependencies** — `jq`/`python3` on PATH, yes/no each. `.cairn/tokens.db` present → latest `timestamp` in `calls` (`sqlite3` or python3's `sqlite3` module); absent/no rows → say so.
8. **Task folders** — list `docs/tasks/*/` (skip `_template/`): folder name + `STATE.md`'s `key_info` if present.
9. **Release** — no `## Release` in `.harness/workflow.md` → "defaults apply", stop. Else validate per `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/release-validation.md`.
