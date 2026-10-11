import { expect, test } from "@playwright/test";

// "Refresh now" on the board refetches projects, the filtered tasks list and
// the header's unfiltered tasks list, with visible in-flight feedback. The
// 5s background poll can add requests, so counts are "at least one new".

function card() {
  return {
    project: "a",
    folder: "docs/tasks/2026-01-01-0000-build-refresh-1",
    parent: null,
    kind: "build",
    goal: "A card for the refresh check.",
    key_info: "in progress",
    last_log_date: "2026-01-01",
    last_log_time: "",
    column: "building",
    active: false,
    needs_attention: false,
    done: false,
    sub_tasks: null,
  };
}

test("Refresh now refetches all three queries and shows feedback", async ({ page }) => {
  const projectCalls: string[] = [];
  const taskCalls: string[] = [];
  let delayMs = 0;
  const meta = () => ({ generated_at: new Date().toISOString() });

  await page.route("**/api/projects*", async (route) => {
    projectCalls.push(route.request().url());
    await route.fulfill({
      json: { data: { hostname: "e2e-host", projects: [{ label: "a", parent: null }, { label: "b", parent: null }] }, meta: meta() },
    });
  });
  await page.route("**/api/tasks*", async (route) => {
    taskCalls.push(route.request().url());
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await route.fulfill({ json: { data: [card()], meta: meta() } });
  });

  await page.goto("/kanban?project=a");
  await expect(page.getByTestId("task-card-docs/tasks/2026-01-01-0000-build-refresh-1")).toBeVisible();
  await expect.poll(() => taskCalls.some((u) => !u.includes("project="))).toBe(true);

  const projectsBefore = projectCalls.length;
  const filteredBefore = taskCalls.filter((u) => u.includes("project=a")).length;
  const unfilteredBefore = taskCalls.filter((u) => !u.includes("project=")).length;
  delayMs = 500;

  const button = page.getByRole("button", { name: "Refresh now" });
  await button.click();
  await expect(button).toBeDisabled();
  await expect(button).toBeEnabled();
  await expect(page.locator(".updated-at")).toBeVisible();

  await expect.poll(() => projectCalls.length).toBeGreaterThan(projectsBefore);
  await expect.poll(() => taskCalls.filter((u) => u.includes("project=a")).length).toBeGreaterThan(filteredBefore);
  await expect.poll(() => taskCalls.filter((u) => !u.includes("project=")).length).toBeGreaterThan(unfilteredBefore);
});
