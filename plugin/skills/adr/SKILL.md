---
name: adr
description: ADR structure, numbering and supersession. Loaded by scribe.
---

# cairn:adr

## Where

`docs/decisions/NNNN-kebab-title.md`, a four-digit number. The next number is the highest existing plus one, read from a Glob of `docs/decisions/`; `0001` when none. ADRs are tracked in git, unlike task folders.

## Before writing

- `docs/decisions/` absent: create it only when the request says the user approved it (a retro-approved dispatch states this). Otherwise hand back asking for that yes.
- An existing ADR already records the same decision: hand back its path instead of writing a second.

## When an ADR fits

A choice between real alternatives, with lasting consequences, hard to reverse. A rule about how to work in the repo goes in `.harness/` instead; a rule may cite an ADR through `evidence: path:`.

## Structure

- `# NNNN. Title`
- A `Status:` line directly under it: `proposed`, `accepted`, or `superseded by [NNNN](NNNN-kebab-title.md)`.
- `## Context`, `## Decision`, `## Consequences`, `## Alternatives considered`.

Write all four sections. A section with nothing to say means the decision is not ready: keep it `proposed`, or hand back.

## Supersession

Write the new ADR (status `accepted`; its Context says it supersedes NNNN), then edit only the old ADR's `Status:` line to `superseded by [NNNN](...)`. The old body stays as written. A changed mind is a new ADR, not an edit of an accepted one.

## Closing

Hand back the path(s) written.
