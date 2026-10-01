import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";

/**
 * P10B-W9.9 - core journey reachability, Data & privacy / Trust discoverability, and layout checks on the
 * polished surfaces. Deterministic network mock; no backend, model or paid/live provider.
 */

const T = (locale: string, k: string) => translate(locale as never, k);

function account(locale: string) {
  return {
    user_id: 1, email: "u@example.com", display_name: "Sam", platform_role: "user", tier: "basic", status: "active",
    email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], response_detail: "brief",
    interface_locale: locale, conversation_language: "en", coaching_style: "balanced", career_geography: "de",
    target_role: "PM", onboarding_completed: true, onboarding_step: 0,
  };
}

async function mock(page: Page, locale = "en") {
  await page.addInitScript(() => {
    try { localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() })); } catch { /* ignore */ }
  });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^.*\/api\/v1/, "");
    const j = (b: unknown) => route.fulfill({ status: 200, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (path === "/auth/me") return j(account(locale));
    if (path === "/capabilities") return j({ agent_coach_enabled: true, realtime_voice_enabled: false, company_research_enabled: false, career_intelligence: true, interview_practice: true });
    if (path === "/opportunities") return j({ opportunities: [{ id: 1, title: "Senior PM - Acme", target_role: "Senior PM", status: "active" }] });
    if (path === "/history/interviews") return j({ interviews: [{ id: 3, target_role: "Senior PM", status: "completed", questions: 5, created_at: "2026-09-01T10:00:00Z" }] });
    if (path === "/progress") return j({ interviews_completed: 1, answers_evaluated: 5, average_practice_score: 70, most_common_improvement_area: null, average_answer_seconds: 90, recent_interviews: [] });
    if (path === "/memory") return j({ memories: [] });
    if (path === "/documents") return j({ documents: [] });
    if (path === "/shares/mine") return j({ shares: [] });
    if (path === "/workspaces") return j({ workspaces: [], invited: [] });
    return j({});
  });
}

test("core journey stays reachable and Data & privacy / Trust are discoverable from the account menu", async ({ page }) => {
  await mock(page);
  await page.goto("/app");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const nav = page.getByRole("navigation").first();
  for (const [label, url] of [["Opportunities", /\/opportunities/], ["Prepare", /\/prepare/], ["Practice", /\/practice/], ["Progress", /\/progress/], ["History", /\/history/]] as const) {
    await nav.getByRole("link", { name: label }).click();
    await expect(page).toHaveURL(url);
  }
  await page.getByRole("button", { name: T("en", "nav.account") }).click();
  await page.getByRole("menuitem", { name: T("en", "settings.title") }).click();
  await expect(page).toHaveURL(/\/settings/);
  await page.getByRole("button", { name: T("en", "nav.account") }).click();
  await page.getByRole("menuitem", { name: T("en", "trustUx.navDataPrivacy") }).click();
  await expect(page).toHaveURL(/\/account\/data/);
  await expect(page.getByTestId("data-privacy-center")).toBeVisible();
  await page.getByRole("button", { name: T("en", "nav.account") }).click();
  await page.getByRole("menuitem", { name: T("en", "trustUx.navTrust") }).click();
  await expect(page).toHaveURL(/\/trust/);
  await expect(page.getByTestId("trust-group-ai")).toBeVisible();
});

test("Home composer button never wraps and aligns with the cards", async ({ page }) => {
  await mock(page);
  await page.goto("/app");
  const btn = page.getByRole("button", { name: T("en", "home.askMo") });
  const box = await btn.boundingBox();
  expect(box!.height).toBeLessThan(60); // single line (it wrapped to ~2 lines before)
});

for (const locale of ["de", "ru"]) {
  test(`${locale}: polished surfaces have no horizontal overflow at 390px in light and dark`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mock(page, locale);
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      for (const path of ["/app", "/settings", "/history", "/trust", "/account", "/account/data"]) {
        await page.goto(path);
        await expect(page.locator("main, body").first()).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `${locale} ${scheme} ${path}`).toBeLessThanOrEqual(0);
      }
    }
  });
}
