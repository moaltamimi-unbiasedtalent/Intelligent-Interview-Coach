import { expect, test, type Page } from "@playwright/test";

// Guided tour + Help. Real Next.js browser flow; the API is mocked at the network layer
// so no backend and no paid calls are needed. Each test gets a fresh context (clean
// tutorial state), so the first-visit invitation is eligible.

async function mockApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: "application/json", headers: { "x-request-id": "req_tut" }, body: JSON.stringify(body) });
    if (url.includes("/knowledge/sources")) return json({ sources: [] });
    if (url.includes("/knowledge/snapshot")) return json({ documents: 0, chunks: 0, document_types: 0 });
    if (url.includes("/progress")) return json({ interviews_completed: 0, answers_evaluated: 0, average_practice_score: null, most_common_improvement_area: null, average_answer_seconds: null, recent_interviews: [] });
    if (url.includes("/history/interviews")) return json({ interviews: [] });
    if (url.includes("/memory")) return json({ memories: [] });
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: true });
    return json({});
  });
}

test("first visit: invitation → start → advance → dismiss → stays dismissed after refresh", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  const invite = page.getByRole("dialog", { name: "Welcome to Ask4Mo" });
  await expect(invite).toBeVisible();

  await page.getByRole("button", { name: "Start tour" }).click();
  await expect(page.getByText("Start with your goal")).toBeVisible();
  await expect(page.getByText("1 of 12")).toBeVisible();

  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Give Mo the right context")).toBeVisible();
  await expect(page).toHaveURL(/\/prepare/); // route-aware

  await page.getByRole("button", { name: "Skip" }).click();
  await expect(page.getByText("Give Mo the right context")).toHaveCount(0);

  await page.goto("/");
  await expect(page.getByRole("dialog", { name: "Welcome to Ask4Mo" })).toHaveCount(0);
});

test("Help: search, sections, and replaying the tour", async ({ page }) => {
  await mockApi(page);
  await page.goto("/help");
  await expect(page.getByRole("heading", { name: "Troubleshooting" })).toBeVisible();

  // Local search filters (assert on a Progress-specific article + that others drop out).
  await page.getByLabel("Search help").fill("metrics mean");
  await expect(page.getByRole("heading", { name: "What the metrics mean" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Troubleshooting" })).toHaveCount(0);
  await page.getByLabel("Search help").fill("");

  // Replay the tour from Help.
  await page.getByRole("button", { name: "Take the tour" }).click();
  await expect(page.getByText("Start with your goal")).toBeVisible();
});

test("contextual help: Sources links to the Sources help section", async ({ page }) => {
  await mockApi(page);
  await page.goto("/sources");
  await page.getByRole("link", { name: "How Ask4Mo uses evidence" }).click();
  await expect(page).toHaveURL(/\/help#sources$/);
});
