import { expect, type Page, test } from "@playwright/test";

// Board layout in a real browser (jsdom has no layout): skeleton loader,
// horizontal board scroll at a phone width, and panes that reach the window
// bottom on a tall and a short viewport. Every test sets its viewport
// explicitly - headless Chrome will not go narrow on its own.

const STAGES = ["parent_tasks", "scoping", "awaiting_approval", "planned", "building", "in_review", "blocked", "done"];

function card(i: number, column: string) {
  return {
    project: "e2e",
    folder: `docs/tasks/2026-01-01-0000-build-layout-${column}-${i}`,
    parent: null,
    kind: "build",
    goal: "A card with enough text to give the column pane real height in a layout check.",
    key_info: "in progress",
    last_log_date: "2026-01-01",
    last_log_time: "",
    column,
    active: false,
    needs_attention: false,
    done: column === "done",
    sub_tasks: null,
  };
}

// Many cards per column, so every column's pane overflows vertically.
async function mockTasks(page: Page, delayMs = 0) {
  const data = STAGES.flatMap((c) => Array.from({ length: 30 }, (_, i) => card(i, c)));
  await page.route("**/api/tasks*", async (route) => {
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await route.fulfill({
      json: { data, meta: { generated_at: new Date().toISOString() } },
    });
  });
}

async function openBoard(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await mockTasks(page);
  await page.goto("/kanban");
  await expect(page.locator(".kanban-column")).toHaveCount(8);
  await expect(page.getByTestId("kanban-skel")).toHaveCount(0);
}

test.describe("kanban board layout", () => {
  test("375x800: board scrolls sideways, columns stay readable, page does not, columns scroll vertically", async ({
    page,
  }) => {
    await openBoard(page, 375, 800);
    const board = page.locator(".kanban-columns");

    expect(await board.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
    const widths = await page
      .locator(".kanban-column")
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().width));
    for (const w of widths) expect(w).toBeGreaterThanOrEqual(240);

    const pageOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(pageOverflow).toBeLessThanOrEqual(4);

    await board.evaluate((el) => {
      el.scrollLeft = el.scrollWidth;
    });
    const lastRight = await page
      .locator(".kanban-column")
      .last()
      .evaluate((el) => el.getBoundingClientRect().right);
    expect(lastRight).toBeLessThanOrEqual(375 + 1);

    const cards = page.locator(".kanban-column-cards").last();
    expect(await cards.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
  });

  for (const [width, height] of [
    [1280, 900],
    [1280, 500],
  ]) {
    test(`${width}x${height}: no page scroll, panes end a header-pad gap above the window bottom`, async ({ page }) => {
      await openBoard(page, width, height);

      const noPageScroll = await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight);
      expect(noPageScroll).toBe(true);

      const pad = await page.locator("header.app").evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom));
      expect(pad).toBe(16);
      const gaps = await page
        .locator(".kanban-column-cards")
        .evaluateAll((els) => els.map((el) => window.innerHeight - el.getBoundingClientRect().bottom));
      expect(gaps).toHaveLength(8);
      for (const gap of gaps) expect(Math.abs(gap - pad)).toBeLessThanOrEqual(1);
    });
  }

  test("2160x1000: all eight columns are visible without sideways scroll", async ({ page }) => {
    await openBoard(page, 2160, 1000);
    const board = page.locator(".kanban-columns");
    expect(await board.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    const rights = await page
      .locator(".kanban-column")
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().right));
    for (const r of rights) expect(r).toBeLessThanOrEqual(2160);
    // 1280 stays narrower than eight 248px columns (about 2096px with gaps), so it scrolls sideways there.
    await page.setViewportSize({ width: 1280, height: 900 });
    expect(await board.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
  });

  test("375x800: every column shows skeleton cards until the first tasks response, then none", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await mockTasks(page, 800);
    await page.goto("/kanban");

    await expect(page.locator(".kanban-column")).toHaveCount(8);
    for (const col of await page.locator(".kanban-column").all()) {
      await expect(col.getByTestId("kanban-skel").first()).toBeVisible();
    }
    await expect(page.getByTestId("kanban-skel")).toHaveCount(0);
    await expect(page.getByTestId("kanban-see-more-done")).toBeVisible();
  });
});
