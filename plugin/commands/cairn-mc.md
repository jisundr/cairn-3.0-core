---
description: Starts the mission-control dashboard server in the background and opens it in the browser.
---

1. Start `python3 -u ${CLAUDE_PLUGIN_ROOT}/mission-control/server.py <project-root>` in the background via `Bash` with `run_in_background`, passing this session's project root as an absolute path explicitly (don't rely on the script's cwd default). The `-u` flag keeps stdout unbuffered so the readiness line in step 2 actually reaches the captured output instead of sitting in a pipe buffer. An empty or missing `.cairn/tokens.db` (no `Stop` event has fired yet) needs no special handling here — the server and frontend already render an empty state on their own.
2. Wait for the server's own readiness line in its output, `token-metering dashboard: http://<host>:<port>`, rather than a fixed sleep.
3. Open that URL in the default browser (`open` on macOS, `xdg-open` on Linux, `start` on Windows — pick per platform).
4. Report the URL and how to stop the server: this command started it as a backgrounded task in this session, not a foreground terminal process, so stopping it means ending that background task (report its task id) rather than pressing Ctrl-C.
