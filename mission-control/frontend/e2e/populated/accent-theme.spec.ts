import { expect, test } from "@playwright/test";

// Per-install accent picker (see docs/tasks/.../04-build-per-install-theme/
// REQUIREMENTS.md + PLAN.md). Default accent is design.css's hardcoded
// green (--add: #2f8f49) - every assertion below checks against that exact
// value, not just "changed to something," so a preset that happened to
// also render green wouldn't silently pass. getComputedStyle's
// getPropertyValue on a custom property returns the raw declared string,
// not a normalized rgb() the way it would for a real CSS property.
const DEFAULT_ADD = "#2f8f49";

async function computedAdd(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--add").trim());
}

test("picking a preset changes --add immediately and survives a reload", async ({ page }) => {
  await page.goto("/");
  expect(await computedAdd(page)).toBe(DEFAULT_ADD);

  await page.getByTestId("accent-picker-btn").click();
  await page.getByTestId("accent-picker-option-purple").click();

  const afterPick = await computedAdd(page);
  expect(afterPick).not.toBe(DEFAULT_ADD);

  await page.reload();
  expect(await computedAdd(page)).toBe(afterPick);
});

test("the accent is unaffected by the board's project filter (boardProject)", async ({ page }) => {
  // fixtures/seed.py's own populated project - single-project install, so
  // InstallScopeRow renders a readonly chip rather than its multi-project
  // dropdown (`projects.length > 1`), but the underlying mechanism this
  // guards - App.tsx's `boardProject` URL state - is exactly what
  // REQUIREMENTS names ("doesn't reset or change when boardProject/the
  // Overview project filter changes"), and it's reachable without that
  // dropdown: the same `?project=` param InstallScopeRow's onSelectProject
  // would push, applied here via history + popstate (App.tsx's own
  // client-side listener) so this exercises a live in-session filter
  // change, not just cold-load/reload persistence (already covered above).
  const projectsRes = await page.request.get("/api/projects");
  const { data } = await projectsRes.json();
  const projectLabel: string = data.projects[0].label;

  await page.goto("/kanban");
  await page.getByTestId("accent-picker-btn").click();
  await page.getByTestId("accent-picker-option-teal").click();
  const beforeFilter = await computedAdd(page);
  expect(beforeFilter).not.toBe(DEFAULT_ADD);

  await page.evaluate((label) => {
    window.history.pushState(null, "", `/kanban?project=${encodeURIComponent(label)}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, projectLabel);

  // boardProject really changed (App.tsx's popstate handler picked it up) -
  // otherwise this test would trivially pass by never having changed the
  // filter at all.
  await expect(page).toHaveURL(new RegExp(`project=${encodeURIComponent(projectLabel)}`));

  expect(await computedAdd(page)).toBe(beforeFilter);
  expect(await page.evaluate(() => document.documentElement.dataset.accentTheme)).toBe("teal");
});
