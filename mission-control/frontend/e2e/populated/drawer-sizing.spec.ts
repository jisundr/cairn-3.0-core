import { expect, test } from "@playwright/test";

// Goal 11 / Success criteria (PRD §6.7): the task-detail overlay is a
// centered modal, not a side drawer, and its content fills the modal's own
// width at every viewport the old drawer supported - no dead space, no
// horizontal scrollbar. jsdom (vitest) never evaluates `design.css`'s media
// query or box-model math at all, so nothing but a real browser can catch a
// regression here (the same gap layout-sanity.spec.ts's own icon-sizing
// checks exist to close). Opens the drawer on seed.py's own fixture task
// folder, per-test viewport, and reads the details tab's own scroll
// dimensions.

const FIXTURE_CARD = "task-card-docs/tasks/2026-01-01-0000-research-e2e-drawer-fixture";

async function openDrawer(page: import("@playwright/test").Page) {
  await page.goto("/kanban");
  await page.getByTestId(FIXTURE_CARD).click();
  const drawer = page.getByTestId("task-drawer");
  await expect(drawer).toBeVisible();
  return drawer;
}

async function hasNoHorizontalOverflow(page: import("@playwright/test").Page): Promise<boolean> {
  return page.evaluate(() => {
    const el = document.querySelector(".drawer-body");
    if (!el) return false;
    // A few px of tolerance for scrollbar/subpixel rounding, not a wrong rule.
    return el.scrollWidth <= el.clientWidth + 1;
  });
}

test("modal content has no horizontal overflow on a 1280px desktop viewport", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openDrawer(page);

  expect(await hasNoHorizontalOverflow(page)).toBe(true);
});

test("modal content has no horizontal overflow on a 700px narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 800 });
  await openDrawer(page);

  expect(await hasNoHorizontalOverflow(page)).toBe(true);
});
