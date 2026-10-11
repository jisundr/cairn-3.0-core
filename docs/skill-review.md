# Skill review for 3.0

Every skill carried over from cairn 2.0 (`a63d818`), reviewed against the budget gate (`tools/budget.py`) for the 3.0.0 release. Sizes are bytes measured on the epic 07 branch; `SKILL.md` caps are 3000 soft and 4096 hard. Never loaded by the model.

Default verdict is KEEP. A CUT needs a gate failure or a named redundancy and waits for the maintainer.

| Skill | SKILL.md | Headroom | Reference | Description | Load class | Reads `.harness/` | Verdict | Reason |
|---|---|---|---|---|---|---|---|---|
| brainstorm | 1580 | 2516 | 0 | 111 | on demand, from scope's vague path or on request | no | KEEP | Names a doc for `scribe`; `scope`'s vague path interviews and does not write one, so no overlap. |
| diagrams | 2723 | 1373 | 3430 | 82 | on demand, loaded by `scribe` via `spec` and `readme` | no | KEEP | Only diagram source in the plugin; `stale.sh` is executed, not loaded. |
| readme | 737 | 3359 | 0 | 97 | on demand, loaded by `scribe` | no | KEEP | Smallest doc skill; no other README structure exists. A format template loaded by `scribe`, not a duplicate of it. |
| release | 2993 | 1103 | 0 | 79 | on demand, from `/cairn-release` | `## Release` in `workflow.md` | KEEP | Cuts the 3.0.0 tags; under the 3000 soft cap. |
| requirements | 1632 | 2464 | 0 | 120 | on demand, loaded by `scribe` and `scope` | no | KEEP | Requirements structure that `scope` and `brainstorm` both point at. A format template loaded by `scribe`, not a duplicate of it. |
| research | 740 | 3356 | 0 | 72 | on demand, from `/cairn-research` | no | KEEP | Named redundancy: `commands/cairn-research.md` (entry point) -> `skills/research` (740 B pass-through carrying the active-folder precondition and the write-back rule) -> `agents/research`. Kept because the skill owns the precondition and the write-back, which the main thread performs after the agent hands back; the command stays a thin entry point and the agent a pure investigator. |
| review-pr | 4002 | 94 | 3571 | 116 | on demand, from `/cairn-review-pr` | `workflow.md` | KEEP | Soft-cap warning only; under the hard cap. Left untouched in 3.0. |
| run | 631 | 3465 | 0 | 86 | on demand, by name and from `review-pr` | `environment.md` | KEEP | Smallest skill; reads the start command from the harness. |
| scope | 3845 | 251 | 6910 (3 files) | 107 | on demand, from `start`'s checklist | `workflow.md` | KEEP | Soft-cap warning only; the long paths already sit in `reference/`. |
| shared | 4058 | 38 | 6686 (4 files) | 113 | on demand, from every agent | all four files | KEEP | Soft-cap warning only; 38 B of headroom, so left untouched. |
| spec | 853 | 3243 | 0 | 101 | on demand, loaded by `scribe` | no | KEEP | Spec structure; no overlap with `requirements`. A format template loaded by `scribe`, not a duplicate of it. |
| start | 4050 | 46 | 7455 (3 files) | 95 | on demand, once per session | `.harness/**/*.md`, `local/preferences.md` | KEEP | Soft-cap warning only; 46 B of headroom, so left untouched. |

12 KEEP, 0 CUT. The 12 are all of 2.0's skills: none were added or dropped. `task-assets` is a folder of runtime assets, not a skill (no `SKILL.md`).

## Gate

- No skill fails a hard cap. Four exceed the 3000 B soft cap (`review-pr`, `scope`, `shared`, `start`); each is no larger than at 2.0 `a63d818` (4002, 3845, 4058, 4059 B) and passes the gate as a warning.
- Always-loaded descriptions: 2472 B of the 3000 B ceiling across agents, skills and commands; the skills' own descriptions are 1179 B of that.
- Reference files are all under the 6000 B soft cap.
