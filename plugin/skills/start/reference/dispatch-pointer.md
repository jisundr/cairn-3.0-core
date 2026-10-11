# Binding the task pointer before a dispatch

Right before each `planner`, `builder`, `reviewer`, or `scribe` dispatch on an escalated task, rewrite the session's task pointer to the folder the dispatch is for. A dispatch not tied to a task folder (the default path) writes nothing.

**Write.** The same pointer as `resume.md`'s Task pointer paragraph: `~/.claude/cairn/active/$CLAUDE_CODE_SESSION_ID.json` via `Bash`, `{"project": "<cwd>", "task": "<folder path relative to cwd>"}`, `active/` created first if missing, skipped silently if that env var is empty. Its shape and reasons are there, not restated here.

**Which folder.** The sub-task's own folder when the dispatch is for a numbered sub-task. The parent folder when it is for the parent's own scope, including a dispatch after the sub-tasks finish; that is how the pointer rebinds to the parent.

**Why it is enough.** `hooks/subagent-marker.sh` copies the pointer into the agent's marker at `SubagentStart`, so an agent keeps the task it started with even when the pointer moves later. The write does not itself mark a card active.

**Parallel sub-tasks.** Sub-tasks dispatched in parallel share one pointer, so their markers all start on the same task. An agent holding a sub-task folder then rewrites its own marker to it, via `cairn:shared`'s `reference/marker-task.md`, and each card lights. The pointer write stays the fallback: `planner` and `scribe` have no `Bash` to rewrite with, and rely on it.
