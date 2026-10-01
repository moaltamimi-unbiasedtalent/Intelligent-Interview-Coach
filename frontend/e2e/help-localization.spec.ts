import { expect, test, type Page } from "@playwright/test";

/**
 * P10B-W9.6A — Help Center localization closure E2E.
 *
 * Proves the Help Center (section titles + article question/answer bodies, previously hardcoded
 * English in a TS object literal) now localizes with the interface language across all seven locales,
 * that no English source copy leaks in a non-English interface, that the replay-tour entry point still
 * works, and that search operates over the localized content. Backend fully stubbed; 0 paid/live.
 */

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user",
    tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], response_detail: "brief",
    interface_locale: "de", conversation_language: "en", onboarding_completed: true, ...over,
  };
}

async function mock(page: Page, acct: Record<string, unknown>) {
  // Suppress the auto tutorial invitation so it does not race the assertions; the replay launcher is
  // tested explicitly in H4. (Account-scoped tutorial key from W9.5.)
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
    } catch { /* ignore */ }
  });
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(acct);
    return json({});
  });
}

// ─── H1 — German Help: heading, section, article title, article body, search UI all localized ───
test("H1: /help renders German heading, section, article title and body", async ({ page }) => {
  await mock(page, account());
  await page.goto("/help");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  // Page header (help.heading) and section heading (help.gsTitle)
  await expect(page.getByRole("heading", { name: "Hilfe" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Erste Schritte" })).toBeVisible();
  // Article title (help.gs1q) + body (help.gs1a) — the previously-hardcoded content
  await expect(page.getByRole("heading", { name: "Was ist Ask4Mo?" })).toBeVisible();
  await expect(page.getByText(/KI-Interview-Coach/)).toBeVisible();
  // Search placeholder localized (help.searchExamples)
  await expect(page.getByPlaceholder(/Hilfe durchsuchen/)).toBeVisible();
});

// ─── H2 — English source copy must not leak in the German interface ───
test("H2: known English Help source strings are not visible in German", async ({ page }) => {
  await mock(page, account());
  await page.goto("/help");
  await expect(page.getByRole("heading", { name: "Erste Schritte" })).toBeVisible();
  await expect(page.getByText("Getting started", { exact: true })).toHaveCount(0);
  await expect(page.getByText("What is Ask4Mo?", { exact: true })).toHaveCount(0);
  await expect(page.getByText("An AI interview coach.", { exact: false })).toHaveCount(0);
});

// ─── H3 — seven-locale smoke on a stable Help section heading ───
const GS_TITLE: Record<string, string> = {
  en: "Getting started", de: "Erste Schritte", fr: "Premiers pas", es: "Primeros pasos",
  it: "Per iniziare", pt: "Primeiros passos", nl: "Aan de slag",
};
for (const [code, title] of Object.entries(GS_TITLE)) {
  test(`H3: /help section heading is localized for ${code}`, async ({ page }) => {
    await mock(page, account({ interface_locale: code }));
    await page.goto("/help");
    await expect(page.locator("html")).toHaveAttribute("lang", code);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  });
}

// ─── H4 — replay-tour entry point still works after localization ───
test("H4: the Help replay-tour launcher is localized and starts the tour", async ({ page }) => {
  await mock(page, account());
  await page.goto("/help");
  // Tour card heading (help.tourTitle) + launcher (common.takeTour), both German.
  await expect(page.getByRole("heading", { name: "Neu hier?" })).toBeVisible();
  const launcher = page.getByRole("button", { name: "Tour starten" });
  await expect(launcher).toBeVisible();
  await launcher.click();
  // The tour step/invitation renders as a dialog — replay works post-localization.
  await expect(page.getByRole("dialog").first()).toBeVisible();
});

// ─── H5 — search operates over the localized content, with a localized no-result state ───
test("H5: Help search filters localized content and shows a localized no-result state", async ({ page }) => {
  await mock(page, account());
  await page.goto("/help");
  const search = page.getByPlaceholder(/Hilfe durchsuchen/);

  // A term present in the localized content keeps its article visible.
  await search.fill("Ask4Mo");
  await expect(page.getByRole("heading", { name: "Was ist Ask4Mo?" })).toBeVisible();

  // A non-matching term yields the localized no-result message (help.noMatch).
  await search.fill("zzzznomatchxyz");
  await expect(page.getByText(/Keine Hilfethemen passen zu/)).toBeVisible();
});
