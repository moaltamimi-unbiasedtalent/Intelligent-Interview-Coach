import { expect, test, type Page } from "@playwright/test";
import { translate } from "../lib/i18n/catalog";

/**
 * Ask4Mo v4 experience, in real Chromium against the production build (backend mocked at the network layer; no provider call).
 * Public routes + the core app routes at desktop (1280) and mobile (390): no horizontal overflow, an h1, no raw translation keys,
 * no video or audio loaded, images that actually decode, the floating marketing header (20px float, stays visible while scrolling,
 * never inside the authenticated app), the mobile menu, the workflow map and the in-app journey cues. Readiness is deterministic
 * (domcontentloaded + #main + h1), never network idleness.
 */

const PUBLIC = ["/", "/getting-started", "/pricing", "/about", "/product", "/trust", "/help"];
const APP = ["/app", "/opportunities", "/prepare", "/practice", "/progress", "/history"];
const T = (k: string) => translate("en", k);

const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_v4" }, body: JSON.stringify(body) });
const account = () => ({ user_id: 1, email: "candidate@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active",
  email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
  coaching_style: "balanced", career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 });

async function mockApi(page: Page, authed: boolean) {
  await page.addInitScript(() => { try { window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() })); } catch { /* ignore */ } });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return authed ? json(route, account()) : json(route, { error: { code: "unauthenticated", message: "Sign in required.", request_id: "r" } }, 401);
    if (path.endsWith("/capabilities")) return json(route, { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true, company_research_enabled: false });
    if (path.endsWith("/interviews/options")) return json(route, { career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: ["deepen_reasoning", "challenge_assumptions"] });
    if (path.endsWith("/interviews")) return json(route, { sessions: [] });
    if (path.includes("/opportunities")) return json(route, { opportunities: [] });
    if (path.includes("/history")) return json(route, { interviews: [] });
    if (path.includes("/memory")) return json(route, { memories: [] });
    if (path.includes("/progress")) return json(route, { interviews_completed: 0, answers_evaluated: 0, average_practice_score: null, most_common_improvement_area: null, average_answer_seconds: null, recent_scores: [], improvement_areas: [] });
    if (path.includes("/documents")) return json(route, { documents: [] });
    if (path.endsWith("/auth/plan")) return json(route, { plan: { plan_code: "basic", plan_name: "Basic", version: 1 }, entitlements: {} });
    return json(route, {});
  });
}

async function ready(page: Page, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await expect(page.locator("#main")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
}

async function snapshot(page: Page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const raw = (text.match(/\b[a-z][a-z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){2,}\b/g) ?? []).filter((t) => !/^(www|e\.g|i\.e)/.test(t) && !/\.(com|org|io|net|dev)\b/.test(t));
    const imgs = Array.from(document.images).filter((i) => i.getBoundingClientRect().width > 0 && i.loading !== "lazy" ? true : i.complete);
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      h1: document.querySelectorAll("h1").length,
      raw,
      video: document.querySelectorAll("video, audio").length,
      brokenImages: imgs.filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.currentSrc || i.src),
      marketingHeader: !!document.querySelector("[data-testid=marketing-header]"),
    };
  });
}

for (const width of [1280, 390] as const) {
  test(`v4 public routes at ${width}px: no overflow, h1, no raw keys, no video, images decode`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockApi(page, false);
    const media: string[] = [];
    page.on("request", (r) => { if (["media"].includes(r.resourceType()) || /\.(mp4|webm|mov|m4v|mp3|wav)(\?|$)/i.test(r.url())) media.push(r.url()); });
    const violations: string[] = [];
    for (const path of PUBLIC) {
      await ready(page, path);
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));          // trigger lazy images
      await page.waitForFunction(() => Array.from(document.images).every((i) => i.complete), null, { timeout: 15_000 });
      const s = await snapshot(page);
      if (s.overflow > 1) violations.push(`${path}: horizontal overflow ${s.overflow}px`);
      if (s.h1 < 1) violations.push(`${path}: no h1`);
      if (s.raw.length) violations.push(`${path}: raw keys ${s.raw.join(", ")}`);
      if (s.video) violations.push(`${path}: video/audio element present`);
      if (s.brokenImages.length) violations.push(`${path}: images failed to decode ${s.brokenImages.join(", ")}`);
      // /help is public but intentionally uses the product shell (unchanged); every other public route carries the floating marketing header.
      if (path !== "/help" && !s.marketingHeader) violations.push(`${path}: marketing header missing`);
    }
    expect(media, "no media (video/audio) request on any public route").toEqual([]);
    expect(violations, violations.join("\n")).toEqual([]);
  });
}

