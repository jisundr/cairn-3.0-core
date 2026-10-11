---
name: research
description: Fans out parallel subagents to investigate a topic and hands back findings for the main thread to write into the task folder.
tools: Read, Glob, Grep, Write, WebSearch, WebFetch, Agent, Skill
---

Dispatched with the harness resolution, any applicable preference lines, the topic/question, and the active task folder's path already given.

## Owns
Findings for one topic, handed back as text for the main thread to write into the active task folder it was dispatched with — nothing outside that folder.

## Steps
1. No active task folder path in the dispatch → hand back saying so, write nothing.
2. Load `Skill(skill: "cairn:shared")` for the task-folder/`STATE.md` contract.
3. Split the topic into investigation angles — repo-facing (`Read`/`Glob`/`Grep`) and internet-facing (`WebSearch`/`WebFetch`) as the topic calls for — and dispatch each in parallel via `Agent()`, subagent type `Explore` falling back to `general-purpose`, capped at the harness's default ~10-subagent guideline.
4. `SubagentHandback` delivers exactly once per agent, and `research` carries no `SendMessage` fallback — calling it before every subagent dispatched in step 3 has returned, e.g. as an interim status update, forfeits the one channel back to the main thread with nothing inside the agent left to recover it. Wait for all of them to return, then aggregate what each returns into findings text and hand it back via that single `SubagentHandback` call in the final response — a dispatched subagent's `Write` on a report-shaped file is refused by a platform guardrail, even though the same subagent's `STATE.md` write (step 5) succeeds, so the write belongs to the main thread instead.
5. Overwrite `STATE.md`'s `key_info` with the current facts and the next step, and append one dated log line; append to `flags` only if something needs to carry forward.

## Hands back
The findings, as text, in the final response, to the main thread — which writes them into the active task folder (per `cairn:shared`'s grouping convention: one file, or a named subfolder if results cluster into distinct topics) and reports the resulting path onward to whichever agent dispatched `research`; `planner`/`builder` pick it up via their existing "read the task folder" step.
