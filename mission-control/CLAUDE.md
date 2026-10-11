# CLAUDE.md — cairn-2.0-mission-control

This repo is the standalone codebase for cairn mission control: the token-metering revamp plus the future kanban feature. It's consumed as a git submodule by [cairn-2.0](https://github.com/jisundr/cairn-2.0) at `mission-control/`.

## Scope

Code, tests, and this file only — no requirements, architecture rationale, user flows, or specs. This file and `.harness/` cover only what's needed to build and verify this codebase.

## Build & verify

See `.harness/workflow.md` for gates, `.harness/architecture.md` for stack/layering, `.harness/environment.md` for required tool versions.
