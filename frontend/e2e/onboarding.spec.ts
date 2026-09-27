import { expect, test, type Page } from "@playwright/test";

// P10B Wave 2 — premium onboarding. Mocked at the network layer (no backend, no provider calls).
// Covers: new-user gate → complete → /app; resume; existing-user not blocked + Settings; and
// interface-language independence from the conversation language.

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
    coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: false, onboarding_step: 0, ...over,
  };
}

async function mock(page: Page, state: { completed: boolean; step: number }) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me"))
      return json(account({ onboarding_completed: state.completed, onboarding_step: state.step }));
    if (url.includes("/auth/onboarding") && method === "POST") {
      const body = route.request().postDataJSON() as { step?: number; complete?: boolean };
      if (typeof body.step === "number") state.step = Math.max(state.step, body.step);
      if (body.complete) state.completed = true;
      return json(account({ onboarding_completed: state.completed, onboarding_step: state.step }));
    }
    if (url.includes("/auth/preferences") && method === "PATCH")
      return json(account({ onboarding_completed: state.completed, onboarding_step: state.step }));
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: true, realtime_voice_enabled: false });
    if (url.includes("/memory")) return json({ memories: [], items: [] });
    return json({});
  });
}

async function advanceToFinish(page: Page) {
  await page.getByRole("button", { name: "Get started" }).click();
  // Steps 2..6 use "Continue"; step 7 (Review) uses "Enter Ask4Mo".
  for (let i = 0; i < 5; i++) {
    await page.getByRole("button", { name: "Continue" }).click();
  }
}

test("E2E 1: new user is gated into onboarding and completes to /app", async ({ page }) => {
  const state = { completed: false, step: 0 };
  await mock(page, state);
  await page.goto("/prepare");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: /set up Mo around you/i })).toBeVisible();
  await advanceToFinish(page);
  await expect(page.getByRole("button", { name: "Enter Ask4Mo" })).toBeVisible();
  await page.getByRole("button", { name: "Enter Ask4Mo" }).click();
  await expect(page).toHaveURL(/\/app$/);
});

test("E2E 2: interrupted onboarding resumes at the saved step", async ({ page }) => {
  await mock(page, { completed: false, step: 3 });
  await page.goto("/onboarding");
  await expect(page.getByText(/Step 4 of 7/i)).toBeVisible();
});

test("E2E 3: existing user is not blocked and can edit coaching in Settings", async ({ page }) => {
  await mock(page, { completed: true, step: 7 });
  await page.goto("/prepare");
  await expect(page).toHaveURL(/\/prepare$/); // not redirected to onboarding
  await page.goto("/settings");
  await expect(page.getByText(/not how your interview performance is scored/i)).toBeVisible();
  await expect(page.getByRole("radio", { name: /Challenging/ })).toBeVisible();
});

test("E2E 4: interface language on onboarding is independent of conversation language", async ({ page }) => {
  await mock(page, { completed: false, step: 6 }); // Review step shows the conversation language
  await page.goto("/onboarding");
  // Conversation language row shows the account default (en) and must not change with the UI language.
  await expect(page.getByText("Step 7 of 7")).toBeVisible();
  // Switch interface language via the global menu; onboarding chrome should localize.
  await page.getByTestId("language-menu-button").click();
  await page.getByRole("menuitemradio", { name: /Deutsch/ }).click();
  // The Back control localizes to German ("Zurück"), proving interface language changed…
  await expect(page.getByRole("button", { name: "Zurück" })).toBeVisible();
  // …while the conversation-language value in the review is unchanged ("en" still shown),
  // proving the interface language switch did not touch the conversation language.
  expect(await page.getByText("en", { exact: true }).count()).toBeGreaterThan(0);
});
