import { expect, test, type Page } from "@playwright/test";

/**
 * 06H (REQ-LANG-11/13/14): the language selectors reflect the server's activation decision.
 * Hosted mode with no qualified language offers nothing and says so; a qualified subset is offered alone; development labels
 * every language UNQUALIFIED. Mocked API only (no backend, no provider call); the server enforces the same rule on every
 * new activity (tests/test_language_activation_06h.py).
 */
const SEVEN = ["en", "de", "fr", "es", "it", "pt", "nl"];

function account() {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
    coaching_style: "balanced", career_geography: "de", target_role: "",
    onboarding_completed: true, onboarding_step: 0,
  };
}

async function mock(page: Page, caps: Record<string, unknown>) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_06h" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    if (url.includes("/capabilities")) {
      return json({ default_locale: "en", career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, ...caps });
    }
    return json({});
  });
}

test("hosted with no qualified language: Settings selectors are disabled and a clear unavailable note is shown", async ({ page }) => {
  await mock(page, { active_candidate_locales: [], unqualified_locales: [], qualified_locales: [], no_language_available: true, language_activation_mode: "enforced" });
  await page.goto("/settings");
  await expect(page.getByTestId("language-none-available").first()).toBeVisible();
  await expect(page.getByLabel("Interface language")).toBeDisabled();
  await expect(page.getByLabel("Mo conversation language")).toBeDisabled();
  await expect(page.getByLabel("Interface language").locator("option")).toHaveCount(0);
});

test("hosted with one qualified language: only that language is offered, unlabelled", async ({ page }) => {
  await mock(page, { active_candidate_locales: ["de"], unqualified_locales: [], qualified_locales: ["de"], language_activation_mode: "enforced" });
  await page.goto("/settings");
  const conv = page.getByLabel("Mo conversation language");
  await expect(conv).toBeVisible();
  await expect(conv.locator("option")).toHaveCount(1);
  await expect(conv.locator("option")).toHaveAttribute("value", "de");
  await expect(page.getByTestId("language-none-available")).toHaveCount(0);
});

test("development labels every language UNQUALIFIED in the selectors and the header menu", async ({ page }) => {
  await mock(page, { active_candidate_locales: SEVEN, unqualified_locales: SEVEN, qualified_locales: [], language_activation_mode: "labelled" });
  await page.goto("/settings");
  const options = page.getByLabel("Interface language").locator("option");
  await expect(options).toHaveCount(7);
  await expect(options.first()).toContainText("Unqualified");
  await page.getByTestId("language-menu-button").click();
  await expect(page.getByRole("menuitemradio")).toHaveCount(7);
  await expect(page.getByTestId("language-unqualified-de")).toBeVisible();
});

test("hosted with no qualified language: the header menu offers no choice and says so", async ({ page }) => {
  await mock(page, { active_candidate_locales: [], unqualified_locales: [], no_language_available: true, language_activation_mode: "enforced" });
  await page.goto("/settings");
  await page.getByTestId("language-menu-button").click();
  await expect(page.getByTestId("language-none-available").first()).toBeVisible();
  await expect(page.getByRole("menuitemradio")).toHaveCount(0);
});
