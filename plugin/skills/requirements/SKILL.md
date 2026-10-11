---
name: requirements
description: Requirements doc structure (problem, goals, non-goals, constraints, open questions, success criteria). Loaded by scribe.
---

# cairn:requirements

Write under `docs/`, at a path matching what was asked. When the source material names a file, function, or behavior, check it against the codebase before writing Problem and Goals — a claim that doesn't hold goes under Constraints & assumptions as an open discrepancy, not into Problem as settled fact. Sections:

## Problem

What's wrong or missing today, for whom.

## Goals

What this must do, as checkable statements.

## Non-goals

What's explicitly out of scope, so scope doesn't drift mid-build.

## Stakeholders

Who's affected or has a say, beyond the requester. Omit when there's only one party.

## Constraints & assumptions

What bounds the solution — technical, timeline, dependency — and what's being assumed true without verification.

## Open questions

What's still unresolved and needs a decision before or during the build.

## Success criteria

How anyone can tell the requirement is met, without asking the author.

Keep each section to what the request actually supplies — an empty Non-goals section is fine; a placeholder isn't.

Hand the written path back with one line offering to continue into planning against it — a suggestion, not a trigger. The user may decline and stop here; nothing resolves scope until they ask.

Also loaded by `cairn:scope` for a task folder's `REQUIREMENTS.md`, for this section shape only — there, `reference/requirements-approval.md` governs approval, not the closing line above.
