# cairn

A lean, on-demand, non-invasive development workflow for Claude Code.

**cairn studies your repo and drafts its rules for you to approve. The rules are yours: plain markdown in `.harness/` that any Claude session can follow, with or without cairn.** Keep using cairn and it builds, reviews and plans against those rules on a small token budget. Remove it and the rules stay.

Think of cairn as a considerate guest in your project: it reads everything only when it's needed, does nothing until your project has told it how things work, and leaves nothing of its own behind when you remove it. The whole framework lives in this plugin.

## Install

```
/plugin marketplace add jisundr/cairn-2.0
/plugin install cairn@cairn-marketplace
```

Then, in the project you want cairn to work in, run `/cairn-setup`.

### Requirements

| Tool | Needed for | Without it |
|---|---|---|
| Claude Code | everything | — |
| `bash` | the hooks | hooks don't run. On Windows, use Git for Windows (Git Bash) or WSL. |
| `jq` | the hooks | hooks skip their work; session tracking and `/cairn-mc` data stay empty. |
| `python3` ≥ 3.10 | `/cairn-mc` and its token tracking | no dashboard, no cost data. Standard library only, nothing to `pip install`. |
| `git` | branches, worktrees, PRs | — |
| `gh` or `glab` (optional) | `/cairn-review-pr`, detecting merged PRs | `/cairn-review-pr` stops and says so; task stages fall back to `STATE.md`. |

Run `/cairn-doctor` to see which of these it finds.

## Commands

| Command | What it does |
|---|---|
| `/cairn-setup` | Adds the marker to `CLAUDE.md`, then drafts `.harness/` rules for you to confirm. `--local` writes your personal preferences. |
| `/cairn-doctor` | Read-only health check: version, marker, harness, dependencies. |
| `/cairn-triage` | Sorts task folders by stage. |
| `/cairn-research <topic>` | Investigates a topic with parallel subagents into the active task folder. |
| `/cairn-review-pr <url>` | Reviews a PR with cairn's security checklist; drafts first, posts only when you confirm. |
| `/cairn-retro` | Proposes harness updates from this session's evidence. |
| `/cairn-mc` | Opens the local cost dashboard. |
| `/cairn-teardown` | Removes the marker and `.cairn/`, and reports anything left behind. |

Day-to-day work needs no command: once set up, just ask Claude for a change and cairn routes it.

## Your first five minutes

1. **Run `/cairn-setup` in your project.** It asks before writing anything:
   - No `CLAUDE.md` yet? It offers to create a bare one, or you can run `/init` first.
   - It shows the one marker block it adds to `CLAUDE.md`.
   - It reads your repo and proposes rules for `.harness/`, each with the evidence it found. Approve, edit or drop each one.
   - It offers one line for `CLAUDE.md` pointing at `.harness/`, so Claude follows the rules even without cairn.
   - It asks whether to copy its task and product templates into `docs/`. "No" is fine; cairn has its own copies.
   - It suggests `.gitignore` lines for task folders, for you to add if you want.
