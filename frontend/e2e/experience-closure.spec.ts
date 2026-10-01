import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";
import { BRAND_SLOGAN } from "../lib/brand";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "../lib/i18n/locales";

/**
 * P10B-W9.7A - experience closure, in real Chromium against the production build (backend mocked at the
 * network layer; no model/provider call). Covers: Home feature blocks in German/Russian/all 8 locales,
 * the Opportunity action (never a blank rectangle; bounded loading; auth-failure state; contrast, focus,
 * keyboard, themes, mobile), Mo-vs-interface language ownership in the response presentation, the error
 * card hierarchy (compact, collapsed details, request id, retry, focus, themes, Russian), Cyrillic font.
 */

const tr = (l: string, k: string, v?: Record<string, string | number>) => translate(l as AppLocale, k, v);
const EN_FEATURES = [
  "Prepare with evidence", "Grounded career information and citations when needed.",
  "Practise with purpose", "Tailored questions based on the role and your preparation context.",
  "Stay in control", "Memory and important handoffs require clear approval.",
  "Improve over time", "Structured feedback, progress and reusable preparation context.",
];

function account(ui: string, conv = "en") {
  return {
    user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session", capabilities: [],
    response_detail: "brief", interface_locale: ui, conversation_language: conv, coaching_style: "balanced",
    career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0,
  };
}

type Mock = {
  ui?: string; conv?: string; theme?: "light" | "dark"; authFail?: boolean; oppHang?: boolean;
  failHistory?: { on: boolean }; chat?: Record<string, unknown>; chatBodies?: unknown[];
};

async function mock(page: Page, o: Mock = {}) {
  const theme = o.theme;
  await page.addInitScript((th) => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
      if (th) window.localStorage.setItem("iic-theme", th);
    } catch { /* ignore */ }
  }, theme);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_w97a" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) {
      if (o.authFail) return json({ error: { code: "server", message: "x", request_id: "req_w97a" } }, 500);
      return json(account(o.ui ?? "en", o.conv ?? "en"));
    }
    if (path.endsWith("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    if (path.includes("/opportunities")) {
      if (o.oppHang) return new Promise(() => {}); // never settles
      return json({ opportunities: [] });
    }
    if (path.includes("/career/chat") && method === "POST") {
      o.chatBodies?.push(route.request().postDataJSON());
      return json(o.chat ?? {});
    }
    if (path.includes("/history")) {
      if (o.failHistory?.on) return json({ error: { code: "server", message: "x", request_id: "req_w97a" } }, 500);
      return json({ interviews: [] });
    }
    if (path.includes("/memory")) return json({ memories: [] });
    if (path.includes("/progress")) return json({ interviews_completed: 0, answers_evaluated: 0, average_practice_score: null, most_common_improvement_area: null, average_answer_seconds: null, recent_interviews: [] });
    if (path.includes("/knowledge/")) return json({ sources: [], documents: 0, chunks: 0, document_types: 0 });
    return json({});
  });
}

// WCAG contrast of an element's text colour against its (first non-transparent) background.
async function contrast(page: Page, selector: string): Promise<number> {
  return page.locator(selector).first().evaluate((el) => {
    const parse = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number);
    const lum = ([r, g, b]: number[]) => {
      const f = (v: number) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const fg = parse(getComputedStyle(el).color);
    let bgEl: Element | null = el, bg = [0, 0, 0, 0];
    while (bgEl) {
      const c = parse(getComputedStyle(bgEl).backgroundColor);
      if (c.length >= 3 && (c[3] === undefined || c[3] > 0)) { bg = c; break; }
      bgEl = bgEl.parentElement;
    }
    const L1 = lum(fg), L2 = lum(bg);
    return (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
  });
}

// ─── Home feature blocks ───
for (const ui of ["de", "ru"] as const) {
  test(`Home ${ui}: original English feature strings absent, ${ui} present, Opportunity action labelled + keyboard-operable`, async ({ page }) => {
    await mock(page, { ui });
    await page.goto("/app");
    await expect(page.locator("html")).toHaveAttribute("lang", ui);
    const blocks = page.getByTestId("home-feature-blocks");
    for (const k of ["feat1", "feat2", "feat3", "feat4"]) {
      await expect(blocks).toContainText(tr(ui, `home.${k}Title`));
      await expect(blocks).toContainText(tr(ui, `home.${k}Body`));
    }
    for (const s of EN_FEATURES) await expect(page.getByText(s, { exact: true })).toHaveCount(0);
    const cta = page.getByRole("link", { name: tr(ui, "home.opportunityCreate") });
    await expect(cta).toBeVisible();
    expect((await cta.innerText()).trim().length).toBeGreaterThan(0);
    await cta.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/opportunities\?create=1$/);
  });
}

