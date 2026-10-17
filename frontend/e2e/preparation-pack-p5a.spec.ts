import { expect, test, type Page } from "@playwright/test";

/**
 * W12.4D-P5-A Opportunity Preparation Pack: responsive + accessibility regression in real Chromium (backend mocked at the network layer; no provider call).
 * /opportunities/1 with saved Packs in each availability state, the opened Pack view and a failed Pack x {1280, 768, 390} x {light, dark} x {en, de, ru}.
 * Programmatic checks only; no WCAG certification is claimed.
 */
const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_p5a" }, body: JSON.stringify(body) });
const account = (ui: string) => ({ user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: ["current_market_research"], admin_permissions: [], response_detail: "brief", interface_locale: ui, conversation_language: ui, coaching_style: "balanced",
  career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 });
const OPP = { id: 1, title: "Senior Registered Nurse in Intensive Care at the University Hospital", target_role: "Senior Registered Nurse", company_name: "Acme Hospital", company_location: "Berlin",
  company_country: "DE", company_domain: null, job_description_document_id: null, status: "active", notes: null, jd_available: false, interview_ids: [], interview_count: 0 };
const item = (kind: string, text: string, category: string, extra: Record<string, unknown> = {}) => ({ kind, text, category, source_ids: [], ref_ids: [], meta: {}, ...extra });
const CONTENT = { schema_version: "pack-1", opportunity: {}, inputs: {}, sections: [
  { id: "overview", status: "partial", items: [item("role", "Senior Registered Nurse in Intensive Care with extended responsibilities for the whole ward", "opportunity_provided"), item("missing", "employer", "unavailable")], notes: ["no_job_description"] },
  { id: "company", status: "available", items: [item("business_market", "Acme Hospital operates a 40-bed intensive care unit serving a large metropolitan region.", "verified_external", { source_ids: ["W:s1"] })], notes: ["unsourced_claims_dropped"] },
  { id: "requirements", status: "available", items: [item("requirement", "Lead and mentor a team of junior nurses on the ward", "opportunity_provided")], notes: [] },
  { id: "alignment", status: "partial", items: [item("alignment", "Lead and mentor a team of junior nurses on the ward", "candidate_provided", { meta: { status: "supported" } })], notes: ["candidate_claims_not_verified"] },
  { id: "gaps", status: "available", items: [item("evidence_gap", "Strong communication with families and stakeholders", "ai_guidance", { meta: { method: "deterministic" } })], notes: ["absence_of_evidence_is_not_absence_of_skill"] },
  { id: "questions", status: "available", items: [item("question", "Tell me about a time you led a team through a difficult shift and what you changed afterwards.", "ai_guidance", { meta: { question_type: "leadership", evidence_to_prepare: "A leadership example", follow_ups: "What would you do differently?" } })], notes: [] },
  { id: "examples", status: "available", items: [item("example", "Led and mentored junior nurses on the intensive care ward", "candidate_provided")], notes: [] },
  { id: "roadmap", status: "available", items: [item("roadmap_step", "Write one leadership example in your own words and rehearse it aloud.", "ai_guidance", { meta: { action_type: "prepare_example", order: "1" } })], notes: ["no_interview_date_assumed"] },
  { id: "sources", status: "available", items: [], notes: [] }],
  sources: [{ id: "W:s1", title: "Acme Hospital about page", url: "https://acme.example/about", category: "verified_external", provider: "company_web", retrieved_at: "2026-10-01T00:00:00Z", effective_date: "2026-09-01", self_reported: true }],
  assumptions: ["no_interview_date_assumed", "no_geography_inferred_from_interface_language"], limitations: ["compensation_not_included_p10c", "not_a_hiring_decision_or_guarantee", "ai_guidance_is_not_a_verified_fact"] };
const sum = (id: number, status: string, extra = {}) => ({ id, opportunity_id: 1, revision: id, status, schema_version: "pack-1", failure_category: null, created_at: "2026-10-10T10:00:00+00:00", completed_at: null, section_statuses: {}, ...extra });

