# EPIC.md

A parent folder with numbered sub-tasks holds `EPIC.md`: one row per sub-task — number, slug, status, `depends_on`, a one-line note. Status mirrors the same stage-inference `STATE.md` above already uses for a single task folder (no `PLAN.md` — `requirements`; a plan and no merged PR — `building`; a merged PR — `done`), plus `blocked` when a `flags` entry names what it's waiting on. `blocked` overrides whatever the stage-inference alone would say — a pre-`PLAN.md` sub-task that's also flagged reads `blocked`, not `requirements` — since a status that only says "nothing's happened yet" hides the reason a reader most needs. Drop back to the plain stage word the moment the blocking `flags` entry resolves.

It's a persisted table, not a re-derivation kept for convenience: whichever session moves a sub-task to its next stage — requirements get approved, `PLAN.md` lands, its PR merges — updates that sub-task's row before moving on, in the same commit where one is already being made for that transition. A row that falls behind its sub-task's own `STATE.md` is that session's own close-out left unfinished, not something a later reader should have to reconcile by re-deriving from frontmatter instead.

Create it in the same pass as the first numbered sub-task folder, seeded from `skills/task-assets/assets/tasks/_template/EPIC.md`.
