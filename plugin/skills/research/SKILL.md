---
name: research
description: Resolves the topic and task folder, then hands off to dispatch research.
---

# cairn:research

## Steps

1. No topic or question given → ask for one.
2. No active task folder for this session → say so, stop. This skill does not create one — `research` requires that folder to already exist.
3. Hand back a dispatch scope — the topic, the active task folder's path — to the main thread, which dispatches `research` with it.
4. Once the dispatched `research` agent hands back findings text, the main thread writes it into the active task folder (per `cairn:shared`'s grouping convention: one file, or a named subfolder if results cluster into distinct topics) and reports the resulting path onward.
