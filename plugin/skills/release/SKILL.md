---
name: release
description: Cuts an rc tag or final release per the harness rules; publishes on a yes only.
---

# cairn:release

Runs in the main thread; subagents do not publish. Invoked as `rc` or `final`, plus an optional `major|minor|patch|X.Y.Z` (default `patch`).

## Rules

Read `## Release` in `.harness/workflow.md`: one `- Key: value` line per key, from this fixed list (`/cairn-doctor` checks it). Defaults apply to an absent key or section.

| Key | Default |
|---|---|
| Branch | the repo's default branch |
| rc tag | `vX.Y.Z-rcN`; an rc is a tag only |
| final tag | `vX.Y.Z` |
| final title | `X.Y.Z`; a final is tag plus release with notes |
| Version file | `none`: the tag is the version |
| Host CLI | `gh` for github.com, `glab` for a GitLab host |
| Extra checks | `none` |
| Procedure | `none`; else a path to a Markdown file (e.g. `.harness/reference/release.md`) |

Section absent → say which defaults apply and offer to write them under `## Release`; the offer declined leaves the harness untouched.

## Steps

1. **Prechecks** — clean tree, on the release branch, level with its remote, pipeline on HEAD green, target tag absent. Any miss → report it and stop. No tags at all → propose `v0.1.0` as the first version.
2. **Version** — last final tag plus the bump. rc → `N` is one above the highest existing `-rcN` for that version, else `1`. final → the version itself, whatever rcs exist.
3. **Collect** — merge commits since the last final tag, with each PR/MR title and description.
4. **Notes** — final only: plain language for someone who runs or integrates the project, from step 3. rc has no notes.
5. **Plan** — show commit, previous tag, new tag, release title, notes, and the exact commands. `AskUserQuestion`: **Go** or **Edit**. Edit → revise, ask again.
6. **Publish** — on Go: `git tag -a <tag> -m <tag>`, `git push origin <tag>`; final also creates the release with the host CLI.
7. **Verify** — the tag is on the remote and, for a final, the release exists; report the links.

## Procedure

Key set → read that file and follow it for steps 3–7: what to collect, a changelog entry and its commit, the tag message, the notes layout, and what CI does after the tag and how to verify it. The other keys still set branch, tag names, title and host. A procedure adds to them; a tag name or title it contradicts → report the clash and stop. File missing → report and stop.

Repo files change only where the procedure names them. The plan lists each such edit and commit, with its exact `git` commands, before anything is committed or pushed. The prechecks, the version rule, the plan with its explicit Go, and the stops below hold whatever the file says.

## Stops

An existing tag is never moved or overwritten (the CLI has no force flag here). A failed step ends the run and reports that step; nothing later runs. Repo files are untouched unless the harness says the version lives in one or the procedure names them.
