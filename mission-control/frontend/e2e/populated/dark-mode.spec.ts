import { expect, test } from "@playwright/test";

// design.css's `@media (prefers-color-scheme: dark)` block was only ever
// checked by a static grep audit (PLAN.md's Commit 6), never a real
// rendered pass - this confirms each loaded page still renders (and picks
// up the dark palette) without console errors under an emulated dark
// color scheme, against the same populated fixture the light-mode tests
// use.

test.use({ colorScheme: "dark" });

test("Overview renders under prefers-color-scheme: dark, no console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/");
  await expect(page.getByTestId("chart-bars")).toBeVisible();

  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  // design.css's dark block repoints `--bg` from #fdfdfb (light) to
  // #14140f (dark) - matching that exact color, not just "isn't the light
  // one," proves the media query actually applied rather than merely
  // being present in the stylesheet.
  expect(bg).toBe("rgb(20, 20, 15)");

  expect(consoleErrors).toEqual([]);
});

test("Sessions List renders under prefers-color-scheme: dark, no console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/sessions");
  await expect(page.getByTestId("sessions-table")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("Drilldown renders under prefers-color-scheme: dark, no console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/sessions/e2e-session-main");
  await expect(page.getByTestId("chat-thread")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