test("Home: all 8 locales render localized feature headings, a labelled CTA and the exact slogan", async ({ page }) => {
  await mock(page, { ui: "en" });
  for (const ui of SUPPORTED_LOCALE_CODES) {
    await page.unroute("**/api/v1/**");
    await mock(page, { ui });
    await page.goto("/app");
    await expect(page.locator("html")).toHaveAttribute("lang", ui);
    for (const k of ["feat1", "feat2", "feat3", "feat4"]) {
      await expect(page.getByText(tr(ui, `home.${k}Title`), { exact: true }), `${ui} ${k}`).toBeVisible();
    }
    await expect(page.getByRole("link", { name: tr(ui, "home.opportunityCreate") }), `${ui} CTA`).toBeVisible();
    await expect(page.getByText(BRAND_SLOGAN, { exact: true }).first()).toBeVisible();
  }
});

// ─── Opportunity action: never a blank rectangle ───
test("Opportunity action: failed auth (the old permanent-placeholder state) shows the labelled default action", async ({ page }) => {
  await mock(page, { ui: "en", authFail: true });
  await page.goto("/app");
  const cta = page.getByRole("link", { name: tr("en", "home.opportunityCreate") });
  await expect(cta).toBeVisible();
  await page.waitForTimeout(800);
  await expect(page.locator('[data-tour="opportunity-entry"] .animate-pulse')).toHaveCount(0);
  await expect(page.getByTestId("opportunity-entry-loading")).toHaveCount(0);
  const box = await cta.boundingBox();
  expect(box!.width).toBeGreaterThan(60);
  expect(box!.height).toBeGreaterThan(30);
});

test("Opportunity action: a hanging request shows a LABELLED bounded placeholder, then the default action", async ({ page }) => {
  await mock(page, { ui: "en", oppHang: true });
  await page.goto("/app");
  const loading = page.getByTestId("opportunity-entry-loading");
  await expect(loading).toBeVisible();
  await expect(loading).toHaveAttribute("role", "status");
  await expect(loading).toContainText(tr("en", "states.loading"));
  await expect(page.getByRole("link", { name: tr("en", "home.opportunityCreate") })).toBeVisible({ timeout: 8000 });
  await expect(loading).toHaveCount(0);
});

for (const theme of ["light", "dark"] as const) {
  for (const vp of [{ w: 1280, h: 800, n: "desktop" }, { w: 390, h: 780, n: "390px" }]) {
    test(`Opportunity action (${theme}, ${vp.n}): visible text, AA contrast, visible keyboard focus, no overflow`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h });
      await mock(page, { ui: "ru", theme });
      await page.goto("/app");
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      const label = tr("ru", "home.opportunityCreate");
      const cta = page.getByRole("link", { name: label });
      await expect(cta).toBeVisible();
      expect(await contrast(page, `a:has-text("${label}")`)).toBeGreaterThanOrEqual(4.5);
      await cta.focus();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Shift+Tab");
      const ring = await cta.evaluate((el) => { const s = getComputedStyle(el); return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) }; });
      expect(ring.style).not.toBe("none");
      expect(ring.width).toBeGreaterThan(0);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }
}

// ─── Cyrillic typography ───
test("Russian text renders in the existing Inter family (webfont), with the Cyrillic file preloaded", async ({ page }) => {
  await mock(page, { ui: "ru" });
  await page.goto("/app");
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("DOM.enable");
  await cdp.send("CSS.enable");
  const doc = await cdp.send("DOM.getDocument", { depth: -1 });
  for (const sel of ["main h1", "main h2", "main p"]) {
    const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: sel });
    const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
    expect(fonts.length, sel).toBeGreaterThan(0);
    for (const f of fonts) {
      expect(f.familyName, `${sel} must use Inter`).toBe("Inter");
      expect(f.isCustomFont, `${sel} must be the self-hosted webfont, not a system fallback`).toBe(true);
    }
  }
  // The Cyrillic subset is preloaded (no late swap): >= 2 font preloads (latin + cyrillic).
  expect(await page.locator('link[rel="preload"][as="font"]').count()).toBeGreaterThanOrEqual(2);
});

// ─── Response presentation: interface vs conversation ownership ───
const CHAT_NO_EVIDENCE = {
  answer: "(model answer text, rendered verbatim)",
  citations: [], sources: [{ title: "O*NET Product manager", source_url: "https://example.org/onet", reference_year: 2024 }],
  tools: [], input_flagged: false, has_evidence: false, preparation_available: false,
};

