# Generating the harness

1. Observe the codebase against the four sections (`architecture.md`, `standards.md`, `environment.md`, `workflow.md`). Show each candidate as a rule with typed evidence (`path:`, `cmd:`, or the user's own statement as `correction:<today>`; propose only rules you can cite), an `applies when:` trigger and the count ("3/4 services"); ask approve/edit/drop. Syntax: `${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/rule-format.md`.
1b. For `workflow.md`'s `## Release`, propose `cairn:release`'s keys (`${CLAUDE_PLUGIN_ROOT}/skills/release/SKILL.md`) from what the repo shows: default branch, host CLI from the remote, tag format from existing tags. Same approve/edit/drop; keys left out use the skill's defaults.
Then ask once whether the repo has a written release procedure (changelog entry, tag message, notes layout, post-tag CI). Yes → ask for its path, check the file exists, propose `- Procedure: <path>`, plus a plain sentence above the keys so a session without cairn follows it too: `Cutting a release: follow the Procedure file, and get an explicit yes before pushing a tag or creating a release.` The keys' values are written out, so they read the same without cairn. No, or no answer → leave the key out, so `cairn:release` uses its default flow.
2. For each of the four: read its template, fill confirmed rules, write to `.harness/<name>`, header unchanged. A file that already exists is never rewritten: insert confirmed lines under the matching sections, skip rules already present, and offer a restated legacy line as a one-line replace that adds its annotations.
3. Unless root `CLAUDE.md` already mentions `.harness/`, show this line and ask before appending it outside the cairn marker block, so any Claude session reads the rules, with or without cairn. It is the project's line, and `/cairn-teardown` leaves it.

   ```
   Project rules live in .harness/ (architecture, standards, environment, workflow); read the relevant file before changing code; skip rules whose `applies when:` doesn't match what you're changing.
   ```

4. Write `docs/BUDGET.md` from `budget.md`: each harness file's line count and headroom, one roster row per tracked file; never read back. Delete a stale `.harness/BUDGET.md`.

A bare `<path>` (needs `.harness/` already present, else run unscoped first) skips the marker steps entirely: step 1 observes only `<path>`'s uncovered patterns, and step 2 inserts confirmed lines ending `applies when: paths:<glob>` instead of rewriting the section. `<glob>` is `<path>` with any trailing slash stripped: a directory becomes `<dir>/**`, a file is used as is.