async function mock(page: Page, ui: string, theme: string, generation: string) {
  await page.addInitScript((th) => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
      window.localStorage.setItem("iic-theme", th);
    } catch { /* ignore */ }
  }, theme);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return json(route, account(ui));
    if (path.endsWith("/opportunities/1")) return json(route, OPP);
    if (path.endsWith("/opportunities/1/packs/availability")) return json(route, { generation });
    if (path.endsWith("/opportunities/1/packs")) return json(route, { packs: [sum(3, "failed", { failure_category: "ungrounded_output" }), sum(2, "insufficient_evidence"), sum(1, "completed")] });
    if (path.endsWith("/preparation-packs/1")) return json(route, { ...sum(1, "completed"), content: CONTENT });
    if (path.endsWith("/capabilities")) return json(route, {});
    return json(route, {});
  });
}

async function inspect(page: Page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const visible = (el: Element) => { const r = (el as HTMLElement).getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const name = (el: Element) => el.getAttribute("aria-label") || (el.textContent ?? "").trim() || el.getAttribute("title");
    const raw = (text.match(/\b[a-z][a-z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){2,}\b/g) ?? []).filter((t) => !/\.(com|org|io|net|dev|example)\b/.test(t));
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      h1: document.querySelectorAll("h1").length,
      raw: Array.from(new Set(raw)).slice(0, 5),
      unnamed: Array.from(document.querySelectorAll("a[href],button")).filter((e) => visible(e) && !name(e)).map((e) => e.outerHTML.slice(0, 80)).slice(0, 5),
      crashed: /Something went wrong|Application error/.test(text),
    };
  });
}

for (const ui of ["en", "de", "ru"]) {
  for (const [w, h] of [[1280, 800], [768, 1024], [390, 844]] as const) {
    for (const theme of ["light", "dark"]) {
      test(`P5-A pack section ${ui} ${w}px ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width: w, height: h });
        await mock(page, ui, theme, "feature_disabled");
        await page.goto("/opportunities/1", { waitUntil: "domcontentloaded" });
        const section = page.getByTestId("pack-section");
        await expect(section).toBeVisible({ timeout: 20_000 });
        await expect(page.getByTestId("pack-list").locator("li")).toHaveCount(3);
        await expect(page.getByTestId("pack-availability")).toHaveAttribute("data-generation", "feature_disabled");
        await page.getByTestId("pack-list").locator("li").nth(2).locator("button").first().click();
        await expect(page.getByTestId("pack-view")).toBeVisible({ timeout: 10_000 });
        for (const id of ["overview", "company", "requirements", "alignment", "gaps", "questions", "examples", "roadmap", "sources"]) await expect(page.getByTestId(`pack-section-${id}`)).toBeVisible();
        const r = await inspect(page);
        const problems: string[] = [];
        if (r.overflow > 1) problems.push(`overflow ${r.overflow}`);
        if (r.raw.length) problems.push(`raw keys ${r.raw}`);
        if (r.unnamed.length) problems.push(`unnamed ${r.unnamed}`);
        if (r.crashed) problems.push("crashed");
        if (r.h1 < 1) problems.push("no h1");
        expect(problems).toEqual([]);
        expect(await page.locator("a[href*='checkout'], a[href*='subscribe']").count()).toBe(0);
      });
    }
  }
}

for (const generation of ["not_entitled", "available"]) {
  test(`P5-A generation ${generation}: Generate button exists only when the server says available`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mock(page, "en", "light", generation);
    await page.goto("/opportunities/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("pack-availability")).toHaveAttribute("data-generation", generation, { timeout: 20_000 });
    await expect(page.getByRole("button", { name: "Generate Pack" })).toHaveCount(generation === "available" ? 1 : 0);
    const r = await inspect(page);
    expect(r.overflow).toBeLessThanOrEqual(1);
  });
}
