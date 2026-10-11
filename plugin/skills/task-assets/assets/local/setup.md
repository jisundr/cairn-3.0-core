# Setting up local preferences

Never touches team files or the marker.

1. Ask which local prefs to set: models per role (builder/planner/reviewer/scribe/research; a `model <agent> = <model>[, <model>…]` allow-list each, plus one `model default = <model>` line, required whenever any model line is written; the orchestrator picks within them), path-choice leaning (one `prefer-path = default` or `= escalated` line), token ceiling, narration, optional-pass; skip unwanted.
2. Show exact contents, write `.harness/local/preferences.md` (base: `local/preferences.md`) plus `.harness/local/.gitignore` containing `*`. With an existing file: each single-model line becomes its list's first entry, other lines are kept, comments come from the base.
