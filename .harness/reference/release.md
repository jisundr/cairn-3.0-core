# Release procedure

Read by `cairn:release` through `## Release` in `workflow.md`. The version and `CHANGELOG.md` change in the release PR, so a tag is cut on a commit that already carries them and nothing is edited at tag time.

## Before any tag

1. `version` in `plugin/.claude-plugin/plugin.json` equals the tag's `X.Y.Z`.
2. `CHANGELOG.md` has a `## X.Y.Z` heading. Either check fails: stop and say which; the fix is a PR, not an edit here.
3. `python tools/budget.py` and `python -m pytest tools/` pass on HEAD, and CI on HEAD is green.

## rc

An rc is the tag alone: `vX.Y.Z-rcN`, an annotated tag pushed to origin. No release object, no notes, no file edits.

## final

1. Tag `vX.Y.Z`, release title `X.Y.Z`.
2. Notes, in this order:
   - the lead paragraph of the `## X.Y.Z` section in `CHANGELOG.md`;
   - a pointer to the upgrade note, by full URL because a relative link is dead in release notes: https://github.com/jisundr/cairn-3.0-core#upgrading-from-20;
   - one line on the external cold run: `External cold run: <name>, <date>, pass`, or `Shipped without an external cold run: <reason>`.
   The run line is the maintainer's to fill in; ask for it when the plan is shown, and take Edit if it is not yet known.
3. Create the release with the host CLI after the tag is on the remote.

## After the tag

The tag does not re-run CI: `.github/workflows/ci.yml` runs on pushes to `main` and on pull requests, and the tag sits on a commit CI already passed on `main`. Confirm the tag and the release exist on the remote (`git ls-remote --tags origin`, `gh release view`) and report the links. A failure here is reported, never patched by moving the tag.
