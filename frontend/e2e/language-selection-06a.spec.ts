import { expect, test, type Page } from "@playwright/test";

/**
 * 06A (REQ-LANG-14, LG-14): the Candidate language selectors offer exactly the seven active languages and never
 * Russian; a stored or cookie `ru` falls back to the default interface language without touching geography.
 * Mocked API only (no backend, no provider call).
 */
const SEVEN = ["en", "de", "fr", "es", "it", "pt", "nl"];

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
    coaching_style: "balanced", career_geography: "de", target_role: "",
    onboarding_completed: true, onboarding_step: 0, ...over,
  };
}

async function mock(page: Page, acct: Record<string, unknown> | null, patches: Record<string, unknown>[] = []) {
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = req.url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_06a" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return acct ? json(acct) : json({ error: { code: "unauthorized", message: "x", request_id: "r" } }, 401);
    if (url.includes("/auth/preferences") && req.method() === "PATCH") {
      patches.push(req.postDataJSON());
      return json(acct ?? {});
    }
    if (url.includes("/capabilities")) {
      return json({ active_candidate_locales: SEVEN, default_locale: "en", career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true });
    }
    return json({});
  });
}

test("Settings offers exactly seven interface and seven conversation languages, no Russian", async ({ page }) => {
  await mock(page, account());
  await page.goto("/settings");
  const iface = page.getByLabel("Interface language");
  const conv = page.getByLabel("Mo conversation language");
  await expect(iface).toBeVisible();
  for (const sel of [iface, conv]) {
    expect(await sel.locator("option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value))).toEqual(SEVEN);
    await expect(sel.locator("option", { hasText: "Русский" })).toHaveCount(0);
  }
});

test("the header language menu lists seven languages and no Russian", async ({ page }) => {
  await mock(page, null);
  await page.goto("/app");
  await page.getByTestId("language-menu-button").click();
  await expect(page.getByRole("menuitemradio")).toHaveCount(7);
  await expect(page.getByRole("menuitemradio", { name: /Русский/ })).toHaveCount(0);
});

test("a stored Russian preference falls back to English for display and is never re-saved", async ({ page }) => {
  const patches: Record<string, unknown>[] = [];
  await mock(page, account({ interface_locale: "ru", conversation_language: "ru" }), patches);
  await page.goto("/settings");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByLabel("Interface language")).toHaveValue("en");
  await expect(page.getByLabel("Mo conversation language")).toHaveValue("en");
  expect(patches).toEqual([]); // display fallback only: no write, so geography and the stored value are untouched
});

test("a legacy Russian locale cookie renders the English interface", async ({ page, baseURL }) => {
  await mock(page, null);
  await page.context().addCookies([{ name: "ask4mo_locale", value: "ru", url: baseURL ?? "http://localhost:3000" }]);
  await page.goto("/app");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("link", { name: "Prepare" }).first()).toBeVisible();
});

test("choosing a conversation language sends only that field (geography untouched)", async ({ page }) => {
  const patches: Record<string, unknown>[] = [];
  await mock(page, account(), patches);
  await page.goto("/settings");
  await page.getByLabel("Mo conversation language").selectOption("es");
  await expect.poll(() => patches.length).toBeGreaterThan(0);
  expect(patches[0]).toEqual({ conversation_language: "es" });
  expect(JSON.stringify(patches)).not.toContain("career_geography");
});
