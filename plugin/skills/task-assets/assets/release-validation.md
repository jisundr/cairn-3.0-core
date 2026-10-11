# Validating `## Release`

Keys come from `${CLAUDE_PLUGIN_ROOT}/skills/release/SKILL.md`. Check each `- Key: value` line in `.harness/workflow.md`:

- Unknown key, or no `: value` → unrecognised. A key twice → duplicate.
- `rc tag` and `final tag` need `X.Y.Z`; `rc tag` also needs `N`. `final title` containing `v` → malformed.
- `Branch` must be a local or remote branch. `Version file`, unless `none`, must exist. `Host CLI` must be `gh` or `glab` and on PATH. `Procedure`, unless `none`, must be an existing file.

One line per finding; "valid" when none.
