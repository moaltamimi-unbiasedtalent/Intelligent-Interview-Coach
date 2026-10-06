import { expect, test, type Page } from "@playwright/test";
import { translate } from "../lib/i18n/catalog";
import type { AppLocale } from "../lib/i18n/locales";

/**
 * P10B-W11 integrated visual + accessibility regression, in real Chromium against the production build (backend mocked at the network layer; no provider call).
 * CANDIDATE: 13 surfaces x {de, ru} x {desktop 1280, mobile 390} x {light, dark} = 104 programmatic page/configuration checks.
 * ADMIN (English-only): every top-level Admin destination + a detail page x {tablet 768, desktop 1280} x {light, dark}. A shared-header breakpoint regression
 * (LAYOUT-W11-01, found by W11 and corrected: the desktop/mobile navigation handoff moved from md=768px to lg=1024px) covers candidate and Admin chrome at 768 and 1024.
 * Programmatic checks only (no screenshots are asserted); no WCAG certification is claimed. W9.13 recorded A11Y-W9-13-01 (/practice without a page-level h1, ACCEPTED).
 * On the W11 tree a FULLY RENDERED /practice has an h1 in every configuration and the page source has not changed since W9.7, so the finding is not reproducible;
 * this suite now requires an h1 on all 13 surfaces. The crash detector is localized (the route error boundary is detected by its translated copy), so a crashed
 * de/ru page can never pass vacuously.
 */

const CAND_PAGES = ["/", "/app", "/opportunities", "/prepare", "/practice", "/progress", "/history", "/settings", "/account", "/account/data", "/trust", "/help", "/onboarding"];

const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_w11" }, body: JSON.stringify(body) });
const account = (ui: string, perms: string[] = [], onboarded = true) => ({ user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: perms.length ? "x" : "user", tier: "basic", status: "active",
  email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: ui, conversation_language: ui,
  coaching_style: "balanced", career_geography: "", target_role: "", onboarding_completed: onboarded, onboarding_step: 0 });

async function mockCandidate(page: Page, ui: string, theme: "light" | "dark", onboarded: boolean) {
  await page.addInitScript((th) => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
      window.localStorage.setItem("iic-theme", th);
    } catch { /* ignore */ }
  }, theme);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return json(route, account(ui, [], onboarded));
    if (path.endsWith("/capabilities")) return json(route, { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true, company_research_enabled: false });
    if (path.endsWith("/interviews/options")) return json(route, { career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: ["deepen_reasoning", "challenge_assumptions"] });
    if (path.endsWith("/interviews")) return json(route, { sessions: [] });
    if (path.includes("/opportunities")) return json(route, { opportunities: [] });
    if (path.includes("/history")) return json(route, { interviews: [] });
    if (path.includes("/memory")) return json(route, { memories: [] });
    if (path.includes("/progress")) return json(route, { interviews_completed: 0, answers_evaluated: 0, average_practice_score: null, most_common_improvement_area: null, average_answer_seconds: null, recent_scores: [], improvement_areas: [] });
    if (path.includes("/documents")) return json(route, { documents: [] });
    if (path.includes("/support/")) return json(route, { tickets: [], total: 0, page: 1, page_size: 20 });
    if (path.endsWith("/auth/plan")) return json(route, { plan: { plan_code: "basic", plan_name: "Basic", version: 1 }, entitlements: {} });
    return json(route, {});
  });
}

