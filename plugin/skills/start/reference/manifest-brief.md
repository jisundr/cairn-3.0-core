# Manifest-built briefs

`CONTEXT.md` is the folder's per-stage inputs and outputs, seeded from `task-assets/assets/tasks/_template/CONTEXT.md`. It is working output: stage derivation and sub-task numbering never read it.

**Seed.** When the main thread creates a new escalated task folder, copy the template in beside `REQUIREMENTS.md`. Only escalated, only new folders: the default path and existing folders get no manifest.

**Brief.** Before dispatching the next stage, read that stage's Inputs rows in `CONTEXT.md` and list in the brief only those files and sections, with each row's why. Outputs rows tell the stage where to write. The brief names the task folder path, the same folder `dispatch-pointer.md` binds for this dispatch; a sub-task dispatch names the sub-task's folder, a parent dispatch the parent's.

**No manifest.** A folder with no `CONTEXT.md` gets its brief built as it is today, from the scope record and the plan. Nothing is created for it and nothing reports it as a fault.

**Pointer.** The task pointer write is unchanged and happens as `dispatch-pointer.md` says; the brief adds no field to it.

**Upkeep.** `planner` fills the Plan rows while writing `PLAN.md`; the main thread fills the other stages' rows when it builds that stage's brief. Keep the file at 80 lines or fewer.
