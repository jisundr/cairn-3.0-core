---
goal: Add an rm command that deletes a todo
paths: [src/todo.py, tests/test_todo.py]
done_when: rm <n> deletes the nth todo and a test covers it
out_of_scope: [undo, bulk delete]
source: user request
path: escalated
depends_on: none
key_info: approved. Next: builder implements rm and its test.
flags: ["numbering is 1-based"]
---

2026-09-01 10:00: task created
