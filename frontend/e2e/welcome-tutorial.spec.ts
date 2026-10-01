import { expect, test, type Page } from "@playwright/test";

// P10B-W9.5 - Post-onboarding Welcome + Tutorial v2 first-run journey (PF-11/PF-12).
// Deterministic network mock; onboarding completion flips to completed so /app is no longer gated.

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
    coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: false, onboarding_step: 0, ...over,
  };
}

async function mock(page: Page, opts: { userId?: number; startCompleted?: boolean } = {}) {
  const state = { completed: opts.startCompleted ?? false, userId: opts.userId ?? 1 };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/onboarding") && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      if (body?.complete === true) state.completed = true;
      return json(account({ user_id: state.userId, onboarding_completed: state.completed }));
    }
    if (path.endsWith("/auth/preferences")) return json(account({ user_id: state.userId, onboarding_completed: state.completed }));
    if (path.endsWith("/auth/me")) return json(account({ user_id: state.userId, onboarding_completed: state.completed }));
    if (path.endsWith("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    if (path.includes("/opportunities")) return json({ opportunities: [] });
    if (path.includes("/memory") || path.includes("/history") || path.includes("/interviews") || path.includes("/progress")) return json({ sessions: [], interviews: [], memories: [], answers_evaluated: 0, recent_interviews: [] });
    return json({});
  });
  return state;
}

async function completeOnboarding(page: Page) {
  await page.goto("/onboarding");
  await page.getByRole("button", { name: "Get started" }).click();
  for (let i = 0; i < 5; i++) await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Enter Ask4Mo" }).click();
  // Intentional Welcome handoff (not dumped into /app).
  await expect(page.getByRole("heading", { name: /Mo is ready/i })).toBeVisible();
}

test("onboarding completes to an intentional Welcome, then the tour starts and shows Opportunity before Prepare", async ({ page }) => {
  await mock(page);
  await completeOnboarding(page);

  // Welcome offers all three paths (none mandatory).
  await expect(page.getByRole("button", { name: /Create your first opportunity/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Take the quick tour/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Go to your workspace/i })).toBeVisible();

  // Take the tour -> enters /app and Tutorial v2 auto-starts.
  await page.getByRole("button", { name: /Take the quick tour/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  const tour = page.getByRole("dialog");
  await expect(tour.getByText(/Welcome to your workspace/i)).toBeVisible();
  await expect(page.getByText("1 of 9")).toBeVisible();

  // Opportunity step comes before Prepare (step 2 of the v2 journey).
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText(/Keep one job together/i)).toBeVisible();
  await expect(page.getByText("2 of 9")).toBeVisible();

  // Dismiss and arrive in the product; a reload does NOT restart onboarding.
  await page.getByRole("button", { name: "Skip" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page).toHaveURL(/\/app$/); // not bounced back to /onboarding
});

test("onboarding Welcome -> Create your first opportunity hands off to the existing create flow", async ({ page }) => {
  await mock(page);
  await completeOnboarding(page);
  await page.getByRole("button", { name: /Create your first opportunity/i }).click();
  await expect(page).toHaveURL(/\/opportunities\?create=1$/);
  await expect(page.getByRole("heading", { name: "Create an opportunity" })).toBeVisible();
});

test("shared browser: Account A's dismissed tour does not suppress Account B's tour", async ({ page }) => {
  // Both accounts already onboarded (so /app is reachable); the tour state is account-scoped.
  const state = await mock(page, { userId: 1, startCompleted: true });
  await page.goto("/app");
  // Account 1 gets the first-visit invitation and dismisses it.
  await expect(page.getByRole("dialog", { name: /Welcome to Ask4Mo/i })).toBeVisible();
  await page.getByRole("button", { name: /Maybe later/i }).click();
  await expect(page.getByRole("dialog", { name: /Welcome to Ask4Mo/i })).toHaveCount(0);

  // Switch to Account 2 on the SAME browser -> its own fresh invitation appears.
  state.userId = 2;
  await page.reload();
  await expect(page.getByRole("dialog", { name: /Welcome to Ask4Mo/i })).toBeVisible();
});