2. **Commit what setup wrote.** `.harness/` is your team's from here on.
3. **Ask for a change in plain words**, for example: *"Add an `rm <n>` command that deletes a todo, with a test."* cairn takes the default path: `builder` makes the change and runs your tests, `reviewer` checks the diff, and you get a summary with any review notes. Nothing is committed or pushed until you say so. On a small Python project, that run took 8 turns and about $0.30.
4. **Bigger change?** When it meets the [escalation trigger](#two-paths-cheap-by-default), cairn writes requirements and a plan for you to approve before building, and asks you if the call is unclear.

If something seems off, run `/cairn-doctor`.

## Two paths, cheap by default

| Path | Flow | Budget |
|---|---|---|
| **Default** | `builder` → `reviewer` → PR. Two hops, no task folder, no plan, no spec. | ≤ 40k tokens |
| **Escalated** (opt-in) | `planner` → `builder` → `reviewer` → PR, with `docs/tasks/<slug>/STATE.md` for resume. | ≤ 150k tokens |

**When to escalate:** when the change spans more than one submodule, alters a published contract (API, schema, or event), or you can't describe it in two sentences.

The default path handles most changes, most of the time, in just two hops. Escalating is a deliberate choice for the cases above — not a fallback for when you're unsure.

## Attendance modes

Three postures for running the same chain — not three separate chains:

| Mode | Posture |
|---|---|
| **Interactive** | A normal chat session. cairn asks when it needs to. |
| **Attended** | Same chain, tool calls auto-accepted. A human is still there to answer. |
| **Unattended** | Dispatched, then left alone. Escalated path only — cairn makes and flags its own assumptions instead of asking, and stops at one of three outcomes (`done`, `needs-human`, `stalled`) written into `STATE.md`. |

Unattended mode never publishes on its own — it stops once `reviewer` passes and leaves merging or opening a PR to you. To run one: confirm the launch once, then hand the task off to an isolated worktree, either through a headless Claude Code run you start yourself or a scheduled/triggered one. To check back in, just resume the task normally — a cold resume reads `STATE.md`, the stop marker in `key_info` explains why it stopped, and any `flags` list what it assumed along the way.

See `plugin/skills/start/reference/unattended.md` for the details.

## What gets loaded, and when

Every artifact cairn ships falls into exactly one of four load classes, tracked in [`docs/BUDGET.md`](docs/BUDGET.md):

| Class | Cost | Rule |
|---|---|---|
| **Always loaded** | paid every turn of every context | Only the ≤ 400 B marker block in your project's root `CLAUDE.md`, plus the frontmatter `description` of each agent/skill/command. Nothing else, ever. |
| **On demand** | paid once, in one context | Agent bodies, `SKILL.md`, `reference/*.md`, `.harness/*.md`. Loaded by an explicit `Glob` + `Read` at a named step. |
| **Executed** | ~0 tokens | Scripts. Invoked via `Bash`, return compact JSON. The model reads the output, never the source. |
| **Never loaded** | 0 | `docs/REGISTRY.md`, `docs/BUDGET.md`, tests, CI config. Read by tooling and humans only. |

## Seeing what it actually costs

Run `/cairn-mc` to start a local dashboard at `http://127.0.0.1:<port>` showing exactly what your Claude Code sessions have cost — tokens and dollars, broken down by agent, model, skill, tool, and MCP call — with drill-down into any session's real transcript to verify the numbers yourself. It's local-only: no accounts, no cloud sync, nothing leaves your machine.

## What cairn writes in your project

In a consuming project, cairn writes **only** the paths below — everything else is out of bounds, including paths that would otherwise be convenient:

| Path | When | Whose content |
|---|---|---|
| A bare root `CLAUDE.md` (one `# <folder>` line) | `/cairn-setup`, only if none exists and you confirm | your project's |
| One marker block in root `CLAUDE.md` | `/cairn-setup`, on confirmation | cairn's, and cleanly removable |
| `.harness/*.md` | `/cairn-setup` or `/cairn-retro`, per-rule confirmation | your project's — cairn drafts it, your team owns it |
| One line in root `CLAUDE.md` pointing at `.harness/`, outside the marker | `/cairn-setup`, on confirmation | your project's — kept by `/cairn-teardown` so the rules outlive cairn |
| `docs/BUDGET.md` | `/cairn-setup`, alongside `.harness/` | your project's — line counts and caps for the harness files |
| `docs/tasks/_template/`, `docs/product/_template/` | `/cairn-setup`, only if you say yes | your project's — editable copies of cairn's templates |
| `.harness/local/` | `/cairn-setup --local`, on confirmation | this developer's — never committed |
| `docs/tasks/<slug>/` | escalated path only | your project's |
| `.cairn/` | runtime state | cairn's, and self-ignoring |
| `~/.claude/cairn/known-projects.json`, `pricing-check-state.json` | end of each session in a cairn project | cairn's — the list of projects `/cairn-mc` shows, and when its pricing table was last checked |
| `~/.claude/cairn/.jq-hint` | first session without `jq` | cairn's — an empty flag so the missing-`jq` hint shows only once |
| The files you actually asked to change | during work | your project's — that's the job |

**Never written, under any circumstance:** `.claude/settings.json` or `settings.local.json`; `.claude/agents/`, `.claude/skills/`, `.claude/commands/`, `.claude/hooks/`; your project's own `.gitignore` (except the self-contained one inside `.cairn/`); CI config, package manifests, lockfiles, git hooks, or `.git/` internals; any doc scaffold your project didn't ask for; anything else outside the repository root.

Run `/cairn-teardown` any time to remove the marker block and `.cairn/` (delete `~/.claude/cairn/` by hand once no project uses cairn). Your `.harness/` rules and the `CLAUDE.md` line pointing at them stay, so Claude keeps following them. Teardown shows you exactly what's left behind and why.

## Developing cairn

The plugin lives in [`plugin/`](plugin/), and that folder is all an install copies; `docs/`, `tools/` and the rest of the root are for developing cairn. See [`CLAUDE.md`](CLAUDE.md) for the per-commit discipline, and `.harness/*.md` for this repo's own development standards.
