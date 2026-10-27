import { expect, test, type Page } from "@playwright/test";

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { candidateReady, historyReady, observeHistory, qualifyHistoryImage, SECURITY_OBSERVATION_MS } from "./fixtures/historyReadiness";

import table from "../tests/fixtures/deferral-table-07a.json";

// 07A (PG-10, REQ-DEFER-01): browser evidence that every DEFERRED or GATED family is unreachable for a Candidate and for an Admin while its gate is off. The family table comes
// from tests/_deferral_table_07a.py (generated JSON mirror); the API refusals are proven against the real FastAPI app in tests/test_deferral_inaccessibility_07a.py. Here the
// backend is mocked at the network layer exactly as the server answers with every gate off, and the specs assert that no link, button, route or capability text exposes a
// deferred feature, that direct URL navigation answers the not-found page, and that NO request ever goes to a gated endpoint or to a host other than the app itself.

const FAMILIES = table.families;
const ABSENT_PATHS = FAMILIES.flatMap((f) => f.ui_absent_paths);
const ABSENT_TEXTS = FAMILIES.flatMap((f) => f.ui_absent_texts.map((t) => ({ family: f.id, re: new RegExp(t, "i") })));
// Endpoints that must never be requested by the UI while the gates are off (only their inert, read-only siblings may be).
const FORBIDDEN_API = /\/speech\/(transcriptions|synthesis)|\/billing\/(checkout-sessions|webhooks)|\/voice\/realtime\/session(?!\/end)|\/admin\/billing\/(price-changes|payments\/[^/]+\/refunds|refunds\/[^/]+\/(approve|reject))|\/admin\/billing\/operations\/(events|subscriptions)\/[^/]+\/(retry|requeue|reconcile)|\/compensation|\/international|\/global/;

const ALL_PERMS = ["platform.overview.read", "platform.users.read", "platform.audit.read", "platform.integrations.read", "platform.ai.read", "platform.knowledge.read", "platform.flags.read",
  "platform.billing.read", "platform.billing.recover", "platform.jobs.read", "platform.support.read", "platform.workspaces.read", "platform.plans.read", "platform.privacy.read",
  "platform.reports.read", "platform.security.read"];

const CAPS_OFF = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true,
  human_in_the_loop: true, agent_coach_enabled: true, realtime_voice_enabled: false, company_research_enabled: false };
const NONE = { checkout: "none", subscription: "none", payment: "none", confirmation: "not_applicable", entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false },
  checkout_id: null, created_at: null, expires_at: null };
const SPEECH_CAPS = { server_stt_languages: [], server_tts_languages: [], browser_stt_allowed: true, browser_tts_allowed: true, product_languages: ["en"], excluded_languages: ["ru"], audio_persisted: false, browser_disclosure: "" };

function account(role: string, perms: string[]) {
  return { user_id: 1, email: "u@example.com", display_name: null, platform_role: role, tier: "basic", status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0 };
}

interface Log { api: string[]; external: string[] }

