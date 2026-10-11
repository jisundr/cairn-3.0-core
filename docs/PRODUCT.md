# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, both already fluent in Claude Code's own vocabulary (agents, skills, subagents, sessions, tokens):

1. An individual developer browsing GitHub or a plugin marketplace, deciding whether to run `/plugin install` on their own project.
2. A team lead or senior engineer deciding whether cairn is the right shared workflow convention to standardize on across a team's repos.

## Product Purpose

cairn is a Claude Code plugin that gives a project a lean, on-demand, non-invasive development workflow: a fixed builder → reviewer (with an opt-in planner) pipeline, run under a disclosed token budget, that reads a project's own `.harness/` rules instead of imposing its own conventions, and that a project can remove without a trace.

## Positioning

Unlike heavier agent-orchestration frameworks that add persistent scaffolding, dependencies, and standing token overhead to a project, cairn's entire footprint in a consuming project is one ≤ 400 B marker line in `CLAUDE.md`; everything else (agents, skills, budgets, docs) lives in the plugin itself and loads only on demand, in one of four explicit load classes tracked in `docs/BUDGET.md`. It is provably cheap (≤ 40k tokens default path, ≤ 150k escalated) rather than cheap by assertion, and provably removable rather than removable by promise.

## Operating Context

- Installed via the Claude Code plugin marketplace (`/plugin marketplace add`, `/plugin install`), then activated per-project with `/cairn-setup`.
- Two workflow paths: a two-hop default (`builder` → `reviewer` → PR) and an opt-in escalated path (`planner` → `builder` → `reviewer` → PR) for changes that span submodules, alter a published contract, or can't be described in two sentences.
- Three attendance postures over the same chain: interactive, attended, and unattended (escalated-path only; stops at `done` / `needs-human` / `stalled`; never auto-publishes).
- `/cairn-teardown` reverses installation, removing the marker block and `.cairn/` and reporting exactly what's left behind and why.
- Ships one optional feature, a local token-metering dashboard, mission-control (`/cairn-mc`, shipped as the `plugin/mission-control/` submodule), for a solo developer checking their own Claude Code session cost/token usage in a browser. Its visual system extends the landing page's Lockfile world into a live dashboard and has its own design record (`docs/DESIGN.md`, app at `plugin/mission-control/frontend/src`); landing-page work edits `docs/marketing/DESIGN-landing.md`, not the dashboard's record or components.

## Capabilities and Constraints

- Writes only a fixed, disclosed set of paths in a consuming project (marker block, `.harness/*.md`, `.harness/local/`, `docs/tasks/<slug>/`, `.cairn/`, and the files a task actually asks it to change) — never `.claude/settings*`, agents/skills/commands/hooks directories, the project's own `.gitignore`, CI config, manifests, lockfiles, or git internals.
- No accounts, no hosted service, no telemetry — everything runs locally inside the user's own Claude Code session.
- Pre-1.0 (current version in `plugin/.claude-plugin/plugin.json`), single-maintainer, open source on GitHub — no enterprise/paid tier.

## Brand Commitments

- Name is always lowercase in running prose: "cairn", never "Cairn" as a proper noun (headings/titles may still capitalize per normal title-case).
- Voice, established by the existing README: plain, direct, technical-confident — claims are backed by a specific number or file path rather than an adjective.

## Evidence on Hand

- No stars, testimonials, or case studies to cite — a cairn-brand surface's proof must come from the mechanism itself, never from invented third-party endorsement. But real, measured before/after numbers exist and are the strongest available proof:
  - **cairn's own predecessor → cairn 2.0** (this repo, measured directly at the 2.0 rewrite): 18 agents (278 KB) → 4 agents (5.5 KB); 10 skills (87 KB) → 10 skills (14.6 KB) — since grown to 5 agents (10.2 KB) and 11 skills (25.2 KB) as of 0.44; baseline tokens loaded before a user types anything, ~9k → ~800 (marker block + always-loaded frontmatter, counted from this repo's current `agents/`, `commands/`, `skills/*/SKILL.md`); tokens spent per feature, 200–400k → ≤ 40k (default path) / ≤ 150k (escalated path).
  - **Two other, unnamed agent frameworks evaluated during this redesign** (kept anonymous — private projects, not public products, cited only for their measured numbers): one ran ~52k baseline tokens before any work began and 0.7–1.5M+ tokens for one medium feature, driven by a large always-loaded registry and 10+ agent hops per task; the other proved that a ~1–2k token baseline is achievable with almost no framework at all, at the cost of near-zero enforcement (no CI, no blocking checks).
  - Source data for all of the above lives in a private local comparison document, not committed to this repo (it names and paths those other projects); only the numbers above, and cairn's own measured figures, are for public use.
- Real facts and voice to draw from: `README.md`, `CLAUDE.md`, `docs/BUDGET.md`, `docs/REGISTRY.md`.
- No existing logo or visual brand asset beyond the plain lowercase wordmark "cairn".

## Product Principles

1. Cheap by default, not cheap by claim — every cost statement on a cairn-brand surface must trace to a real number already published in the repo.
2. Non-invasive is the core trust argument — what cairn will never touch deserves equal prominence to what a user gets.
3. Two audiences, one page — speak to the solo evaluator's "will this cost me tokens/attention" and the team lead's "is this a convention worth standardizing on," without forking into two separate pages.
4. No invented social proof — stars, quotes, or logos that don't exist yet stay absent rather than faked.

## Accessibility & Inclusion

No project-specific requirement established beyond standard web accessibility; cairn itself is a CLI/plugin with no GUI to evaluate separately.
