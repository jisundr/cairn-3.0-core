import { expect, test } from "@playwright/test";

// WarningBanner moved from a standalone top-of-page alert box (with an
// AlertTriangleIcon that once rendered unconstrained at ~800px - the bug
// that motivated adding real-browser e2e at all) into a plain `.kv-row`
// inside Breakdown, on request. No icon and no "View session" link anymore
// - the row is just a name:value fact like Cost/Tokens/Sessions above it,
// so the icon-sizing regression class this spec used to guard no longer
// applies. fixtures/seed.py seeds e2e-session-main with a usage-limit event.
//
// This stays a render-level smoke test - selectedDate-scoping itself
// (Overview.test.tsx's "O2: the usage-limit row scopes to the selected
// day's own events") is covered deterministically in Vitest instead of
// here: repeated local e2e/seed runs accumulate events in the same fixture
// db, so there's no stable count to assert on. Clicking a day at all -
// including a zero-token one - is covered in a real browser instead, in
// chart-click.spec.ts.

test("usage-limit row renders inside Breakdown", async ({ page }) => {
  await page.goto("/");

  const row = page.getByTestId("usage-limit-banner");
  await expect(row).toBeVisible();
  await expect(page.getByTestId("breakdown")).toContainText("Usage limit");
});
