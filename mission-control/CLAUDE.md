# CLAUDE.md — mission-control

This directory is the source of cairn's mission control: token metering plus the task board. It lives in this repo as a plain directory; `python tools/sync_mission_control.py` copies it to `plugin/mission-control/`, which is what ships.

## Scope

Code, tests, and this file only — no requirements, architecture rationale, user flows, or specs. This file and `.harness/` cover only what's needed to build and verify this codebase.

## Build & verify

See `.harness/workflow.md` for gates, `.harness/architecture.md` for stack/layering, `.harness/environment.md` for required tool versions.
