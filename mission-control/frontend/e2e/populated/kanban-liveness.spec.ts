import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ../../../docs/tasks/2026-09-28-1345-build-kanban-board/05-verification's
// own scripted stand-in for "two real parallel Claude Code sessions" (PRD
// §12 step 9's own "or a scripted equivalent" allowance - a live two-
// terminal run isn't scriptable in CI; see that sub-task's REQUIREMENTS.md
// Goal 4 for the one-time manual check this doesn't replace). Two real
// fixture task folders (fixtures/seed.py's HEARTBEAT_TASK_FOLDER_A/B) play
// the two sessions; this writes each one's heartbeat file directly under
// this webServer's own scratch `~/.claude/cairn/active/`
// (tasks.DEFAULT_HEARTBEAT_DIR, resolved against playwright.config.ts's own
// `HOME` override for the "populated" webServer) - the same
// testability seam tasks.build_cards's own `heartbeat_dir` parameter
// exists for (test_tasks.py exercises it directly; this exercises the same
// seam through a real server process and a real rendered board instead).
// Never touches the real global `~/.claude/cairn/active/`.

const SPEC_DIR = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(SPEC_DIR, "..", "..");
const POPULATED_SCRATCH = path.join(FRONTEND_ROOT, ".e2e-scratch", "populated");
const PROJECT_ROOT = path.join(POPULATED_SCRATCH, "project");
const HEARTBEAT_DIR = path.join(POPULATED_SCRATCH, ".claude", "cairn", "active");

const FOLDER_A = "docs/tasks/2026-01-03-0000-research-e2e-heartbeat-a";
const FOLDER_B = "docs/tasks/2026-01-03-0000-research-e2e-heartbeat-b";
const SESSION_A = "e2e-heartbeat-session-a";
const SESSION_B = "e2e-heartbeat-session-b";

// tasks.MARKER_MAX_AGE_SECONDS is 14400 (4 hours, §8) - comfortably past it
// without leaning on any other timing assumption.
const STALE_SECONDS = 15000;

function heartbeatPath(sessionId: string): string {
  return path.join(HEARTBEAT_DIR, `${sessionId}--agent.active`);
}

// Mirrors the real write side's own payload shape verbatim (`cairn:scope`'s
// SKILL.md: `{"project": "<cwd>", "task": "<folder path relative to cwd>"}`)
// - `PROJECT_ROOT` here plays that `<cwd>`, resolved the same way
// `server.discover_projects` resolves its own `project.root`.
function writeHeartbeat(sessionId: string, folder: string) {
  fs.mkdirSync(HEARTBEAT_DIR, { recursive: true });
  fs.writeFileSync(heartbeatPath(sessionId), JSON.stringify({ project: PROJECT_ROOT, task: folder }));
}

function removeHeartbeats() {
  for (const sessionId of [SESSION_A, SESSION_B]) {
    fs.rmSync(heartbeatPath(sessionId), { force: true });
  }
}

test.describe("kanban parallel-session liveness (§8)", () => {
  test.afterEach(removeHeartbeats);

  test("two fresh heartbeats both read active; aging one drops only its active badge", async ({ page }) => {
    // Defensive: a prior local run that failed before its own afterEach
    // ran would otherwise leave a stale file behind.
    removeHeartbeats();

    writeHeartbeat(SESSION_A, FOLDER_A);
    writeHeartbeat(SESSION_B, FOLDER_B);

    await page.goto("/kanban");
    const cardA = page.getByTestId(`task-card-${FOLDER_A}`);
    const cardB = page.getByTestId(`task-card-${FOLDER_B}`);
    await expect(cardA.locator(".kcard-ongoing")).toBeVisible();
    await expect(cardB.locator(".kcard-ongoing")).toBeVisible();

    // Age only A's marker's mtime past the 4 h ceiling - B's
    // stays fresh.
    const staleTime = Date.now() / 1000 - STALE_SECONDS;
    fs.utimesSync(heartbeatPath(SESSION_A), staleTime, staleTime);

    await page.reload();
    await expect(cardA.locator(".kcard-ongoing")).toHaveCount(0);
    await expect(cardB.locator(".kcard-ongoing")).toBeVisible();
  });
});
