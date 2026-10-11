import { expect, test } from "@playwright/test";
import { formatDateLabel } from "../../src/lib/format";

// Regression coverage for a real click-through bug: TokensPerDayChart's
// visible segments render `height: Math.max(height, 0)` - a zero-token
// day's segments are all 0-height, which Playwright (correctly) refuses to
// click as "not visible." The fix added `ColumnHitArea`, a full-plot-height
// invisible rect (Recharts' `background` prop on the baseline `<Bar>`,
// sized off the plot area rather than that day's own value) carrying the
// `chart-bar-${date}` testid instead. fixtures/seed.py clusters all its
// session data within the last 2 days of "now" - the 30-day Trend window's
// oldest (leftmost) bar is reliably a zero-token day, so clicking it is
// exactly the case a visible-bar-only hit target would fail on.

test("a zero-token day (the range's oldest bar) is still clickable", async ({ page }) => {
  await page.goto("/");

  const bars = page.getByTestId(/^chart-bar-/);
  const oldest = bars.first();
  await expect(oldest).toBeVisible();

  await oldest.click();

  // Breakdown switches from the range-wide "Last 30 days" label to the
  // clicked day's own date - the click reached the day, not nothing.
  const date = await oldest.getAttribute("data-testid").then((t) => t!.replace("chart-bar-", ""));
  await expect(page.getByTestId("install-scope-date-chip")).toContainText(formatDateLabel(date));
  await expect(page.getByTestId("breakdown-sessions")).toContainText("0");
});
