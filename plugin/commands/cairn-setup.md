---
description: Adds cairn's CLAUDE.md marker, then drafts .harness/ rules to confirm. --local sets personal prefs; --track toggles ledger tracking.
argument-hint: [<path>] [--local] [--track <label>] [--untrack <label>]
---

Templates: `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/` (relative below).

`--track`/`--untrack` → Track mode; `--local` → `--local` mode; else Default.

## Default mode

1. No root `CLAUDE.md` → ask: create a bare one (`# <repo folder name>`, shown first), or stop so the user writes one (or runs `/init`). No answer → stop.
2. `CLAUDE.md` already has `<!-- cairn:start -->` → skip to 4.
3. Else read `claude-md-marker.md`, show it, ask before appending (blank line first if needed).
4. Follow `harness-generation.md` to observe, confirm, and write the four harness files plus `docs/BUDGET.md`; also covers the bare-`<path>` variant.
5. Unless a bare `<path>`, follow `tasks/setup.md`, then `product/setup.md`.
6. Finish per `setup-finish.md`.

## Track mode

Edits only the roster, rewrites `docs/BUDGET.md`; never touches team files or marker text.

1. `--track claude-md-marker`: no marker → say so, stop. Else add `claude-md-marker CLAUDE.md 400` to the roster (idempotent). `--untrack` removes it, else says so.
2. Other `<label>` → unrecognized; stop.

## `--local` mode

Follow `local/setup.md`. Never touches team files or the marker.
