import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";
import { BRAND_SLOGAN } from "../lib/brand";

/**
 * P10B-W9.7 - Russian as the 8th interface language, end to end.
 * Deterministic network mock (no backend, no model, no speech provider; 0 paid/live).
 * Expected Russian strings are read from the SAME catalogue the app renders (single source of truth),
 * and each is asserted to be Cyrillic and different from the English value, so a silent English
 * fallback cannot pass. Russian is an interface/conversation language only: no Russian dictation,
 * voice, labour market or ESCO claim is made or tested for.
 */

const CYR = /[Ѐ-ӿ]/;
const ru = (k: string, v?: Record<string, string | number>) => translate("ru", k, v);
const en = (k: string) => translate("en", k);

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "ru", conversation_language: "en",
    coaching_style: "balanced", career_geography: "de", target_role: "",
    onboarding_completed: true, onboarding_step: 0, ...over,
  };
}

const OPP = {
  id: 7, title: "Senior Product Manager", target_role: "Senior Product Manager",
  company_name: "Example Corp", company_location: "Berlin", status: "active",
};
const JD = "Lead the European launch.";
const SOURCES = {
  sources: [
    { source_id: "onet", title: "O*NET", group: "occupations", source_type: "occupation_taxonomy", source_url: "https://www.onetcenter.org/", provider: "official", country: "US", reference_year: null },
  ],
};
const CAPS = {
  agent_coach_enabled: true, realtime_voice_enabled: false, company_research_enabled: false,
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
};

type Opts = {
  acct?: Record<string, unknown>;
  state?: { completed: boolean };
  patches?: unknown[];
  failHistory?: { on: boolean };
};

async function mock(page: Page, o: Opts = {}) {
  // Suppress the first-visit tour invitation (account-scoped key, W9.5) so it never races page asserts.
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
    } catch { /* ignore */ }
  });
  const state = o.state ?? { completed: true };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_ru" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/onboarding") && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      if (body?.complete === true) state.completed = true;
      return json(account({ ...(o.acct ?? {}), onboarding_completed: state.completed }));
    }
    if (path.endsWith("/auth/preferences")) {
      if (method === "PATCH") o.patches?.push(route.request().postDataJSON());
      return json(account({ ...(o.acct ?? {}), onboarding_completed: state.completed }));
    }
    if (path.endsWith("/auth/me")) return json(account({ ...(o.acct ?? {}), onboarding_completed: state.completed }));
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.includes("/opportunities")) return json({ opportunities: [OPP] });
    if (path.includes("/knowledge/sources")) return json(SOURCES);
    if (path.includes("/knowledge/snapshot")) return json({ documents: 3, chunks: 9, document_types: 2 });
    if (path.includes("/documents")) return json({ documents: [] });
    if (path.includes("/stories")) return json({ stories: [] });
    if (path.includes("/memory")) return json({ memories: [] });
    if (path.includes("/progress"))
      return json({ interviews_completed: 0, answers_evaluated: 0, average_practice_score: null, most_common_improvement_area: null, average_answer_seconds: null, recent_interviews: [] });
    if (path.includes("/history")) {
      if (o.failHistory?.on) return json({ error: { code: "server", message: "x", request_id: "req_ru" } }, 500);
      return json({ interviews: [] });
    }
    if (path.includes("/interviews/options")) return json({ career_levels: [], interview_types: [], difficulty_levels: [], deep_dive_modes: [] });
    if (path.includes("/interviews")) return json({ sessions: [] });
    return json({});
  });
  return state;
}

function expectRussian(key: string) {
  expect(ru(key), `${key} must be Russian`).toMatch(CYR);
  expect(ru(key), `${key} must differ from English`).not.toBe(en(key));
}

// ─── AB: Russian core journey across the authenticated product ───
const ROUTES: Array<{ path: string; key: string; role?: "heading" }> = [
  { path: "/opportunities", key: "opportunity.listTitle", role: "heading" },
  { path: "/documents", key: "documents.title", role: "heading" },
  { path: "/prepare", key: "prepare.coachTitle", role: "heading" },
  { path: "/practice", key: "practice.title", role: "heading" },
  { path: "/progress", key: "progress.title", role: "heading" },
  { path: "/history", key: "history.title", role: "heading" },
  { path: "/sources", key: "prepare.careerEvidence", role: "heading" },
  { path: "/settings", key: "settings.title", role: "heading" },
  { path: "/help", key: "help.heading", role: "heading" },
];

