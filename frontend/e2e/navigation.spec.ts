import { expect, test, type Page } from "@playwright/test";

// Navigation discoverability flows. Broad safe API mock so every route renders
// without a backend. No provider calls.

async function mock(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json({
      career_intelligence: true, interview_practice: true, knowledge_base: true,
      evaluation: true, live_interview_enabled: false, agentic_rag: true,
      agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true });
    if (url.includes("/memory/preview")) return json({ target_role: null, load_limit: 10, items: [] });
    if (url.includes("/memory")) return json({ memories: [] });
    if (url.includes("/knowledge")) return json({ sources: [], snapshot: {} });
    if (url.includes("/history")) return json({ interviews: [] });
    return json({});
  });
}

test("Flow 1: home → Prepare", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Prepare" }).click();
  await expect(page).toHaveURL(/\/prepare$/);
});

test("Flow 2: More → Sources", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByRole("button", { name: /More/ }).click();
  await page.getByRole("menuitem", { name: /Sources/ }).click();
  await expect(page).toHaveURL(/\/sources$/);
});

test("Flow 3: More → Review & Diagnostics", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByRole("button", { name: /More/ }).click();
  await page.getByRole("menuitem", { name: /Review & Diagnostics/ }).click();
  await expect(page).toHaveURL(/\/review$/);
});

test("Flow 4: Review hub → Agent Inspector", async ({ page }) => {
  await mock(page);
  await page.goto("/review");
  await page.getByRole("link", { name: /Agent Inspector/ }).click();
  await expect(page).toHaveURL(/\/review\/agent$/);
});

test("Flow 5: account control → Settings", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByRole("link", { name: "Account and settings" }).click();
  await expect(page).toHaveURL(/\/settings$/);
});

test("Flow 6: wordmark → home", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByRole("link", { name: "Intelligent Interview Coach — home" }).click();
  await expect(page).toHaveURL(new RegExp(`${3200}/$|localhost:\\d+/$`));
});

test("Flow 7: keyboard — focus More, open, Escape closes", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  const more = page.getByRole("button", { name: /More/ });
  await more.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(more).toHaveAttribute("aria-expanded", "false");
});

test("Mobile (390px): 4-item bottom nav; supporting routes still reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mock(page);
  await page.goto("/prepare");

  // Bottom nav shows exactly the four primary destinations.
  const bottom = page.locator("nav.fixed");
  await expect(bottom.getByRole("link")).toHaveCount(4);
  for (const label of ["Prepare", "Practice", "Progress", "History"]) {
    await expect(bottom.getByRole("link", { name: label })).toBeVisible();
  }
  await expect(bottom.getByText("Sources")).toHaveCount(0);

  // Sources reachable via the header More control (no URL typing).
  await page.getByRole("button", { name: /More/ }).click();
  await page.getByRole("menuitem", { name: /Sources/ }).click();
  await expect(page).toHaveURL(/\/sources$/);

  // Settings reachable via the account control.
  await page.getByRole("link", { name: "Account and settings" }).click();
  await expect(page).toHaveURL(/\/settings$/);
});
