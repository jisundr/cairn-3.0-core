# Context layers

What a stage loads, outermost first. Each layer has a token cap per path; the caps sum inside the path's budget (40k default, 150k escalated), and when a stage runs long the tail layers truncate first.

| # | Layer | Default cap | Escalated cap |
|---|---|---|---|
| 1 | Root `CLAUDE.md` | 1000 | 1000 |
| 2 | `.harness/` rules selected by trigger and scope | 5000 | 8000 |
| 3 | Manifest `CONTEXT.md` (escalated folders that have one) | 0 | 2000 |
| 4 | Notes, applying only when notes exist; at most 5 notes and 4,000 B in total | 1000 | 1000 |
| 5 | Prior stage outputs named by the manifest's Inputs rows | 8000 | 40000 |
| 6 | Working files: the code and docs the stage reads and edits | 20000 | 90000 |

Rows sum to 35,000 (default) and 142,000 (escalated), leaving headroom for the conversation itself.

Layers 1 and 2 are read once per task. Layer 3 is read when a stage's brief is built, per `manifest-brief.md`. Layer 4 does not exist until a project has notes; a project without them skips it and nothing else changes. Layers 5 and 6 are the tail: truncate 6 first, then 5, then 4.

A status question loads only the task's `STATE.md` frontmatter and the derived stage, plus the manifest when the answer needs it, and no notes.