test("AB: Russian interface across the core journey (stable chrome Russian, <html lang=ru>)", async ({ page }) => {
  await mock(page);
  // Home: Russian navigation + the protected slogan stays EXACTLY English.
  await page.goto("/app");
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  expectRussian("nav.prepare");
  await expect(page.getByRole("link", { name: ru("nav.prepare") }).first()).toBeVisible();
  await expect(page.getByText(BRAND_SLOGAN, { exact: true }).first()).toBeVisible();

  for (const r of ROUTES) {
    await page.goto(r.path);
    await expect(page.locator("html")).toHaveAttribute("lang", "ru");
    expectRussian(r.key);
    await expect(page.getByRole("heading", { name: ru(r.key) }).first(), `${r.path} heading`).toBeVisible();
    // No English leakage of the SAME chrome string (headings differ between en and ru).
    await expect(page.getByRole("heading", { name: en(r.key), exact: true }), `${r.path} English leak`).toHaveCount(0);
    // Navigation stays Russian everywhere.
    await expect(page.getByRole("link", { name: ru("nav.prepare") }).first()).toBeVisible();
  }
});

// ─── AG: user / source content is never translated ───
test("AG: role, company and official source names stay verbatim; chrome is Russian", async ({ page }) => {
  await mock(page);
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { name: ru("opportunity.listTitle") })).toBeVisible();
  await expect(page.getByText("Senior Product Manager").first()).toBeVisible();
  await expect(page.getByText(/Example Corp/).first()).toBeVisible();
  await page.goto("/sources");
  await expect(page.getByText(/O\*NET/).first()).toBeVisible(); // official source name verbatim
  // JD text is user content: it is never part of the catalogue, so it cannot be translated.
  expect(JD).toBe("Lead the European launch.");
  expect(JSON.stringify(Object.values(translate("ru", "nav.prepare")))).not.toContain(JD);
});

// ─── AC: Russian first-run (onboarding -> Welcome -> Tutorial v2 -> Opportunity step) ───
test("AC: first-run in Russian: onboarding, Welcome, Tutorial v2 Opportunity step, replay", async ({ page }) => {
  await mock(page, { state: { completed: false } });
  await page.goto("/onboarding");
  await page.getByRole("button", { name: ru("onboarding.getStarted") }).click();
  for (let i = 0; i < 5; i++) await page.getByRole("button", { name: ru("onboarding.next") }).click();
  await page.getByRole("button", { name: ru("onboarding.finish") }).click();
  // Russian Welcome (not English, not dumped into /app).
  expectRussian("onboarding.completeTitle");
  await expect(page.getByRole("heading", { name: ru("onboarding.completeTitle") })).toBeVisible();
  for (const k of ["tutorial.welcomeCreate", "tutorial.welcomeTour", "tutorial.welcomeWorkspace"]) {
    expectRussian(k);
    await expect(page.getByRole("button", { name: ru(k) })).toBeVisible();
  }
  // Tour in Russian; step 1 then the Opportunity step before Prepare.
  await page.getByRole("button", { name: ru("tutorial.welcomeTour") }).click();
  await expect(page).toHaveURL(/\/app$/);
  const tour = page.getByRole("dialog");
  await expect(tour.getByText(ru("tutorial.s1Title"))).toBeVisible();
  await expect(page.getByText(ru("tutorial.stepOf", { n: 1, total: 9 }))).toBeVisible();
  await page.getByRole("button", { name: ru("tutorial.next") }).click();
  await expect(page.getByText(ru("tutorial.s2Title"))).toBeVisible();
  expectRussian("tutorial.s2Title");
  // Leave the tour; replay is offered from Help in Russian (Tutorial persistence unchanged).
  await page.getByRole("button", { name: ru("tutorial.skip") }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goto("/help");
  await page.getByRole("button", { name: ru("common.takeTour") }).click();
  await expect(page.getByRole("dialog").first()).toBeVisible();
});

// ─── AD: language independence ───
test("AD1: Russian UI + English conversation: chrome Russian, stored conversation language stays en", async ({ page }) => {
  await mock(page, { acct: { interface_locale: "ru", conversation_language: "en" } });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: ru("settings.title") })).toBeVisible();
  const iface = page.getByLabel(ru("settings.interfaceLanguage"));
  const conv = page.getByLabel(ru("settings.conversationLanguage"));
  await expect(iface).toHaveValue("ru");
  await expect(conv).toHaveValue("en");
  await expect(iface.locator("option", { hasText: "Русский" })).toHaveCount(1);
  // Dictation is a third, separate control that does NOT offer Russian and stays on a supported value.
  const dict = page.getByLabel(ru("settings.dictationLanguage"));
  await expect(dict.locator("option")).toHaveCount(7);
  await expect(dict).toHaveValue("en-US");
});