// Everything evaluated INSIDE the page so the checks are about what a visitor perceives.
async function inspect(page: Page, ui = "en") {
  // The route error boundary is LOCALIZED: detect it by its translated copy as well as the English text, so a crashed de/ru page can never pass vacuously.
  const crashNeedles = [translate(ui as AppLocale, "states.serverError"), translate("en" as AppLocale, "states.serverError"), "Something went wrong", "Application error"];
  return page.evaluate((needles) => {
    const visible = (el: Element) => { const r = (el as HTMLElement).getBoundingClientRect(); const cs = getComputedStyle(el as HTMLElement); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none"; };
    const name = (el: Element) => (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || (el as HTMLElement).innerText || el.getAttribute("title") || el.querySelector("img[alt]")?.getAttribute("alt") || (el as HTMLInputElement).value || "").trim();
    const text = document.body.innerText;
    const rawKeys = (text.match(/\b[a-z][a-z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){2,}\b/g) ?? []).filter((t) => !/^(www|e\.g|i\.e)/.test(t) && !/\.(com|org|io|net|dev)\b/.test(t));
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      mainOverflow: (() => {
        const vw = document.documentElement.clientWidth;
        const clipped = (el: Element) => { for (let p = el.parentElement; p && p.tagName !== "MAIN"; p = p.parentElement) { const ox = getComputedStyle(p).overflowX; if (["auto", "scroll", "hidden", "clip"].includes(ox) && p.getBoundingClientRect().right <= vw + 1) return true; } return false; };
        return Math.max(0, ...Array.from(document.querySelectorAll("main, main *")).filter((e) => !clipped(e)).map((e) => Math.round((e as HTMLElement).getBoundingClientRect().right - vw)));
      })(),
      h1: document.querySelectorAll("h1").length,
      rawKeys: Array.from(new Set(rawKeys)).slice(0, 5),
      unnamed: Array.from(document.querySelectorAll("a[href],button")).filter((e) => visible(e) && !name(e)).map((e) => e.outerHTML.slice(0, 80)).slice(0, 5),
      noAlt: Array.from(document.querySelectorAll("img")).filter((i) => visible(i) && !i.hasAttribute("alt") && i.getAttribute("role") !== "presentation").map((i) => (i as HTMLImageElement).src.slice(-40)).slice(0, 5),
      adminLinks: Array.from(document.querySelectorAll("a[href^='/admin']")).length,
      cyrillic: /[Ѐ-ӿ]/.test(text),
      umlaut: /[äöüß]/i.test(text),
      sloganVariants: ((document.body.textContent ?? "").match(/Ask More[.,]?\s*Be More[.,]?/gi) ?? []).filter((s) => s !== "Ask More. Be More."),
      crashed: needles.some((n) => text.includes(n)),
      length: text.length,
    };
  }, crashNeedles);
}

const CONFIGS: { ui: "de" | "ru"; w: number; h: number; theme: "light" | "dark" }[] = [];
for (const ui of ["de", "ru"] as const) for (const [w, h] of [[1280, 800], [390, 844]] as const) for (const theme of ["light", "dark"] as const) CONFIGS.push({ ui, w, h, theme });

for (const cfg of CONFIGS) {
  test(`W11 candidate visual/a11y: 13 surfaces, ${cfg.ui}, ${cfg.w}px, ${cfg.theme}`, async ({ page }) => {
    await page.setViewportSize({ width: cfg.w, height: cfg.h });
    const violations: string[] = [];
    let checked = 0;
    for (const path of CAND_PAGES) {
      await page.unrouteAll({ behavior: "ignoreErrors" });
      await mockCandidate(page, cfg.ui, cfg.theme, path !== "/onboarding");
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const r = await inspect(page, cfg.ui);
      checked += 1;
      const tag = `${path}`;
      if (r.overflow > 1) violations.push(`${tag}: horizontal overflow ${r.overflow}px`);
      if (r.rawKeys.length) violations.push(`${tag}: raw translation key(s) ${r.rawKeys.join(", ")}`);
      if (r.unnamed.length) violations.push(`${tag}: control(s) without an accessible name ${r.unnamed.join(" | ")}`);
      if (r.noAlt.length) violations.push(`${tag}: image(s) without alt ${r.noAlt.join(", ")}`);
      if (r.adminLinks > 0) violations.push(`${tag}: candidate sees an Admin link`);
      if (r.sloganVariants.length) violations.push(`${tag}: slogan variant ${r.sloganVariants.join(", ")}`);
      if (r.crashed) violations.push(`${tag}: page crashed`);
      if (r.h1 < 1) violations.push(`${tag}: no page-level h1`);
      if (cfg.ui === "ru" && r.length > 80 && !r.cyrillic) violations.push(`${tag}: no Cyrillic text rendered`);
    }
    expect(checked).toBe(13);
    expect(violations, violations.join("\n")).toEqual([]);
  });
}

