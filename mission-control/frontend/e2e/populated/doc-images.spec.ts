import { expect, test } from "@playwright/test";

// Task-doc images in a real browser: seed.py's fixture folder has NOTES.md
// with `./x.png` and `mockups/y.webp`, served by /api/tasks/asset. jsdom
// never fetches or decodes an image, so only here can "the image actually
// rendered" (naturalWidth > 0) be checked, along with the route refusing
// a path that leaves the folder.

const FIXTURE_FOLDER = "docs/tasks/2026-01-01-0000-research-e2e-drawer-fixture";
const FIXTURE_CARD = `task-card-${FIXTURE_FOLDER}`;

test("relative images in a task doc render in the Docs tab", async ({ page }) => {
  await page.goto("/kanban");
  await page.getByTestId(FIXTURE_CARD).click();
  await expect(page.getByTestId("task-drawer")).toBeVisible();
  await page.getByTestId("drawer-tab-docs").click();
  await page.getByTestId("docs-file-NOTES.md").click();

  const images = page.locator(".doc-render img");
  await expect(images).toHaveCount(2);
  await expect
    .poll(() => images.evaluateAll((els) => els.map((el) => (el as HTMLImageElement).naturalWidth)))
    .toEqual([2, 2]);
  await expect(page.getByTestId("doc-img-missing")).toHaveCount(0);
});

test("the asset route refuses a path that leaves the task folder", async ({ page }) => {
  const projects = await (await page.request.get("/api/projects")).json();
  const project = projects.data.projects[0].label as string;
  const query = new URLSearchParams({ project, folder: FIXTURE_FOLDER, path: "../STATE.md" });
  const refused = await page.request.get(`/api/tasks/asset?${query}`);
  expect(refused.status()).toBe(404);

  query.set("path", "x.png");
  const served = await page.request.get(`/api/tasks/asset?${query}`);
  expect(served.status()).toBe(200);
  expect(served.headers()["content-type"]).toBe("image/png");
  expect(served.headers()["x-content-type-options"]).toBe("nosniff");
});
