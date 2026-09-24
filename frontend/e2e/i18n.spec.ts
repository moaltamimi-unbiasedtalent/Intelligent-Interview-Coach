import { expect, test, type Page } from "@playwright/test";

// P3.5 localization smoke. The interface locale comes from the anonymous cookie
// (server-rendered), so we can verify a real 7-language switch without a backend.
// Mocked API returns empty so the page renders; /auth/me is unauthenticated → the
// cookie locale drives the UI.

async function mock(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me"))
      return json({ error: { code: "unauthorized", message: "x", request_id: "r" } }, 401);
    return json({});
  });
}

test("default (no cookie) renders the English interface", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Prepare" }).first()).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

const MATRIX: { code: string; nav: string }[] = [
  { code: "de", nav: "Vorbereiten" },
  { code: "fr", nav: "Préparer" },
  { code: "es", nav: "Preparar" },
  { code: "it", nav: "Prepara" },
  { code: "pt", nav: "Preparar" },
  { code: "nl", nav: "Voorbereiden" },
];

for (const { code, nav } of MATRIX) {
  test(`locale cookie ${code} renders the ${code} interface and sets <html lang>`, async ({ page, baseURL }) => {
    await mock(page);
    await page.context().addCookies([
      { name: "ask4mo_locale", value: code, url: baseURL ?? "http://localhost:3000" },
    ]);
    await page.goto("/");
    await expect(page.getByRole("link", { name: nav }).first()).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", code);
  });
}

test("Settings exposes three independent language controls", async ({ page }) => {
  // Settings is a protected route → provide an authenticated German account. The
  // account's interface_locale is authoritative and drives the UI language.
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me"))
      return json({
        user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
        tier: "basic", status: "active", email_verified: true, providers: ["password"],
        auth_method: "session", capabilities: [], response_detail: "brief",
        interface_locale: "de", conversation_language: "en",
      });
    return json({});
  });
  await page.goto("/settings");
  // German labels for the three distinct controls (interface / conversation / dictation).
  await expect(page.getByText("Oberflächensprache", { exact: true })).toBeVisible();
  await expect(page.getByText("Mo-Gesprächssprache", { exact: true })).toBeVisible();
  await expect(page.getByText("Diktiersprache", { exact: true })).toBeVisible();
});
