# Agent tool registry

Never loaded by the model — read by `tools/budget.py` and humans only.

Every tool an agent's frontmatter grants must be justified here, one section per agent:

```
## <agent-name>
- <Tool> — <one-line justification>
```

`budget.py` fails the build if an agent grants a tool this file doesn't justify for it, or if an agent whose name/description reads as a reviewer (`review`, `audit`, `check`) grants `Write` or `Edit`.

## scribe
- Read — baseline
- Glob — baseline
- Grep — baseline
- Write — authors new documents under docs/
- Edit — updates existing documents under docs/
- Skill — loads the relevant document-type skill for the requested format

## reviewer
- Read — baseline
- Glob — baseline
- Grep — baseline
- Bash — reruns the project's own verification commands against the diff
- Skill — loads cairn:shared for mechanics shared with the other agents

## builder
- Read — baseline
- Glob — baseline
- Grep — baseline
- Write — authors new files for the change
- Edit — modifies existing files for the change
- Bash — runs the project's own verification commands named in the harness
- Skill — loads cairn:shared for mechanics shared with the other agents

## planner
- Read — baseline
- Glob — baseline
- Grep — baseline
- Write — authors the task folder's STATE.md and plan under docs/tasks/<slug>/
- Skill — loads cairn:shared for the plan-writing mechanics shared with the other agents

## research
- Read — baseline
- Glob — baseline
- Grep — baseline
- Write — STATE.md updates only, scoped to the active task folder; findings are handed back as text, not written by the subagent
- WebSearch — internet-facing investigation angle
- WebFetch — internet-facing investigation angle
- Agent — fans out the parallel investigation subagents this capability exists for; the one agent in this repo granted it
- Skill — loads cairn:shared for the task-folder/STATE.md contract
