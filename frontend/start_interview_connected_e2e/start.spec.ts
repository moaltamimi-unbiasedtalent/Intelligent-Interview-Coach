import { expect, test, type Page } from "@playwright/test";
import { T, hydrated, runJourney, startInterviewFromOpportunity } from "../e2e/journey/definition";
import { FIXTURES, VARIANT, languagesToRun, makeEnv } from "../e2e/journey/env";

const api = process.env.JOURNEY_API_URL!;
async function state(page: Page) {
  return page.evaluate(async (base) => {
    const get = async (path: string) => {
      const r = await fetch(base + path, { credentials: "include" });
      return { status: r.status, body: await r.json() };
    };
    const active = await get("/interviews");
    const history = await get("/history/interviews");
    return { activeStatus: active.status, activeCount: active.body.sessions.length,
      historyStatus: history.status, historyCount: history.body.interviews.length };
  }, api);
}

for (const [index, locale] of languagesToRun().entries()) {
  test(`real offline start boundary: ${VARIANT} ${locale}`, async ({ page, baseURL, browser }) => {
    await page.route("**/*", route => {
      const host = new URL(route.request().url()).hostname;
      return host === "localhost" || host === "127.0.0.1" ? route.continue() : route.abort("blockedbyclient");
    });
    const env = makeEnv(locale, index);
    const requests: Array<string | undefined> = [];
    page.on("request", r => {
      if (r.method() === "POST" && new URL(r.url()).pathname === "/api/v1/interviews") requests.push(r.headers()["idempotency-key"]);
    });
    const journey = await runJourney(page, env, baseURL!, { stopAfter: "opportunity" });
    const before = await state(page);
    expect(before).toEqual({ activeStatus: 200, activeCount: 0, historyStatus: 200, historyCount: 0 });
    const anonymous = await browser.newContext();
    try {
      const res = await anonymous.request.get(`${api}/interviews`);
      expect(res.status()).toBe(401);
    } finally { await anonymous.close(); }
    await page.goto("/prepare"); await hydrated(page, "#agent-goal");
    await expect(page.getByTestId("ai-provider-mode")).toHaveAttribute("data-mode", VARIANT === "keyless" ? "not_configured" : "offline");
    const first = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/interviews" && r.request().method() === "POST");
    await startInterviewFromOpportunity(page, env, journey.opportunityId);
    const response = await first;
    if (VARIANT === "healthy") {
      expect(response.status()).toBe(200);
      await expect(page).toHaveURL(/\/practice\?session=/);
      await expect(page.getByRole("heading", { level: 1, name: FIXTURES.interview.questions[0] })).toBeVisible();
      expect(requests).toHaveLength(1);
      expect((await state(page)).activeCount).toBe(1);
      return;
    }
    const expectedCode = VARIANT === "keyless" ? "ai_not_configured" : "ai_provider_unavailable";
    const copy = VARIANT === "keyless" ? "states.aiNotConfigured" : "states.aiProviderUnavailable";
    const other = VARIANT === "keyless" ? "states.aiProviderUnavailable" : "states.aiNotConfigured";
    expect(response.status()).toBe(503);
    const body = await response.json();
    expect(body.error.code).toBe(expectedCode);
    expect(JSON.stringify(body)).not.toMatch(/openrouter|sk-or-|bearer\s+[a-z0-9]|api[ _-]?key|traceback/i);
    await expect(page.getByRole("alert").filter({ hasText: T(locale, copy) })).toBeVisible();
    await expect(page.getByText(T(locale, other))).toHaveCount(0);
    await expect(page).not.toHaveURL(/session=/);
    await expect(page.getByRole("heading", { level: 1, name: FIXTURES.interview.questions[0] })).toHaveCount(0);
    expect(requests).toHaveLength(1);
    expect(await state(page)).toEqual(before);
    const second = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/interviews" && r.request().method() === "POST");
    await page.getByRole("button", { name: T(locale, "practice.start") }).click();
    const retry = await second;
    expect(retry.status()).toBe(503);
    expect((await retry.json()).error.code).toBe(expectedCode);
    await expect(page.getByRole("alert").filter({ hasText: T(locale, copy) })).toBeVisible();
    expect(requests).toHaveLength(2);
    expect(requests[0]).toBeTruthy(); expect(requests[1]).toBe(requests[0]);
    expect(await state(page)).toEqual(before);
    expect(await page.locator("body").innerText()).not.toMatch(/openrouter|sk-or-|bearer\s+[a-z0-9]|api[ _-]?key|traceback/i);
  });
}
