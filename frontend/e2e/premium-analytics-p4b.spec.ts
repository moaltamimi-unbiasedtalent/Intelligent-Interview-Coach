import { expect, test, type Page } from "@playwright/test";

/**
 * W12.4D-P4-B Premium progress analytics: responsive + accessibility regression in real Chromium (backend mocked at the network layer; no provider call).
 * /progress with a server-returned `ready` analytics payload and with the disabled state x {1280, 768, 390} x {light, dark} x {en, de, ru}.
 * Programmatic checks only; no WCAG certification is claimed.
 */
const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_p4b" }, body: JSON.stringify(body) });
const account = (ui: string) => ({ user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], admin_permissions: [], response_detail: "brief", interface_locale: ui, conversation_language: ui, coaching_style: "balanced", career_geography: "",
  target_role: "", onboarding_completed: true, onboarding_step: 0 });
const rub = Object.fromEntries(["relevance", "structure", "evidence", "role_knowledge", "problem_solving", "communication", "credibility"].map((d, i) => [d, { average: 5 + (i % 4), answers_measured: 6 }]));
const pt = (id: number, score: number | null) => ({ interview_id: id, date: `2026-0${id}-10T09:00:00+00:00`, practice_score: score, answers_scored: score === null ? 0 : 4, low_sample: id === 2, report_score: score === null ? null : score - 3,
  target_role: "Senior Registered Nurse in Intensive Care", career_level: "senior", opportunity_id: null, question_count: 4, rubric: rub });
const ready = { state: "ready", truncated: true, analyzed_limit: 500, counts: { completed_interviews: 5, scored_interviews: 4, unscored_interviews: 1 },
  points: [pt(1, 52), pt(2, 61), pt(3, null), pt(4, 70), pt(5, 78)], summary: { first_score: 52, latest_score: 78, change: 26, direction: "improved", comparable_context: false, average_score: 65.3, best_score: 78 },
  distribution: { "0-39": 0, "40-59": 1, "60-79": 3, "80-100": 0 },
  rubric: { dimensions: Object.entries(rub).map(([id, v]) => ({ id, ...v })), strongest: "communication", weakest: "relevance" },
  by_question_type: [{ type: "culture_values", average_score: 66.5, answers_scored: 8 }, { type: "case_study", average_score: 61, answers_scored: 8 }],
  frequency: { last_30_days: 2, last_90_days: 4, by_month: [] }, improvement_areas: [{ area: "Use more concrete evidence and quantified outcomes", count: 5, origin: "model_generated" }],
  filters: { roles: [], opportunity_ids: [3] }, methodology: [], limitations: [] };
const compare = { state: "ready", base: pt(1, 52), target: pt(5, 78), score_difference: 26, direction: "improved", comparability: "limited", comparability_reasons: ["different_question_count", "low_sample"],
  limitations: [], methodology: [], rubric_differences: Object.keys(rub).map((id, i) => ({ id, base: 5, target: i === 2 ? null : 7, difference: i === 2 ? null : 2 })) };

async function mock(page: Page, ui: string, theme: string, analytics: unknown) {
  await page.addInitScript((th) => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
      window.localStorage.setItem("iic-theme", th);
    } catch { /* ignore */ }
  }, theme);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return json(route, account(ui));
    if (path.endsWith("/progress/analytics/compare")) return json(route, compare);
    if (path.endsWith("/progress/analytics")) return json(route, analytics);
    if (path.endsWith("/progress")) return json(route, { interviews_completed: 5, answers_evaluated: 18, average_practice_score: 65.3, most_common_improvement_area: "Evidence", average_answer_seconds: 70,
      recent_interviews: [{ id: 5, target_role: "Senior Registered Nurse in Intensive Care", mode: "text", status: "completed", questions: 4, created_at: "2026-05-10T09:00:00+00:00" }], access: { restricted: false, window: null } });
    if (path.includes("/memory")) return json(route, { memories: [] });
    if (path.endsWith("/capabilities")) return json(route, {});
    return json(route, {});
  });
}

async function inspect(page: Page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const visible = (el: Element) => { const r = (el as HTMLElement).getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const name = (el: Element) => el.getAttribute("aria-label") || (el.textContent ?? "").trim() || el.getAttribute("title");
    const raw = (text.match(/\b[a-z][a-z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){2,}\b/g) ?? []).filter((t) => !/\.(com|org|io|net|dev)\b/.test(t));
    const labelled = Array.from(document.querySelectorAll("select")).filter((s) => visible(s) && !document.querySelector(`label[for="${s.id}"]`));
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      h1: document.querySelectorAll("h1").length,
      raw: Array.from(new Set(raw)).slice(0, 5),
      unnamed: Array.from(document.querySelectorAll("a[href],button")).filter((e) => visible(e) && !name(e)).map((e) => e.outerHTML.slice(0, 80)).slice(0, 5),
      unlabelled: labelled.map((s) => s.outerHTML.slice(0, 60)),
      crashed: /Something went wrong|Application error/.test(text),
    };
  });
}

for (const ui of ["en", "de", "fr"]) {
  for (const [w, h] of [[1280, 800], [768, 1024], [390, 844]] as const) {
    for (const theme of ["light", "dark"]) {
      test(`P4-B analytics ready ${ui} ${w}px ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width: w, height: h });
        await mock(page, ui, theme, ready);
        await page.goto("/progress", { waitUntil: "domcontentloaded" });
        const root = page.getByTestId("premium-analytics");
        await expect(root).toBeVisible({ timeout: 20_000 });
        await expect(page.getByTestId("analytics-chart")).toHaveAttribute("role", "img");
        await expect(page.getByTestId("analytics-table")).toBeVisible();
        await expect(page.getByTestId("progress-trends-planned")).toHaveCount(0);
        const selects = root.locator("select");
        await selects.nth(1).selectOption("1");
        await selects.nth(2).selectOption("5");
        await expect(page.getByTestId("analytics-compare-result")).toBeVisible({ timeout: 10_000 });
        const r = await inspect(page);
        const problems: string[] = [];
        if (r.overflow > 1) problems.push(`overflow ${r.overflow}`);
        if (r.raw.length) problems.push(`raw keys ${r.raw}`);
        if (r.unnamed.length) problems.push(`unnamed ${r.unnamed}`);
        if (r.unlabelled.length) problems.push(`unlabelled ${r.unlabelled}`);
        if (r.crashed) problems.push("crashed");
        if (r.h1 < 1) problems.push("no h1");
        expect(problems).toEqual([]);
        expect(await root.locator("a, [href*='checkout']").count()).toBe(0);
      });
    }
  }
}

for (const state of ["feature_disabled", "not_entitled"]) {
  test(`P4-B analytics ${state} keeps the existing Basic progress and the planned notice with no chart`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mock(page, "en", "light", { state, truncated: false, points: [] });
    await page.goto("/progress", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("progress-trends-planned")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("premium-analytics")).toHaveCount(0);
    await expect(page.getByTestId("analytics-chart")).toHaveCount(0);
    const r = await inspect(page);
    expect(r.overflow).toBeLessThanOrEqual(1);
  });
}
