# Pointing your marker at your sub-task

A `SubagentStart` hook writes each subagent a marker in `~/.claude/cairn/active/`, seeded with the session pointer's task, and its context line names your marker file (`<session_id>--<agent_id>.active`). Parallel sub-tasks share one pointer, so their markers all start on the same task. Rewrite yours to your own sub-task folder so mission-control lights the right card.

**When.** Only if that context line named a marker file and the dispatch prompt gave you a sub-task folder (relative to cwd, as the pointer stores it). Otherwise skip it; the pointer's task stays, which is the fallback. Do it as your first step. It touches only that marker, never the diff, and a failure is not a reason to stop the task.

**Command.** Set `F` to the folder and `M` to the marker file name in the same call:

```bash
D="$HOME/.claude/cairn/active"; [ -n "${F:-}" ] && [ -f "$D/${M:-}" ] && { T=$(mktemp "$D/.retask.XXXXXX") && jq -c --arg t "$F" '.task=$t' "$D/$M" >"$T" && mv "$T" "$D/$M" || rm -f "$T"; }; true
```

The temp file's name does not end `.active`, so a partial write is never read as a marker. `project` is kept; only `task` changes. `SubagentStop` still deletes the marker when you end.
