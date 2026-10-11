import { expect, type Page, test } from "@playwright/test";

// Against the "populated" webServer (fixtures/seed.py): a project with two
// sessions - e2e-session-main (labeled, three calls across three agents,
// a usage-limit event) and e2e-session-other (unlabeled, one call on an
// unpriced model).

const SESSION_MAIN_LABEL = "Add a login page to the app";

function trackErrors(page: Page) {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  const pageErrors: Error[] = [];
  page.on("pageerror", (error) => pageErrors.push(error));
  return { consoleErrors, pageErrors };
}

test.describe("populated loaded states", () => {
  test("Overview renders seeded rollups and the usage-limit row, no console errors", async ({ page }) => {
    const { consoleErrors, pageErrors } = trackErrors(page);

    await page.goto("/");

    await expect(page.getByTestId("overview-empty")).toHaveCount(0);
    await expect(page.getByTestId("overview-disconnected")).toHaveCount(0);
    await expect(page.getByTestId("chart-bars")).toBeVisible();
    await expect(page.getByTestId("breakdown-sessions")).toContainText("2");
    await expect(page.getByTestId("by-models")).toContainText("claude-sonnet-5");
    await expect(page.getByTestId("by-tools")).toContainText("Bash");
    await expect(page.getByTestId("by-agents")).toContainText("builder");
    // O4: this fixture seeds a single project - no By-project panel.
    await expect(page.getByTestId("project-cost-panel")).toHaveCount(0);
    // Now a plain Breakdown row (moved from a standalone banner, link
    // dropped, both on request) - see warning-banner.spec.ts for its
    // selected-day behavior.
    await expect(page.getByTestId("usage-limit-banner")).toBeVisible();
    await expect(page.getByTestId("usage-limit-banner")).toContainText("Usage limit");

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("Sessions List renders both seeded sessions, no console errors", async ({ page }) => {
    const { consoleErrors, pageErrors } = trackErrors(page);

    await page.goto("/sessions");

    await expect(page.getByTestId("sessions-table")).toBeVisible();
    await expect(page.getByTestId("session-row-e2e-session-main")).toContainText(SESSION_MAIN_LABEL);
    await expect(page.getByTestId("session-row-e2e-session-other")).toBeVisible();
    // e2e-session-other's one call is on an unpriced model - its cost cell
    // carries the info-dot affordance (goal 3) rather than crashing.
    await expect(page.getByTestId("session-row-e2e-session-other").getByTestId("info-dot")).toBeVisible();
    // Only e2e-session-main has a recorded cairn version (fixtures/seed.py);
    // it is the newest in range, so nothing is marked older.
    await expect(page.getByTestId("cairn-version-e2e-session-main")).toHaveText("0.40.0");
    await expect(page.getByTestId("cairn-version-e2e-session-other")).toHaveText("unknown");
    await expect(page.getByTestId(/^cairn-older-/)).toHaveCount(0);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("Drilldown renders the seeded session's agents and transcript, no console errors", async ({ page }) => {
    const { consoleErrors, pageErrors } = trackErrors(page);

    await page.goto("/sessions/e2e-session-main");

    // Scoped to the drill header, not a bare getByText(SESSION_MAIN_LABEL) -
    // the transcript's first prompt bubble renders the same text (see
    // fixtures/seed.py), so an unscoped substring match hits both and trips
    // Playwright's strict-mode violation.
    await expect(page.locator(".drill-title")).toContainText(SESSION_MAIN_LABEL);
    await expect(page.getByTestId("agent-row-main")).toBeVisible();
    await expect(page.getByTestId("agent-row-builder")).toBeVisible();
    await expect(page.getByTestId("agent-row-reviewer")).toBeVisible();
    await expect(page.getByTestId("chat-thread")).toBeVisible();
    // The one call with a seeded transcript entry (AVAILABLE_REQUEST_ID)
    // renders its Read tool-action line and text response.
    await expect(page.getByTestId("chat-thread")).toContainText("Read — src/login.py");
    await expect(page.getByTestId("drill-cairn-version")).toHaveText("cairn 0.40.0");

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("Drilldown of a session with no recorded version reads cairn unknown, no console errors", async ({ page }) => {
    const { consoleErrors, pageErrors } = trackErrors(page);

    await page.goto("/sessions/e2e-session-other");

    await expect(page.getByTestId("drill-cairn-version")).toHaveText("cairn unknown");

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