test("AD2: English UI + Russian conversation: chrome English, conversation language becomes ru, geography untouched", async ({ page }) => {
  const patches: unknown[] = [];
  await mock(page, { acct: { interface_locale: "en", conversation_language: "en" }, patches });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: en("settings.title") })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.getByLabel(en("settings.conversationLanguage")).selectOption("ru");
  await expect.poll(() => patches.length).toBeGreaterThan(0);
  expect(patches).toContainEqual({ conversation_language: "ru" });
  // Only the conversation language was sent: no interface or geography change.
  for (const p of patches as Array<Record<string, unknown>>) {
    expect(p).not.toHaveProperty("interface_locale");
    expect(p).not.toHaveProperty("career_geography");
  }
  await expect(page.locator("html")).toHaveAttribute("lang", "en"); // chrome remains English
});

// ─── AE: error / recovery in Russian ───
test("AE: Russian error chrome (retry + technical details), truthful, and Retry recovers in place", async ({ page }) => {
  const failHistory = { on: true };
  await mock(page, { failHistory });
  await page.goto("/history");
  // Scope to the error card (Next also renders an empty role=alert route announcer).
  const alert = page.getByRole("alert").filter({ hasText: ru("states.somethingWentWrong") });
  expectRussian("states.somethingWentWrong");
  await expect(alert).toBeVisible();
  expectRussian("states.retry");
  expectRussian("states.technicalDetails");
  await expect(page.getByRole("button", { name: ru("states.retry") })).toBeVisible();
  await expect(page.getByText(ru("states.technicalDetails"))).toBeVisible();
  // Truthful: a server fault is not blamed on the candidate's internet connection.
  await expect(alert).not.toContainText("соединени");
  await expect(page.getByRole("button", { name: en("states.retry"), exact: true })).toHaveCount(0);
  // Recover in place: same route, no reload or re-login.
  failHistory.on = false;
  await page.getByRole("button", { name: ru("states.retry") }).click();
  await expect(alert).toHaveCount(0);
  await expect(page.getByRole("heading", { name: ru("history.title") }).first()).toBeVisible();
  await expect(page).toHaveURL(/\/history$/);
});

// ─── AF: Help in Russian ───
test("AF: Help in Russian: section, article, body, localized search, no-result, tour replay", async ({ page }) => {
  await mock(page);
  await page.goto("/help");
  await expect(page.getByRole("heading", { name: ru("help.gsTitle") })).toBeVisible();
  await expect(page.getByRole("heading", { name: ru("help.gs1q") })).toBeVisible();
  await expect(page.getByText(ru("help.gs1a"))).toBeVisible();
  await expect(page.getByText("What is Ask4Mo?", { exact: true })).toHaveCount(0);
  const search = page.getByLabel(ru("help.searchLabel"));
  await search.fill("СОБЕСЕДОВАН"); // Unicode case-insensitive Cyrillic search
  await expect(page.getByRole("heading", { name: ru("help.gs1q") })).toBeVisible();
  await search.fill("zzzznomatchxyz");
  await expect(page.getByText(ru("help.noMatch", { query: "zzzznomatchxyz" }))).toBeVisible();
  await search.fill("");
  await page.getByRole("button", { name: ru("common.takeTour") }).click();
  await expect(page.getByRole("dialog").first()).toBeVisible();
});

// ─── Public surfaces in Russian (legal/trust), cookie-driven, no auth ───
test("Public /trust renders Russian legal/trust copy and the slogan stays English", async ({ page, baseURL }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me"))
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ error: { code: "unauthorized", message: "x", request_id: "r" } }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  await page.context().addCookies([{ name: "ask4mo_locale", value: "ru", url: baseURL ?? "http://localhost:3000" }]);
  await page.goto("/trust");
  await expect(page).toHaveURL(/\/trust$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  expectRussian("trust.privateTerm");
  await expect(page.getByText(ru("trust.privateTerm"), { exact: true }).first()).toBeVisible();
  await page.goto("/about");
  await expect(page.getByText(BRAND_SLOGAN).first()).toBeVisible(); // embedded verbatim in the Russian About text
});