// ------------------------------------------------------------------------------------------------------------------ ADMIN (English only)
const ALL_PERMS = ["platform.overview.read", "platform.users.read", "platform.users.manage", "platform.users.role.assign", "platform.users.sessions.revoke", "platform.workspaces.read", "platform.workspaces.manage",
  "platform.audit.read", "platform.audit.export", "platform.integrations.read", "platform.integrations.manage", "platform.ai.read", "platform.ai.manage", "platform.ai.activate", "platform.knowledge.read",
  "platform.knowledge.manage", "platform.knowledge.approve", "platform.plans.read", "platform.plans.manage", "platform.plans.price.change", "platform.subscriptions.manage", "platform.support.read",
  "platform.support.reply", "platform.support.manage", "platform.support.note", "platform.jobs.read", "platform.jobs.manage", "platform.billing.read", "platform.billing.refund", "platform.privacy.read",
  "platform.privacy.execute", "platform.legal.manage", "platform.flags.read", "platform.flags.manage", "platform.config.manage", "platform.reports.read", "platform.reports.commercial.read",
  "platform.security.read", "platform.security.manage", "platform.incidents.manage", "platform.releases.read"];
const ADMIN_PAGES = ["/admin", "/admin/users", "/admin/workspaces", "/admin/plans", "/admin/support", "/admin/security", "/admin/audit", "/admin/billing", "/admin/privacy", "/admin/legal",
  "/admin/knowledge", "/admin/reports", "/admin/configuration", "/admin/flags", "/admin/ai", "/admin/jobs", "/admin/integrations", "/admin/providers", "/admin/users/1", "/admin/support/0123456789abcdef0123456789abcdef"];

// Realistic shapes: the recorded responses of the REAL Admin API (scripts/gen_w11_admin_fixture.py, generated from a temp database; content-free example data).
import recorded from "./fixtures/admin-responses.json";
const REC = recorded as Record<string, unknown>;
function recordedFor(path: string): unknown | undefined {
  const p = path.replace(/^\/api\/v1/, "");
  if (p in REC) return REC[p];
  const norm = p.replace(/\/[0-9a-f]{32}$|\/\d+$/, "/{id}");
  return norm in REC ? REC[norm] : undefined;
}
async function mockAdmin(page: Page, theme: "light" | "dark") {
  await page.addInitScript((th) => { try { window.localStorage.setItem("iic-theme", th); } catch { /* ignore */ } }, theme);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return json(route, account("en", ALL_PERMS));
    if (path.endsWith("/capabilities")) return json(route, { agent_coach_enabled: false, company_research_enabled: false });
    const rec = recordedFor(path);
    return json(route, rec !== undefined ? rec : {});
  });
}

const ADMIN_CONFIGS: { w: number; h: number; theme: "light" | "dark" }[] = [];
for (const [w, h] of [[1280, 800], [768, 1024]] as const) for (const theme of ["light", "dark"] as const) ADMIN_CONFIGS.push({ w, h, theme });

for (const cfg of ADMIN_CONFIGS) {
  test(`W11 Admin visual/a11y: ${ADMIN_PAGES.length} destinations, ${cfg.w}px, ${cfg.theme}`, async ({ page }) => {
    await page.setViewportSize({ width: cfg.w, height: cfg.h });
    const violations: string[] = [];
    for (const path of ADMIN_PAGES) {
      await page.unrouteAll({ behavior: "ignoreErrors" });
      await mockAdmin(page, cfg.theme);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const r = await inspect(page);
      // LAYOUT-W11-01 is corrected: neither the document nor the Admin content may overflow at ANY width (including the 768px tablet handoff).
      if (r.overflow > 1) violations.push(`${path}: horizontal overflow ${r.overflow}px`);
      if (r.mainOverflow > 1) violations.push(`${path}: Admin content overflows the viewport by ${r.mainOverflow}px`);
      if (r.h1 < 1) violations.push(`${path}: no semantic page heading (h1)`);
      if (r.unnamed.length) violations.push(`${path}: control(s) without an accessible name ${r.unnamed.join(" | ")}`);
      if (r.noAlt.length) violations.push(`${path}: image(s) without alt`);
      if (r.crashed) violations.push(`${path}: page crashed (mock too thin or a real defect)`);
    }
    expect(violations, violations.join("\n")).toEqual([]);
  });
}