const OWNERSHIP: Array<[string, string]> = [["de", "en"], ["en", "de"], ["ru", "ru"], ["en", "ru"], ["ru", "en"]];
for (const [ui, conv] of OWNERSHIP) {
  test(`response presentation: interface=${ui} conversation=${conv}: UI labels follow ${ui}, Mo note follows ${conv}`, async ({ page }) => {
    const chatBodies: unknown[] = [];
    await mock(page, { ui, conv, chat: CHAT_NO_EVIDENCE, chatBodies });
    await page.goto("/prepare");
    await page.getByLabel(tr(ui, "prepare.askTheCoach")).fill("What should I focus on?");
    await page.getByRole("button", { name: tr(ui, "prepare.ask"), exact: true }).click();
    // Mo-voiced note: CONVERSATION language.
    await expect(page.getByText(tr(conv, "coach.insufficientEvidence"))).toBeVisible();
    if (ui !== conv) await expect(page.getByText(tr(ui, "coach.insufficientEvidence"))).toHaveCount(0);
    // UI chrome (source summary): INTERFACE language; source title/url verbatim.
    await expect(page.getByText(tr(ui, "prepare.evidenceSourcesOne"))).toBeVisible();
    await page.getByText(tr(ui, "prepare.evidenceSourcesOne")).click();
    await expect(page.getByRole("link", { name: "O*NET Product manager" })).toHaveAttribute("href", "https://example.org/onet");
    // The request carried the CONVERSATION language only (never the interface locale).
    expect(chatBodies.length).toBeGreaterThan(0);
    const body = chatBodies[0] as Record<string, unknown>;
    expect(body.conversation_language).toBe(conv);
    expect(body).not.toHaveProperty("interface_locale");
    expect(body).not.toHaveProperty("career_geography");
  });
}

// ─── Error card hierarchy + recovery ───
for (const theme of ["dark", "light"] as const) {
  for (const vp of [{ w: 1280, h: 800, n: "desktop", maxH: 230 }, { w: 390, h: 780, n: "390px", maxH: 340 }]) {
    test(`error card (${theme}, ${vp.n}, Russian): proportional, localized, collapsed details, keyboard disclosure, retry restores`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h });
      const failHistory = { on: true };
      await mock(page, { ui: "ru", theme, failHistory });
      await page.goto("/history");
      const card = page.locator('[data-error-variant="page"]');
      await expect(card).toBeVisible();
      // Proportional: not a viewport-sized block (the old card was ~full-width centred, 40px+ vertical padding).
      const box = await card.boundingBox();
      expect(box!.height, `card height ${box!.height}px`).toBeLessThanOrEqual(vp.maxH);
      expect(box!.height).toBeLessThan(vp.h * 0.45);
      expect(box!.width).toBeLessThanOrEqual(vp.w);
      // Localized chrome (Russian), no English application chrome.
      await expect(card.getByRole("heading", { name: tr("ru", "states.somethingWentWrong") })).toBeVisible();
      await expect(card.getByText(tr("ru", "states.serverError"))).toBeVisible();
      const retry = card.getByRole("button", { name: tr("ru", "states.retry") });
      await expect(retry).toBeVisible();
      await expect(card.getByText("Something went wrong")).toHaveCount(0);
      expect(await contrast(page, '[data-error-variant="page"] button')).toBeGreaterThanOrEqual(4.5);
      expect(await contrast(page, '[data-error-variant="page"] p')).toBeGreaterThanOrEqual(4.5);
      // Technical details: collapsed by default; native keyboard disclosure shows the request id.
      const details = card.locator("details");
      expect(await details.evaluate((d) => (d as HTMLDetailsElement).open)).toBe(false);
      await expect(card.getByText("req_w97a")).toBeHidden();
      await card.locator("summary").focus();
      await page.keyboard.press("Enter");
      expect(await details.evaluate((d) => (d as HTMLDetailsElement).open)).toBe(true);
      await expect(card.getByText(/req_w97a/)).toBeVisible();
      // Retry: recovers in place (no reload / login loss), error gone, focus moves to the main region.
      failHistory.on = false;
      await retry.focus();
      await page.keyboard.press("Enter");
      await expect(page.locator('[data-error-variant="page"]')).toHaveCount(0);
      await expect(page).toHaveURL(/\/history$/);
      expect(await page.evaluate(() => document.activeElement?.id)).toBe("main");
    });
  }
}