/** Mock the API as the server answers with every gate off, and record every API path and every non-local request. */
async function mock(page: Page, role: string, perms: string[]): Promise<Log> {
  const log: Log = { api: [], external: [] };
  // The app's own origin and the product API origin (every API request is answered by the mock below; none reaches a real backend) are the only hosts allowed.
  const allowed = new Set([new URL(process.env.BASE_URL || `http://localhost:${process.env.E2E_PORT || "3000"}`).origin,
    new URL(process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").origin]);
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (!allowed.has(url.origin) && !url.protocol.startsWith("data") && !url.protocol.startsWith("blob")) log.external.push(`${req.method()} ${url.origin}${url.pathname}`);
  });
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    log.api.push(`${req.method()} ${path}`);
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return json(account(role, perms));
    if (path.endsWith("/capabilities")) return json(CAPS_OFF);
    if (path.endsWith("/auth/plan")) return json({ plan: { plan_code: "basic", plan_name: "Basic", version: 1 }, entitlements: {} });
    if (path.endsWith("/billing/checkout/availability")) return json({ plan: "premium", available: false, reason: "not_enabled" });
    if (path.endsWith("/billing/checkout/status")) return json(NONE);
    if (path.endsWith("/speech/capabilities")) return json(SPEECH_CAPS);
    if (path.endsWith("/voice/realtime/status")) return json({ enabled: false, configured: false, available: false, provider: "openai_realtime", supported_locales: ["en"], max_session_seconds: 300, max_concurrent_per_user: 1, fallback: "turn_based_voice" });
    if (path.endsWith("/model-profiles")) return json({ selector_active: false, default: "balanced", profiles: [] });
    // Valid, empty read contracts: {} used to crash Opportunities and Practice
    // while the old global-idle wait still reported those pages as ready.
    if (path.endsWith("/opportunities")) return json({ opportunities: [] });
    if (path.endsWith("/interviews/options")) return json({ career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: [] });
    if (path.endsWith("/interviews")) return json({ sessions: [] });
    if (path.endsWith("/history/interviews")) return json({ interviews: [] });
    if (path.endsWith("/memory")) return json({ memories: [] });
    if (path.endsWith("/progress")) return json({ interviews_completed: 0, answers_evaluated: 0, recent_interviews: [], recent_scores: [], improvement_areas: [] });
    if (path.endsWith("/documents")) return json({ documents: [] });
    if (path.endsWith("/workspaces")) return json({ workspaces: [], invited: [] });
    if (path.endsWith("/shares/mine") || path.endsWith("/shares/with-me")) return json({ shares: [] });
    if (path.endsWith("/ownership-transfers/mine")) return json({ transfers: [] });
    if (path.endsWith("/agent/runs")) return json({ runs: [] });
    return json({});
  });
  return log;
}

function assertClean(log: Log) {
  expect(log.api.filter((l) => FORBIDDEN_API.test(l)), "a gated endpoint was requested").toEqual([]);
  expect(log.external, "a request left the app (no provider, no payment host)").toEqual([]);
}

function hits(text: string) {
  return ABSENT_TEXTS.filter(({ re }) => re.test(text)).map(({ family, re }) => `${family}:${re.source}`);
}

const CANDIDATE_PAGES = ["/opportunities", "/prepare", "/practice", "/progress", "/history", "/settings", "/account", "/pricing", "/documents", "/workspaces"];

test("Candidate: no page requests a gated endpoint or contacts an external host, and the More menu exposes nothing deferred", async ({ page }, info) => {
  const observation = observeHistory(page);
  const log = await mock(page, "user", []);
  try {
    for (const path of CANDIDATE_PAGES) {
      const response = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(response?.status(), path).toBe(200);
      await candidateReady(page, path);
      await observation.ready(path);
      if (path === "/history") {
        await historyReady(page);
        await qualifyHistoryImage(page.locator("#main img"), observation);
      }
      // An observation window AFTER readiness preserves deferred initialization
      // coverage. It is not the readiness condition and does not require idleness.
      await page.waitForTimeout(SECURITY_OBSERVATION_MS);
      assertClean(log);
      expect(observation.consoleErrors, path).toEqual([]);
      expect(observation.pageErrors, path).toEqual([]);
      expect(observation.transportFailures, path).toEqual([]);
    }
    await page.goto("/opportunities");
    await page.getByRole("button", { name: /more/i }).first().click();
    const items = page.getByRole("menuitem");
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(4);
    for (let i = 0; i < count; i++) {
      const text = (await items.nth(i).textContent()) ?? "";
      const href = (await items.nth(i).getAttribute("href")) ?? "/";
      expect(hits(text), text).toEqual([]);
      expect(ABSENT_PATHS.find((p) => href === p || href.startsWith(p + "/")), href).toBeUndefined();
    }
    // The primary navigation (desktop) carries only the five product destinations.
    const primary = await page.getByRole("navigation").first().getByRole("link").allTextContents();
    expect(hits(primary.join(" | "))).toEqual([]);
    assertClean(log);
  } finally { await observation.attach(info, "candidate-readiness-diagnostics"); }
});

test("Candidate: the account page offers no checkout, only the truthful 'not enabled' state, and starts no checkout", async ({ page }) => {
  const log = await mock(page, "user", []);
  await page.goto("/account");
  await expect(page.getByTestId("checkout-unavailable")).toBeVisible();
  await expect(page.getByTestId("checkout-start")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /checkout|subscribe|upgrade|pay now|buy/i })).toHaveCount(0);
  assertClean(log);
  expect(log.api.filter((l) => l.startsWith("POST") && l.includes("/billing/"))).toEqual([]);
});

