# Contributing to cairn

Thanks for helping. Bug reports, fixes and ideas are all welcome.

## Reporting a bug

Open an issue with the bug template. Include your cairn version and the output of `/cairn-doctor`, which together answer most first questions.

## Making a change

1. Fork, clone with submodules: `git clone --recurse-submodules <your fork>`.
2. Install the dev tools: Python ≥ 3.10, `jq`, and `pip install pytest`.
3. Make your change in `plugin/`. Everything else at the root is for developing cairn and never ships.
4. Follow the per-commit rules in [`CLAUDE.md`](CLAUDE.md): one artifact per commit, a `CHANGELOG.md` entry, and a version bump in `plugin/.claude-plugin/plugin.json`.
5. Run the gate before opening a PR:

   ```
   python tools/budget.py
   python -m pytest tools/
   for s in plugin/hooks/*.sh; do "$s" --selftest; done
   ```

There is no CI; this gate is the only check, so run it locally before every PR. `claude plugin validate . --strict` is worth running too.

## Trying your change

Install your working copy as a local marketplace:

```
/plugin marketplace add /path/to/your/clone
/plugin install cairn@cairn-marketplace
```

Bump the version after each edit so the install picks it up.

## Token budget

cairn's main promise is a small always-loaded footprint. `tools/budget.py` enforces it and `docs/BUDGET.md` explains the four load classes. A change that adds always-loaded text needs a good reason in its PR.
