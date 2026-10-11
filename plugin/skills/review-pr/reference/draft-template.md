---
name: draft-template
description: The structured format review-pr presents combined findings in before posting — one header per PR/MR, one block per finding, plus a dated section for each re-review round.
---

# Draft template

`SEVERITY` is Critical/High/Medium/Low from `reference/security-checklist.md` for a security finding, or Blocking/Suggestion for anything else. `CATEGORY` is the finding's own category — the security checklist's category name, or the code-review category with its fix-lane in parentheses (e.g. `simplification (Lane A)`).

## On disk

Path: `docs/tasks/YYYY-MM-DD-HHMM-review-<repo-slug>-<pr|mr>-<number>/DRAFT.md` — a `review` task folder. `<repo-slug>`, `pr`/`mr`, and `<number>` are parsed directly from the same PR/MR URL "Resolve the target" reads for its host: `<repo-slug>` is the URL's `org/repo` with `/` → `-`; `pr`/`mr` and `<number>` come from the URL's own path/host shape.

Find it with `Glob` on `docs/tasks/*-review-<repo-slug>-<pr|mr>-<number>` — the date-time prefix isn't known ahead of a re-review, and `Glob` sees gitignored paths. Zero matches → First review: create the folder with the current local date-time and seed `DRAFT.md` from `docs/tasks/_template/DRAFT.md` — or, if that file doesn't exist yet (a project set up before review folders moved under `docs/tasks/`), from `../task-assets/assets/tasks/_template/DRAFT.md`, relative to this skill's base directory like the `reference/` paths — then fill in. One match → Re-review: its `DRAFT.md` is the starting draft, not a blank one; append new dated sections, never overwrite a prior round. More than one → ask the user which; don't guess.

Alongside it, seed `STATE.md` from `docs/tasks/_template/STATE.md` (same fallback path): `goal` reviewing the PR/MR, `source` its URL, `path: escalated`, `paths`/`out_of_scope` empty. `key_info` holds the round and the next step, overwritten at each stage: `round N drafted, awaiting Post or Edit` → `round N posted, awaiting author` → `final review` → `done: approved`. One dated log line per event, per `cairn:shared`. A Re-review folder made before review folders carried `STATE.md` gets one seeded on that round.

The files are gitignored (`docs/tasks/*` in the root `.gitignore`) — leaving them after Approval is harmless, nothing to clean up on the PR/MR side.

## First review

````markdown
# <PR #<number> | MR !<IID>> — <Short Title> (<repo>)

**URL**: <PR/MR URL>
**Branch**: `<source-branch>` → `<target-branch>`
**Diff refs**: base `<base_sha>` / head `<head_sha>`

Status: <draft reviewed and approved by user as-is | pending user review>

---

### [SEVERITY] `CATEGORY` — `file:line`
```<language>
<offending snippet>
```
<why this is in scope — tie back to the diff's own stated motivation when possible, not a pre-existing issue>
**Fix:** <concrete fix, or "no action required unless ..." for a Low/Suggestion finding>

<!-- repeat one block per finding, most severe first -->
````

## Re-review round

Appended to the same draft, one section per round:

````markdown
---

**Update (<YYYY-MM-DD>):** re-review round, diff refs base `<base_sha>` → head `<head_sha>`.

### [SEVERITY] `CATEGORY` — `file:line`
```<language>
<snippet>
```
<explanation — cite the prior round's related fix if it's the same class of issue>
**Fix:** <fix>

Status: <fixed | partially-fixed | still-open | disputed>. Verified against `<branch>` at head `<sha>`.

**Posting plan:** <new top-level comment/discussion | reply to thread #<n>>. Awaiting explicit posting confirmation.
````