test("Candidate: Practice shows no live-voice entry while realtime voice is off, and requests no realtime session", async ({ page }) => {
  const log = await mock(page, "user", []);
  const sid = "sess_deferral_07a";
  await page.route("**/api/v1/interviews/**", async (route) => {
    const url = route.request().url();
    const json = (b: unknown) => route.fulfill({ status: 200, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (url.includes("/interviews/options")) return json({ deep_dive_modes: [] });
    return json({ session_id: sid, state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
      current_question: { question_id: 1, question: "Question 1: tell me about a decision.", question_type: "behavioural", competency: "judgement", difficulty: "moderate" },
      report_available: false, last_evaluation: null, target_role: "Senior PM", deep_dive: null, error: null, error_recoverable: false, cumulative_cost_usd: 0 });
  });
  await page.goto(`/practice?session=${sid}`);
  await expect(page.getByRole("heading", { name: /tell me about a decision/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /submit answer/i })).toBeVisible();          // the turn-based path stays
  await expect(page.getByTestId("realtime-practice")).toHaveCount(0);
  await expect(page.locator("summary", { hasText: /live voice/i })).toHaveCount(0);
  assertClean(log);
});

const DIRECT = ABSENT_PATHS.filter((p) => !p.startsWith("/admin"));
test("Candidate: direct navigation to every deferred path answers the not-found page", async ({ page }) => {
  const log = await mock(page, "user", []);
  expect(DIRECT.length).toBeGreaterThan(15);
  for (const path of DIRECT) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(404);
    expect(page.url(), path).toContain(path);
    await expect(page.getByTestId("checkout-start")).toHaveCount(0);
  }
  assertClean(log);
});

test("Admin: navigation exposes no deferred feature and Billing and Speech state that they are mock / not active", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const log = await mock(page, "platform_admin", ALL_PERMS);
  await page.goto("/admin/review");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(nav.getByRole("link").first()).toBeVisible();
  for (const section of await nav.getByRole("button", { expanded: false }).all()) await section.click();
  const links = nav.getByRole("link");
  const count = await links.count();
  expect(count).toBeGreaterThan(10);
  for (let i = 0; i < count; i++) {
    const text = (await links.nth(i).textContent()) ?? "";
    const href = (await links.nth(i).getAttribute("href")) ?? "";
    expect(hits(text), text).toEqual([]);
    expect(ABSENT_PATHS.find((p) => href === p || href.startsWith(p + "/")), href).toBeUndefined();
  }
  expect(await nav.getByRole("link", { name: "Billing" }).getAttribute("href")).toBe("/admin/billing");
  assertClean(log);
});

for (const [path, truth] of [["/admin/billing", /mock|not live|disabled/i], ["/admin/speech", /not active|not operational|not authorized|governed/i]] as const) {
  test(`Admin: ${path} shows no live control and calls no gated endpoint`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const log = await mock(page, "platform_admin", ALL_PERMS);
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const body = await page.locator("body").innerText();
    expect(body).toMatch(truth);
    expect(body).not.toMatch(/go live|enable live|live payments? (are )?(on|enabled)|start checkout/i);
    await expect(page.getByRole("button", { name: /go live|enable live|start checkout|subscribe/i })).toHaveCount(0);
    assertClean(log);
  });
}

test("Admin: direct navigation to deferred Admin paths answers the not-found page", async ({ page }) => {
  const log = await mock(page, "platform_admin", ALL_PERMS);
  const admin = ABSENT_PATHS.filter((p) => p.startsWith("/admin"));
  expect(admin.length).toBeGreaterThanOrEqual(5);
  for (const path of admin) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(404);
  }
  assertClean(log);
});