test("W11 Admin: a permission-denied principal sees a safe state and no Admin navigation or candidate content", async ({ page }) => {
  await page.addInitScript(() => { try { window.localStorage.setItem("iic-theme", "light"); } catch { /* ignore */ } });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return json(route, account("en", []));
    if (path.endsWith("/capabilities")) return json(route, {});
    return json(route, { error: { code: "forbidden", message: "Administrator access required.", request_id: "r" } }, 403);
  });
  await page.goto("/admin/security");
  await page.waitForLoadState("networkidle");
  const r = await inspect(page);
  expect(r.adminLinks).toBe(0);
  expect(r.crashed).toBe(false);
  await expect(page.getByRole("tab")).toHaveCount(0);
});


// ------------------------------------------------------------------------------------------------------------------ shared header breakpoint (LAYOUT-W11-01)
// The desktop header navigation appears from lg (1024px); below it (including exactly 768px) the compact bottom bar is the single primary navigation.
for (const ui of ["de", "ru"] as const) {
  for (const width of [768, 1024] as const) {
    test(`W11 shared header breakpoint: candidate /app, ${ui}, ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await mockCandidate(page, ui, "light", true);
      await page.goto("/app");
      await page.waitForLoadState("networkidle");
      const r = await inspect(page, ui);
      expect(r.overflow, "document horizontal overflow").toBeLessThanOrEqual(1);
      expect(r.mainOverflow, "main content overflow").toBeLessThanOrEqual(1);
      expect(r.crashed).toBe(false);
      expect(r.rawKeys).toEqual([]);
      expect(r.unnamed, "header controls without an accessible name").toEqual([]);
      const primary = page.getByRole("navigation", { name: translate(ui as AppLocale, "nav.primary") });
      await expect(primary).toHaveCount(1);                                              // exactly ONE visible primary landmark (hidden ones are not exposed)
      const labels = ["nav.opportunities", "nav.prepare", "nav.practice", "nav.progress", "nav.history"].map((k) => translate(ui as AppLocale, k));
      for (const label of labels) await expect(primary.getByRole("link", { name: label })).toBeVisible();   // all five destinations reachable
      const bottom = await page.evaluate(() => {
        const navs = Array.from(document.querySelectorAll("nav")).filter((n) => getComputedStyle(n).display !== "none");
        const fixedBottom = navs.some((n) => getComputedStyle(n).position === "fixed");
        const headerNav = navs.some((n) => n.closest("header") !== null);
        return { fixedBottom, headerNav };
      });
      if (width === 768) expect(bottom).toEqual({ fixedBottom: true, headerNav: false });      // compact navigation is the active pattern
      else expect(bottom).toEqual({ fixedBottom: false, headerNav: true });                      // desktop PrimaryNavigation active, bottom bar hidden
      for (const control of [translate(ui as AppLocale, "nav.more") ]) await expect(page.getByRole("button", { name: control }).first()).toBeVisible();
      await expect(page.locator("header").getByRole("button").first()).toBeVisible();          // language, theme and account controls remain in the header
    });
  }
}

test("W11 shared header breakpoint: an Admin keeps Admin access through More at 768px and 1024px", async ({ page }) => {
  for (const width of [768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await mockAdmin(page, "light");
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");
    const r = await inspect(page);
    expect(r.overflow).toBeLessThanOrEqual(1);
    expect(r.mainOverflow).toBeLessThanOrEqual(1);
    expect(r.crashed).toBe(false);
    await page.getByRole("button", { name: /^More/ }).first().click();                       // Admin destinations remain reachable via More
    await expect(page.getByRole("menuitem").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: /^More/ }).first()).toBeFocused();         // keyboard handling intact
  }
});
