import { expect, test, type Page } from "@playwright/test";

/**
 * W12.4D-P3 Basic/Premium candidate experience: responsive + accessibility regression in real Chromium (backend mocked at the network layer, no provider call).
 * Surfaces: /pricing, /account (plan overview + model profiles), /history (restricted notice), /history/12 (restricted detail), /progress (scope + planned trends)
 * x {1280, 768, 390} x {light, dark} x {en, de, ru}. Programmatic checks only; no WCAG certification is claimed.
 */
const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_p3" }, body: JSON.stringify(body) });
const account = (ui: string) => ({ user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], admin_permissions: [], response_detail: "brief", interface_locale: ui, conversation_language: ui, coaching_style: "balanced", career_geography: "",
  target_role: "", onboarding_completed: true, onboarding_step: 0 });

async function mock(page: Page, ui: string, theme: string) {
  await page.addInitScript((th) => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
      window.localStorage.setItem("iic-theme", th);
    } catch { /* ignore */ }
  }, theme);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return json(route, account(ui));
    if (path.endsWith("/model-profiles")) return json(route, { selector_active: false, default: "balanced", profiles: [
      { id: "fast", authorized: true, description: "x" }, { id: "balanced", authorized: true, description: "x" }, { id: "advanced", authorized: true, description: "x" }] });
    if (path.endsWith("/history/interviews")) return json(route, { interviews: [], access: { restricted: true, window: 3, hidden_count: 4 } });
    if (path.includes("/history/interviews/")) return json(route, { error: { code: "history_not_available", message: "x" } }, 403);
    if (path.includes("/progress")) return json(route, { interviews_completed: 3, answers_evaluated: 9, average_practice_score: 6.5, most_common_improvement_area: null, average_answer_seconds: null,
      recent_interviews: [], access: { restricted: true, window: 3 } });
    if (path.endsWith("/auth/plan")) return json(route, { plan: { plan_code: "basic", plan_name: "Basic", version: 1 }, entitlements: {} });
    if (path.includes("/capabilities")) return json(route, {});
    return json(route, {});
  });
}

async function inspect(page: Page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const visible = (el: Element) => { const r = (el as HTMLElement).getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const name = (el: Element) => el.getAttribute("aria-label") || (el.textContent ?? "").trim() || el.getAttribute("title");
    const raw = (text.match(/\b[a-z][a-z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){2,}\b/g) ?? []).filter((t) => !/\.(com|org|io|net|dev)\b/.test(t));
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      h1: document.querySelectorAll("h1").length,
      raw: Array.from(new Set(raw)).slice(0, 5),
      unnamed: Array.from(document.querySelectorAll("a[href],button")).filter((e) => visible(e) && !name(e)).map((e) => e.outerHTML.slice(0, 80)).slice(0, 5),
      crashed: /Something went wrong|Application error/.test(text),
    };
  });
}

const SURFACES: { path: string; testid: string }[] = [
  { path: "/pricing", testid: "premium-status" },
  { path: "/account", testid: "plan-overview" },
  { path: "/history", testid: "history-access-notice" },
  { path: "/history/12", testid: "history-restricted" },
  { path: "/progress", testid: "progress-trends-planned" },
];

for (const ui of ["en", "de", "fr"]) {
  for (const [w, h] of [[1280, 800], [768, 1024], [390, 844]] as const) {
    for (const theme of ["light", "dark"]) {
      test(`P3 plan UX surfaces ${ui} ${w}px ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width: w, height: h });
        const problems: string[] = [];
        for (const s of SURFACES) {
          await page.unrouteAll({ behavior: "ignoreErrors" });
          await mock(page, ui, theme);
          await page.goto(s.path, { waitUntil: "domcontentloaded" });
          await expect(page.getByTestId(s.testid).first()).toBeVisible({ timeout: 20_000 });
          const r = await inspect(page);
          if (r.overflow > 1) problems.push(`${s.path} overflow ${r.overflow}`);
          if (r.raw.length) problems.push(`${s.path} raw keys ${r.raw}`);
          if (r.unnamed.length) problems.push(`${s.path} unnamed ${r.unnamed}`);
          if (r.crashed) problems.push(`${s.path} crashed`);
          if (s.path !== "/history/12" && r.h1 < 1) problems.push(`${s.path} no h1`);
          if (s.path === "/pricing") {
            expect(await page.locator("a[href*='checkout'], a[href*='subscribe']").count()).toBe(0);
          }
          if (s.path === "/account") {
            await expect(page.getByTestId("model-profiles").first()).toBeVisible();
            expect(await page.getByTestId("model-profiles").locator("button, select, input, [role=radio]").count()).toBe(0);
          }
        }
        expect(problems).toEqual([]);
      });
    }
  }
}
