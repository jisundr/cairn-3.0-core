import { expect, test } from "@playwright/test";

// Against the "cold-start" webServer: a project root with no `.cairn/
// tokens.db` at all - server.py's Overview.tsx renders its
// no-sessions-yet empty state instead of the loaded panels.

test("renders Overview's empty state instead of loaded panels, no console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  const pageErrors: Error[] = [];
  page.on("pageerror", (error) => pageErrors.push(error));

  await page.goto("/");

  await expect(page.getByTestId("overview-empty")).toBeVisible();
  await expect(page.getByTestId("overview-empty")).toContainText("No sessions captured yet");
  await expect(page.getByTestId("usage-limit-banner")).toHaveCount(0);
  await expect(page.getByTestId("overview-disconnected")).toHaveCount(0);

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
