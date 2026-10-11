import { expect, type Page, test } from "@playwright/test";

// General-case coverage for the bug class the WarningBanner icon regression
// (warning-banner.spec.ts) was one instance of: an SVG or element that
// renders without the CSS constraint its design assumes doesn't show up in
// any mockup or jsdom unit test, only in a real browser's layout. Runs the
// same two checks across every loaded page this fixture can reach, rather
// than re-asserting only the one icon already covered above.

const MAX_ICON_PX = 48;

async function assertNoOversizedSvg(page: Page) {
  // `.recharts-surface` (goals 3-6's charts) is deliberately as large as its
  // panel - only an *icon* svg growing unconstrained is the bug class this
  // guards against, the same distinction the WarningBanner regression this
  // check generalizes from already draws (a chart canvas, unlike an icon,
  // has no fixed intrinsic size to fall back to).
  const boxes = await page.locator("svg:not(.recharts-surface)").evaluateAll((nodes) =>
    nodes.map((n) => {
      const r = (n as SVGSVGElement).getBoundingClientRect();
      return { width: r.width, height: r.height };
    }),
  );
  for (const box of boxes) {
    expect(box.width).toBeLessThanOrEqual(MAX_ICON_PX);
    expect(box.height).toBeLessThanOrEqual(MAX_ICON_PX);
  }
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth - doc.clientWidth;
  });
  // A few px of tolerance for scrollbar/subpixel rounding, not a growing
  // layout - real overflow (a fixed-width table, an unconstrained image)
  // shows up as tens or hundreds of px, not this.
  expect(overflow).toBeLessThanOrEqual(4);
}

test.describe("layout sanity: no SVG or page exceeds a sane bounding box", () => {
  test("Overview", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("chart-bars")).toBeVisible();
    await assertNoOversizedSvg(page);
    await assertNoHorizontalOverflow(page);
  });

  test("Sessions List", async ({ page }) => {
    await page.goto("/sessions");
    await expect(page.getByTestId("sessions-table")).toBeVisible();
    await assertNoOversizedSvg(page);
    await assertNoHorizontalOverflow(page);
  });

  test("Drilldown", async ({ page }) => {
    await page.goto("/sessions/e2e-session-main");
    await expect(page.getByTestId("chat-thread")).toBeVisible();
    await assertNoOversizedSvg(page);
    await assertNoHorizontalOverflow(page);
  });
});
