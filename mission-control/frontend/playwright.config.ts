import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

// Two fixtures, same split as token-metering/frontend's playwright.config.ts:
// "populated" (seeded via e2e/fixtures/seed.py, under a scratch HOME so
// server.py's import-time DEFAULT_CLAUDE_PROJECTS_DIR/
// DEFAULT_KNOWN_PROJECTS_PATH resolution can't pick up this machine's real
// projects - the same isolation gap that caused a real-data leak during
// phase 5's manual testing) and "cold-start" (an empty, never-seeded
// project root).
//
// Each fixture is now a single `server.py` process: vite.config.ts's
// `build.outDir` points at `../static`, which server.py's own static_dir
// route already serves alongside its JSON API, so there's no second
// `vite preview` process or `/api` proxy to run. `npm run build` must
// still precede `playwright test` - server.py serves whatever's already
// in `static/`, it doesn't build it.
const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));
const MISSION_CONTROL_ROOT = path.resolve(FRONTEND_ROOT, "..");
const SCRATCH_ROOT = path.resolve(FRONTEND_ROOT, ".e2e-scratch");
const POPULATED_SCRATCH = path.join(SCRATCH_ROOT, "populated");
const COLD_START_SCRATCH = path.join(SCRATCH_ROOT, "cold-start");
const COLD_START_ROOT = path.join(COLD_START_SCRATCH, "project");

const POPULATED_PORT = 4417;
const COLD_START_PORT = 4419;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "populated",
      testDir: "./e2e/populated",
      use: { ...devices["Desktop Chrome"], baseURL: `http://127.0.0.1:${POPULATED_PORT}` },
    },
    {
      name: "cold-start",
      testDir: "./e2e/cold-start",
      use: { ...devices["Desktop Chrome"], baseURL: `http://127.0.0.1:${COLD_START_PORT}` },
    },
  ],
  webServer: [
    {
      command: `python3 e2e/fixtures/seed.py "${POPULATED_SCRATCH}" && python3 "${MISSION_CONTROL_ROOT}/server.py" "${POPULATED_SCRATCH}/project" ${POPULATED_PORT}`,
      url: `http://127.0.0.1:${POPULATED_PORT}/api/projects`,
      cwd: FRONTEND_ROOT,
      env: { HOME: POPULATED_SCRATCH },
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: `python3 "${MISSION_CONTROL_ROOT}/server.py" "${COLD_START_ROOT}" ${COLD_START_PORT}`,
      url: `http://127.0.0.1:${COLD_START_PORT}/api/projects`,
      cwd: FRONTEND_ROOT,
      // Overridden too (not left pointing at the real machine's HOME) so
      // DEFAULT_KNOWN_PROJECTS_PATH/DEFAULT_CLAUDE_PROJECTS_DIR (both
      // computed once from Path.home() at import time) can't pick up stray
      // real projects and break the hermetic empty-state fixture.
      env: { HOME: COLD_START_SCRATCH },
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