for (const scale of [1, 2]) {
  test(`History image: real production optimizer, loaded pixels and enforced CSP at DPR ${scale}`, async ({ browser }, info) => {
    const context = await browser.newContext({ deviceScaleFactor: scale, baseURL: process.env.BASE_URL || `http://localhost:${process.env.E2E_PORT || "3000"}` });
    const page = await context.newPage();
    const observation = observeHistory(page);
    const log = await mock(page, "user", []);
    try {
      const asset = readFileSync(resolve(__dirname, "../public/images/ask4mo/ask4mo-empty-history-ink.png"));
      expect(asset.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
      expect(asset.readUInt32BE(16)).toBeGreaterThan(0);
      expect(asset.readUInt32BE(20)).toBeGreaterThan(0);
      const response = (await page.goto("/history", { waitUntil: "domcontentloaded" }))!;
      const csp = response.headers()["content-security-policy"];
      expect(csp).toContain("img-src 'self' data: blob:");
      expect(csp).toMatch(/script-src 'self' 'nonce-[^']+'/);
      await historyReady(page);
      await candidateReady(page, "/history");
      await observation.ready("/history");
      const image = await qualifyHistoryImage(page.locator("#main img"), observation);
      expect(image.origin).toBe(new URL(page.url()).origin);
      await page.waitForTimeout(SECURITY_OBSERVATION_MS);
      expect(observation.imageResponses).toHaveLength(1);
      expect(observation.imageResponses[0].status).toBe(200);
      expect(observation.snapshot().outstanding.filter(url => url.endsWith("/_next/image"))).toEqual([]);
      expect(observation.consoleErrors).toEqual([]);
      expect(observation.pageErrors).toEqual([]);
      expect(observation.transportFailures).toEqual([]);
      assertClean(log);
      const imagePath = info.outputPath("history-image-loaded-state.json");
      writeFileSync(imagePath, JSON.stringify({ ...image, sourceBytes: asset.length, sourceWidth: asset.readUInt32BE(16), sourceHeight: asset.readUInt32BE(20) }));
      await info.attach("history-image-loaded-state", { path: imagePath, contentType: "application/json" });
    } finally { await observation.attach(info, "history-image-diagnostics"); await context.close(); }
  });
}

test("History image: real missing optimizer asset is a distinct failure while navigation stays usable", async ({ page }, info) => {
  const observation = observeHistory(page);
  const log = await mock(page, "user", []);
  try {
    await page.goto("/history", { waitUntil: "domcontentloaded" });
    await historyReady(page);
    await qualifyHistoryImage(page.locator("#main img"), observation);
    // Fault injection only: request a REAL missing local asset through the real
    // optimizer. Nothing is intercepted, hidden, removed or changed in the app.
    const failed = page.waitForResponse(response => response.url().includes("missing-history-qualification.png"));
    await page.locator("#main img").evaluate(node => {
      const image = node as HTMLImageElement;
      image.srcset = "";
      image.src = "/_next/image?url=%2Fimages%2Fask4mo%2Fmissing-history-qualification.png&w=384&q=75";
    });
    expect((await failed).status()).toBe(400);
    await expect(qualifyHistoryImage(page.locator("#main img"), observation)).rejects.toThrow("history_image_http_400");
    await historyReady(page);
    await candidateReady(page, "/history");
    await page.waitForTimeout(SECURITY_OBSERVATION_MS);
    expect(observation.imageResponses.filter(response => response.status === 400)).toHaveLength(1);
    expect(observation.snapshot().outstanding.filter(url => url.endsWith("/_next/image"))).toEqual([]);
    await page.getByRole("link", { name: "Start Practice", exact: true }).click();
    await expect(page).toHaveURL(/\/practice$/);
    await observation.confirmPracticeNavigation();
    await observation.ready("/practice");
    expect(observation.consoleErrors).toEqual(["http_400"]);
    expect(observation.pageErrors).toEqual([]);
    expect(observation.transportFailures).toEqual([]);
    assertClean(log);
  } finally { await observation.attach(info, "history-expected-image-failure"); }
});

test("Candidate readiness observer: a delayed gated request still fails security after the UI is ready", async ({ page }, info) => {
  const observation = observeHistory(page);
  const log = await mock(page, "user", []);
  try {
    await page.goto("/history", { waitUntil: "domcontentloaded" });
    await historyReady(page);
    await qualifyHistoryImage(page.locator("#main img"), observation);
    // Synthetic detector control only. This remains in the API route mock and
    // reaches no backend/provider. It proves the post-readiness window is active.
    await page.evaluate(() => { setTimeout(() => { void fetch("http://localhost:8000/api/v1/compensation"); }, 250); });
    await page.waitForTimeout(SECURITY_OBSERVATION_MS);
    expect(log.api).toContain("GET /api/v1/compensation");
    expect(() => assertClean(log)).toThrow(/a gated endpoint was requested/);
    expect(log.external).toEqual([]);
    expect(observation.consoleErrors).toEqual([]);
    expect(observation.pageErrors).toEqual([]);
  } finally { await observation.attach(info, "history-security-observer-control"); }
});