test("v4 floating header: 20px float at the top, stays visible and compacts while scrolling (desktop)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mockApi(page, false);
  await ready(page, "/getting-started");
  const header = page.getByTestId("marketing-header");
  const bar = header.locator("> div").first();
  const top0 = (await bar.boundingBox())!.y;
  expect(top0).toBeGreaterThanOrEqual(16);
  expect(top0).toBeLessThanOrEqual(26);
  await expect(header).toHaveAttribute("data-scrolled", "false");
  await page.evaluate(() => window.scrollTo(0, 1500));
  await expect(header).toHaveAttribute("data-scrolled", "true");
  const box = (await bar.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeLessThanOrEqual(26);
  await expect(bar).toBeVisible();
  // In-page anchors clear the floating bar: the story heading lands below the bar's bottom edge.
  await page.goto("/getting-started#workflow", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#workflow h2")).toBeVisible();
  const h2top = (await page.locator("#workflow h2").boundingBox())!.y;
  expect(h2top).toBeGreaterThanOrEqual(box.y + box.height - 2);
});

test("v4 mobile menu: opens, lists every route, Escape closes and restores focus (390px)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await mockApi(page, false);
  await ready(page, "/");
  const toggle = page.locator("#marketing-mobile-menu").or(page.getByRole("button", { name: T("v4nav.menuLabel") })).first();
  const btn = page.getByRole("button", { name: T("v4nav.menuLabel") });
  await expect(btn).toHaveAttribute("aria-expanded", "false");
  await btn.click();
  await expect(btn).toHaveAttribute("aria-expanded", "true");
  const menu = page.getByRole("navigation", { name: T("marketing.navAriaMobile") });
  await expect(menu.getByRole("link")).toHaveCount(7);   // six destinations plus Sign in
  for (const href of ["/product", "/getting-started", "/pricing", "/trust", "/about", "/help"]) await expect(menu.locator(`a[href="${href}"]`)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(btn).toHaveAttribute("aria-expanded", "false");
  await expect(btn).toBeFocused();
  void toggle;
});

test("v4 workflow map: keyboard selection updates the four facts (Getting Started)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page, false);
  await ready(page, "/getting-started");
  const first = page.getByRole("tab", { name: T("workflow.opportunityTitle") });
  await first.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: T("workflow.contextTitle") })).toHaveAttribute("aria-selected", "true");
  const panel = page.getByRole("tabpanel");
  for (const k of ["contextDo", "contextAsk4mo", "contextPrivate", "contextNext"]) await expect(panel).toContainText(T(`workflow.${k}`));
});

test("v4 pricing: no purchase control, Available today lists the server-enforced rows, under-consideration is labelled", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page, false);
  await ready(page, "/pricing");
  await expect(page.getByTestId("available-today").locator("tbody tr")).toHaveCount(5);
  await expect(page.getByTestId("under-consideration")).toContainText(T("pricingV4.considerLabel"));
  await expect(page.getByRole("button", { name: /buy|checkout|purchase|pay now/i })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /buy|checkout|purchase|pay now/i })).toHaveCount(0);
  await expect(page.getByTestId("price-benchmark")).toContainText(T("pricingV4.benchmarkDate"));
});

test("v4 session regression: a signed-in visitor on a marketing route gets the app link, not sign-in", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mockApi(page, true);
  await ready(page, "/getting-started");
  const header = page.getByTestId("marketing-header");
  await expect(header.getByRole("link", { name: T("marketing.goToApp") })).toBeVisible();
  await expect(header.getByRole("link", { name: T("marketing.signIn") })).toHaveCount(0);
});

for (const width of [1280, 390] as const) {
  test(`v4 app routes at ${width}px: no overflow, no marketing header, journey cues where expected`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockApi(page, true);
    const violations: string[] = [];
    for (const path of APP) {
      await ready(page, path);
      const s = await snapshot(page);
      if (s.overflow > 1) violations.push(`${path}: horizontal overflow ${s.overflow}px`);
      if (s.marketingHeader) violations.push(`${path}: marketing header leaked into the app`);
      if (s.raw.length) violations.push(`${path}: raw keys ${s.raw.join(", ")}`);
    }
    expect(violations, violations.join("\n")).toEqual([]);
    await ready(page, "/practice");
    await expect(page.getByTestId("journey-rail")).toBeVisible();
    await expect(page.getByTestId("you-are-here")).toContainText(T("journeyCues.stagePractice"));
  });
}

for (const locale of ["de", "ru"] as const) {
  for (const width of [1280, 390] as const) {
    test(`v4 new surfaces in ${locale} at ${width}px: translated, no overflow, no raw keys, floating header intact`, async ({ page, context }) => {
      await page.setViewportSize({ width, height: 900 });
      await context.addCookies([{ name: "ask4mo_locale", value: locale, url: "http://localhost:" + (process.env.E2E_PORT || "3000") }]);
      await mockApi(page, false);
      const violations: string[] = [];
      for (const path of ["/", "/getting-started", "/pricing"]) {
        await ready(page, path);
        await expect(page.locator("html")).toHaveAttribute("lang", locale, { timeout: 15_000 });
        const s = await snapshot(page);
        if (s.overflow > 1) violations.push(`${path}: horizontal overflow ${s.overflow}px`);
        if (s.raw.length) violations.push(`${path}: raw keys ${s.raw.join(", ")}`);
        if (s.video) violations.push(`${path}: video present`);
      }
      await ready(page, "/getting-started");
      await expect(page.locator("h1").first()).toHaveText(translate(locale, "gettingStarted.title"));
      await expect(page.getByTestId("story-disclosure")).toContainText(translate(locale, "gettingStarted.storyDisclosure"));
      await ready(page, "/pricing");
      await expect(page.getByTestId("under-consideration")).toContainText(translate(locale, "pricingV4.considerLabel"));
      expect(violations, violations.join("\n")).toEqual([]);
    });
  }
}
