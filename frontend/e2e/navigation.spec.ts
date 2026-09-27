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
  await page.goto("/app");
  // Pair the client <Link> click with its navigation (see Flow 6): asserting the URL immediately
  // after the click races the Next router hydration window and can be swallowed on slow CI.
  const prepareLink = page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Prepare" });
  await Promise.all([page.waitForURL(/\/prepare$/), prepareLink.click()]);
  await expect(page).toHaveURL(/\/prepare$/);
});

test("Flow 2: More → Sources", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByRole("button", { name: /More/ }).click();
  // Sources is a client <Link>; pair its click with the navigation (see Flow 6) so a click
  // landing in the router hydration window is not swallowed (URL left on /prepare) on slow CI.
  await Promise.all([
    page.waitForURL(/\/sources$/),
    page.getByRole("menuitem", { name: /Sources/ }).click(),
  ]);
  await expect(page).toHaveURL(/\/sources$/);
});

test("Flow 3: More → Review & Diagnostics", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByRole("button", { name: /More/ }).click();
  await Promise.all([
    page.waitForURL(/\/review$/),
    page.getByRole("menuitem", { name: /Review & Diagnostics/ }).click(),
  ]);
  await expect(page).toHaveURL(/\/review$/);
});

test("Flow 4: Review hub → Agent Inspector", async ({ page }) => {
  await mock(page);
  await page.goto("/review");
  await Promise.all([
    page.waitForURL(/\/review\/agent$/),
    page.getByRole("link", { name: /Agent Inspector/ }).click(),
  ]);
  await expect(page).toHaveURL(/\/review\/agent$/);
});

test("Flow 5: account control → account page", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  // P10B Wave 1: the header account control is a menu button; opening it reveals
  // Account + Settings (Settings is no longer buried under Progress → Manage).
  await page.getByRole("button", { name: "Your account" }).click();
  await expect(page.getByRole("menuitem", { name: "Settings" })).toBeVisible();
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("menuitem", { name: "Your account" }).click(),
  ]);
  await expect(page).toHaveURL(/\/account$/);
});

test("Flow 6: wordmark → home", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  // There is exactly one app-header wordmark (AppShell → Brand → Logo); assert the product
  // contract explicitly: it is visible and points at the app home.
  const wordmark = page.getByRole("link", { name: "Ask4Mo - home" });
  await expect(wordmark).toBeVisible();
  await expect(wordmark).toHaveAttribute("href", "/app");
  // Synchronise the click with the client navigation. Asserting-URL-after-click races the
  // Next.js <Link> hydration window: a click landing before the client handler is ready can be
  // swallowed, leaving the URL on /prepare. Waiting for the navigation concurrently with the
  // click is the deterministic Playwright pattern (no sleep / retry / forced click / raised timeout).
  await Promise.all([
    page.waitForURL(/\/app$/),
    wordmark.click(),
  ]);
  await expect(page).toHaveURL(/\/app$/);
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

test("Mobile (390px): primary bottom nav; supporting routes still reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mock(page);
  await page.goto("/prepare");

  // Bottom nav shows exactly the primary destinations (Opportunities added in P10B Wave 6).
  const bottom = page.locator("nav.fixed");
  await expect(bottom.getByRole("link")).toHaveCount(5);
  for (const label of ["Opportunities", "Prepare", "Practice", "Progress", "History"]) {
    await expect(bottom.getByRole("link", { name: label })).toBeVisible();
  }
  await expect(bottom.getByText("Sources")).toHaveCount(0);

  // Sources reachable via the header More control (no URL typing). Sources is a client <Link>;
  // pair the click with its navigation (see Flow 6) so a click landing in the router hydration
  // window is not swallowed (URL left on /prepare) under slow single-worker CI - the observed
  // failure. Deterministic: no sleep / retry / forced click / raised timeout / weakened assertion.
  await page.getByRole("button", { name: /More/ }).click();
  await Promise.all([
    page.waitForURL(/\/sources$/),
    page.getByRole("menuitem", { name: /Sources/ }).click(),
  ]);
  await expect(page).toHaveURL(/\/sources$/);

  // The account page reachable via the account menu (Settings also lives there).
  await page.getByRole("button", { name: "Your account" }).click();
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("menuitem", { name: "Your account" }).click(),
  ]);
  await expect(page).toHaveURL(/\/account$/);
});
