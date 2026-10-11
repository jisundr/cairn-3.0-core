# Running unattended

Unattended forces the escalated path — the default path holds nothing on disk, so there'd be nothing to check once the run detaches.

## Before dispatch: isolation

Look for isolation in this order, and stop at the first one that applies:

1. Already isolated — check for it (e.g. a linked worktree) rather than assuming.
2. A native tool the harness already provides (a worktree command, a `--worktree` flag).
3. An installed worktree skill (e.g. superpowers' `using-git-worktrees`), if the project has one.
4. Plain `git worktree add`, as a last resort.

Worktrees are created only in submodules — never in the parent repo, which holds the task folders — and the dispatch names the parent-repo path of the sub-task's folder.

cairn doesn't build or run any of these itself — it's a plugin that shapes a session's behavior, not a process manager. If nothing isolates the run, it just runs in place; nothing else about unattended mode changes.

Get one explicit confirmation before the run actually detaches — show what will launch (which worktree/branch, what task) and wait for a yes. Not zero confirmations, and not a second round-trip once it's already been described.

## While running: no questions

`cairn:scope`'s vague-request interview is the one remaining place this section governs — dispatched agents (`planner`, `scribe`, …) run as Task-dispatched subagents with no `AskUserQuestion` access at all, attended or not, so their own fallbacks are unconditional and documented directly in each agent file. `cairn:scope` runs as a skill loaded into the main thread, which keeps the interactive channel — so here, specifically, take the most conservative, most reversible reading instead, and append one `flags:` line to `STATE.md` naming the assumption. `flags` is append-only, so by the end there's a full list of what was assumed, not just the last one.

A `reviewer` fail redispatches `builder`; cap this at 3 attempts (matching maestro's own fix-cycle cap) before stopping — don't loop past it.

## Ending: three states, then stop

Every unattended run ends by writing exactly one of these into `STATE.md`'s `key_info`:

| Outcome | Meaning |
|---|---|
| `done` | `builder` produced a change and `reviewer` approved it. |
| `needs-human` | Hit a fork with no safe conservative reading — most likely the goal is genuinely unnameable even conservatively (`cairn:scope`'s usual escalation, `cairn:brainstorm`, is itself interactive, so it isn't reachable here). The exact question goes in `key_info` alongside the marker. |
| `stalled` | The 3-attempt retry cap was hit without a passing review. |

None of these open a PR. `done` stops right after `reviewer` passes — the merge/PR/keep-as-is decision is left for a human, matching the reasoning in `finishing-a-development-branch` (if the project has it) that this decision is never inferred. A human resumes the task later — cold-resume (`skills/start/SKILL.md`'s Scope resolution) reads `STATE.md` back, sees the stop-marker and any `flags`, and picks up from there.

## Watching a run you can't sit through

Use whatever the environment already offers for checking on a detached or scheduled run — a background task notification, a monitor, a scheduled check-in — rather than inventing a relay of cairn's own. cairn's only job is what gets written into `STATE.md`; how a human learns it changed is the harness's concern, not this skill's.
