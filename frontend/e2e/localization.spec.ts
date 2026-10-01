import { expect, test, type Page } from "@playwright/test";

/**
 * P10B-W9.6 — full-app localization E2E.
 *
 * Proves the wave's core promise: choosing an interface language localizes EVERY Ask4Mo-owned
 * candidate-facing string across the product (not just navigation), that the interface language is
 * independent of the Mo conversation language, that error/degraded chrome is localized, and that
 * user/source content is NEVER translated.
 *
 * These are deterministic UI tests: the backend is fully stubbed, so no provider/paid call occurs.
 * The interface locale is driven by the account preference (`interface_locale`) for authenticated
 * routes and by the anonymous `ask4mo_locale` cookie for public routes (server-rendered).
 */

type AccountOverrides = Record<string, unknown>;

function deAccount(over: AccountOverrides = {}) {
  return {
    user_id: 1,
    email: "kandidat@example.com",
    display_name: null,
    platform_role: "user",
    tier: "basic",
    status: "active",
    email_verified: true,
    providers: ["password"],
    auth_method: "session",
    capabilities: [],
    response_detail: "brief",
    interface_locale: "de",
    conversation_language: "en",
    onboarding_completed: true,
    ...over,
  };
}

/** Stub /api/v1 with an authenticated account plus optional per-endpoint responders. */
async function mockAuthed(
  page: Page,
  account: AccountOverrides,
  responders: Array<{ match: string; status?: number; body: unknown }> = [],
) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        headers: { "x-request-id": "req_e2e" },
        body: JSON.stringify(body),
      });
    if (url.includes("/auth/me")) return json(account);
    for (const r of responders) {
      if (url.includes(r.match)) return json(r.body, r.status ?? 200);
    }
    return json({});
  });
}

/** Stub /api/v1 as unauthenticated (for public, server-rendered routes). */
async function mockPublic(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        headers: { "x-request-id": "req_e2e" },
        body: JSON.stringify(body),
      });
    if (url.includes("/auth/me"))
      return json({ error: { code: "unauthorized", message: "x", request_id: "r" } }, 401);
    return json({});
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// E1 — German core journey (multiple surfaces localized, not just nav).
// ─────────────────────────────────────────────────────────────────────────────
test("E1: a German account sees German chrome across home and progress", async ({ page }) => {
  await mockAuthed(page, deAccount());

  await page.goto("/app");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.getByRole("link", { name: "Vorbereiten" }).first()).toBeVisible();

  await page.goto("/progress");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  // A W9.6 shell-fragment string (progress.eyebrow) — proves fragments are wired, not just base nav.
  await expect(page.getByText("Ihr Weg", { exact: true })).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// E2 + E4 — seven-locale smoke on the PUBLIC /trust surface (W9.6 legal fragment).
// ─────────────────────────────────────────────────────────────────────────────
const TRUST_PRIVATE_TERM: Record<string, string> = {
  en: "Private by default",
  de: "Standardmäßig privat",
  fr: "Privé par défaut",
  es: "Privado de forma predeterminada",
  it: "Privato per impostazione predefinita",
  pt: "Privado por predefinição",
  nl: "Standaard privé",
};

for (const [code, term] of Object.entries(TRUST_PRIVATE_TERM)) {
  test(`E2/E4: public /trust renders the ${code} W9.6 legal fragment`, async ({ page, baseURL }) => {
    await mockPublic(page);
    if (code !== "en") {
      await page.context().addCookies([
        { name: "ask4mo_locale", value: code, url: baseURL ?? "http://localhost:3000" },
      ]);
    }
    await page.goto("/trust");
    // Public route: no redirect to sign-in.
    await expect(page).toHaveURL(/\/trust$/);
    await expect(page.locator("html")).toHaveAttribute("lang", code);
    await expect(page.getByText(term, { exact: true }).first()).toBeVisible();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// E3 — interface language is INDEPENDENT of the Mo conversation language.
// ─────────────────────────────────────────────────────────────────────────────
test("E3: interface locale (de) and conversation language (en) are independent", async ({ page }) => {
  // Account: German interface, English Mo-conversation language.
  await mockAuthed(page, deAccount({ interface_locale: "de", conversation_language: "en" }));

  // Interface language is German everywhere…
  await page.goto("/app");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.getByRole("link", { name: "Vorbereiten" }).first()).toBeVisible();

  // …and Settings exposes three DISTINCT controls; their selected values differ (de vs en),
  // proving the interface language did not force the conversation language to match.
  await page.goto("/settings");
  await expect(page.getByText("Oberflächensprache", { exact: true })).toBeVisible();
  await expect(page.getByText("Mo-Gesprächssprache", { exact: true })).toBeVisible();
  const values = await page.locator("select").evaluateAll((els) =>
    els.map((e) => (e as HTMLSelectElement).value),
  );
  expect(values).toContain("de"); // interface
  expect(values).toContain("en"); // conversation — independent, not coerced to de
});

// ─────────────────────────────────────────────────────────────────────────────
// E5 — error/degraded chrome is localized (not English) in a non-English interface.
// ─────────────────────────────────────────────────────────────────────────────
test("E5: a failed load shows the German error chrome and retry", async ({ page }) => {
  await mockAuthed(page, deAccount(), [
    { match: "/opportunities", status: 500, body: { error: { code: "server", message: "x", request_id: "r" } } },
  ]);
  await page.goto("/opportunities");
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  // Retry control is localized (states.retry = "Erneut versuchen"), independent of the server message.
  await expect(page.getByRole("button", { name: "Erneut versuchen" })).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// Content boundary — user/source content is rendered VERBATIM, never translated.
// ─────────────────────────────────────────────────────────────────────────────
test("user/source content is never translated under a non-English interface", async ({ page }) => {
  await mockAuthed(page, deAccount(), [
    {
      match: "/opportunities",
      body: {
        opportunities: [
          {
            id: 1,
            title: "Senior Software Engineer",
            company_name: "Acme Corporation",
            company_location: "Berlin",
            target_role: "Senior Software Engineer",
            status: "active",
          },
        ],
      },
    },
  ]);
  await page.goto("/opportunities");

  // Ask4Mo-owned chrome is German…
  await expect(page.getByRole("heading", { name: "Ihre Möglichkeiten" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Neue Möglichkeit" })).toBeVisible();

  // …but the candidate's own job title and the employer name are rendered exactly as stored.
  await expect(page.getByText("Senior Software Engineer").first()).toBeVisible();
  await expect(page.getByText("Acme Corporation")).toBeVisible();
});
