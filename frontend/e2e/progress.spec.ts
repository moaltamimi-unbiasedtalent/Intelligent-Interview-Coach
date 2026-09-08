import { expect, test, type Page } from "@playwright/test";

// Real Next.js → API browser flow for preparation memory, with CONTROLLED
// responses mocked at the network layer (page.route). No backend, no paid calls.

const MEMORIES = {
  memories: [
    { id: 1, category: "recurring_gap", summary: "Executive communication", target_role: "Head of People", source_run_id: null, created_at: null, updated_at: null },
    { id: 2, category: "strength", summary: "Board communication", target_role: null, source_run_id: null, created_at: null, updated_at: null },
  ],
};

async function mockMemory(page: Page, list: unknown = MEMORIES) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_test" }, body: JSON.stringify(body) });
    if (url.includes("/memory")) {
      if (method === "DELETE") return json({ deleted: true, id: 1 });
      return json(list); // GET list
    }
    return json({});
  });
}

test("progress: shows saved preparation memory grouped by friendly labels", async ({ page }) => {
  await mockMemory(page);
  await page.goto("/progress");
  await expect(page.getByText("Executive communication")).toBeVisible();
  await expect(page.getByText("Board communication")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Priorities" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Strengths" })).toBeVisible();
});

test("progress: remove requires confirmation then deletes the item", async ({ page }) => {
  await mockMemory(page);
  await page.goto("/progress");
  await page.getByRole("button", { name: /Remove saved memory: Executive communication/ }).click();
  await expect(page.getByText("Remove this?")).toBeVisible();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByText("Executive communication")).toHaveCount(0);
});

test("progress: empty state when nothing is saved", async ({ page }) => {
  await mockMemory(page, { memories: [] });
  await page.goto("/progress");
  await expect(page.getByText("Nothing saved yet.")).toBeVisible();
});
