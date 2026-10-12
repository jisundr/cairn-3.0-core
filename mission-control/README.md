# mission-control

Source of cairn's mission control: a local dashboard served by `server.py` (stdlib HTTP, bound to `127.0.0.1:4317`) with a Vite frontend in `frontend/`. It shows token and cost metering from `.cairn/tokens.db`, plus a task board over `docs/tasks/`.

This directory is a plain directory of this repo. `python tools/sync_mission_control.py` copies it to `plugin/mission-control/`, which is what ships. Users start it with `/cairn-mc`.

Build and verify: see `.harness/workflow.md` (`pytest`, then `npm run build`, `npm test` and `npm run e2e` inside `frontend/`).