test("error chrome renders localized in every locale (English never leaks into a non-English error card)", async ({ page }) => {
  for (const ui of SUPPORTED_LOCALE_CODES) {
    await page.unroute("**/api/v1/**");
    await mock(page, { ui, failHistory: { on: true } });
    await page.goto("/history");
    const card = page.locator('[data-error-variant="page"]');
    await expect(card, ui).toBeVisible();
    await expect(card.getByRole("heading", { name: tr(ui, "states.somethingWentWrong") })).toBeVisible();
    await expect(card.getByRole("button", { name: tr(ui, "states.retry") })).toBeVisible();
    await expect(card.getByText(tr(ui, "states.technicalDetails"))).toBeVisible();
    if (ui !== "en") await expect(card.getByText(tr("en", "states.somethingWentWrong"), { exact: true })).toHaveCount(0);
  }
});

test("section errors stay compact and the rest of the page stays usable (Progress, one region failing)", async ({ page }) => {
  await mock(page, { ui: "en" });
  await page.unroute("**/api/v1/**");
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (b: unknown, s = 200) => route.fulfill({ status: s, contentType: "application/json", headers: { "x-request-id": "req_w97a" }, body: JSON.stringify(b) });
    if (path.endsWith("/auth/me")) return json(account("en"));
    if (path.includes("/memory")) return json({ memories: [] });
    if (path.includes("/progress")) return json({ error: { code: "server", message: "x", request_id: "req_w97a" } }, 500);
    return json({});
  });
  await page.goto("/progress");
  const section = page.getByRole("alert").filter({ hasText: /\S/ });
  await expect(section).toBeVisible();
  const box = await section.first().boundingBox();
  expect(box!.height).toBeLessThan(200);
  await expect(page.getByRole("heading", { name: tr("en", "progress.title"), exact: true })).toBeVisible();
});

// ─── Cyrillic visual QA across the main Russian surfaces (font, overflow, mobile, tutorial, error) ───
for (const vp of [{ w: 1280, h: 800, n: "desktop" }, { w: 390, h: 780, n: "390px" }]) {
  test(`Russian surfaces (${vp.n}): Inter webfont for every text node, no horizontal overflow, controls not clipped`, async ({ page }) => {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    const failHistory = { on: false };
    await mock(page, { ui: "ru", failHistory });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("DOM.enable");
    await cdp.send("CSS.enable");
    const surfaces = ["/app", "/opportunities", "/prepare", "/practice", "/progress", "/history", "/help"];
    for (const path of surfaces) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("lang", "ru");
      await page.waitForTimeout(300);
      const doc = await cdp.send("DOM.getDocument", { depth: -1 });
      for (const sel of ["main h1", "main p"]) {
        const found = await cdp.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: sel });
        if (!found.nodeId) continue;
        const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId: found.nodeId });
        for (const f of fonts) expect(`${f.familyName}/${f.isCustomFont}`, `${path} ${sel}`).toBe("Inter/true");
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `${path} horizontal overflow`).toBeLessThanOrEqual(1);
      // Buttons/links are not clipped: their text fits inside their own box.
      const clipped = await page.evaluate(() =>
        Array.from(document.querySelectorAll<HTMLElement>("main a, main button, nav a, nav button"))
          .filter((el) => el.offsetParent !== null && el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== "visible")
          .map((el) => (el.textContent ?? "").trim().slice(0, 30)),
      );
      expect(clipped, `${path} clipped controls`).toEqual([]);
    }
    // Mobile bottom navigation fits all Russian labels without overflow.
    if (vp.w < 768) {
      const navOverflow = await page.evaluate(() => {
        const nav = document.querySelector("nav[aria-label]:not([class*='md:'])") as HTMLElement | null;
        return nav ? nav.scrollWidth - nav.clientWidth : 0;
      });
      expect(navOverflow).toBeLessThanOrEqual(1);
    }
    // Tutorial card (Russian) is usable and in Inter.
    await page.goto("/help");
    await page.getByRole("button", { name: tr("ru", "common.takeTour") }).click();
    const dlg = page.getByRole("dialog").first();
    await expect(dlg).toBeVisible();
    const dbox = await dlg.boundingBox();
    expect(dbox!.x).toBeGreaterThanOrEqual(0);
    expect(dbox!.x + dbox!.width).toBeLessThanOrEqual(vp.w + 1);
    // Error state (Russian) in Inter as well.
    failHistory.on = true;
    await page.goto("/history");
    const card = page.locator('[data-error-variant="page"]');
    await expect(card).toBeVisible();
    const doc2 = await cdp.send("DOM.getDocument", { depth: -1 });
    const h = await cdp.send("DOM.querySelector", { nodeId: doc2.root.nodeId, selector: '[data-error-variant="page"] h2' });
    const { fonts: ef } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId: h.nodeId });
    for (const f of ef) expect(`${f.familyName}/${f.isCustomFont}`).toBe("Inter/true");
  });
}
