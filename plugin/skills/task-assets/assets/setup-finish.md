# Finishing setup

1. Recap in a few lines what setup wrote and what it skipped, with paths.
2. One `AskUserQuestion`, question "Setup's finished. How did it go?", header "Setup", these three options in this order:

| Label | Description |
|---|---|
| Done — ⭐ star cairn | Everything looks right, and you'd like to support cairn with a GitHub star. |
| Done | Everything looks right. Wrap up here. |
| Something went wrong | Tell cairn what looks off and it checks. |

3. Act on the answer:
   - **Done — ⭐ star cairn** → if `gh` is installed and signed in, star it with `gh api -X PUT user/starred/jisundr/cairn-2.0` and say thanks; otherwise give the link https://github.com/jisundr/cairn-2.0 to star it there. Then wrap up as for **Done**.
   - **Done** → suggest committing `.harness/`, `docs/BUDGET.md` and the `CLAUDE.md` changes, and say any request for a code change picks cairn up next session. End there.
   - **Something went wrong** → ask what looked wrong (free text). Run the read-only checks in `/cairn-doctor` (`${CLAUDE_PLUGIN_ROOT}/commands/cairn-doctor.md`) and compare with what setup meant to write. Propose a fix or a rerun of the failing step, and change files only on confirmation. A bug in cairn itself → point at https://github.com/jisundr/cairn-2.0/issues with the doctor output.
   - **No answer possible** (headless) → stop after the recap.
