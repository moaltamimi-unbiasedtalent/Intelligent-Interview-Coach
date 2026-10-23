import { expect, test, type Page } from "@playwright/test";

import { T, hydrated, runJourney, startInterviewFromOpportunity } from "./journey/definition";
import { FIXTURES, MODE, MODE_LABEL, VARIANT, languagesToRun, makeEnv, type JourneyLocale } from "./journey/env";
import { MockWorld } from "./journey/mockWorld";

/**
 * 04D (DEMO-02, REQ-CAND-01): when the AI provider is unavailable the Candidate sees ACCURATE, LOCALIZED copy, the app never claims success, nothing is silently retried into duplicates,
 * and no provider detail or secret reaches the page. This is also the owner-named Start Interview REGRESSION: the original failure was a keyless stack on which Start Interview showed
 * the same generic "temporarily unavailable" as a passing outage; a keyless stack must now say, in the candidate's language, that AI is not configured, and say so in the mode indicator.
 *
 *   keyless       : no AI credential on the stack (the original defect's environment). Expected copy: states.aiNotConfigured, mode not_configured.
 *   provider_down : a configured provider that fails this time. Expected copy: states.aiProviderUnavailable (try again), nothing duplicated.
 *
 * mocked (always on in CI): every variant, every language.  real: only the variant the stack was started with (scripts/e2e/journey_stack.py run --variant keyless|provider_down).
 */

test.describe.configure({ mode: "serial" });

type FailureVariant = "keyless" | "provider_down";
const FAILURE_VARIANTS: FailureVariant[] = MODE === "mocked" ? ["keyless", "provider_down"] : VARIANT === "healthy" ? [] : [VARIANT as FailureVariant];
const SECRET_SHAPES = /openrouter|sk-or-|sk-[a-z0-9]{16,}|api[ _-]?key|bearer\s+[a-z0-9]/i;

function expectations(variant: FailureVariant) {
  return variant === "keyless"
    ? { key: "states.aiNotConfigured", other: "states.aiProviderUnavailable", mockedMode: "not_configured", realMode: "not_configured" }
    : { key: "states.aiProviderUnavailable", other: "states.aiNotConfigured", mockedMode: "live", realMode: "offline" };
}

/** Records every API response body and the `ai_provider_mode` the stack reported, so the secrets and the mode indicator can be checked against what really crossed the wire. */
function watchApi(page: Page) {
  const bodies: string[] = [];
  const modes: string[] = [];
  const createKeys: Array<string | undefined> = [];
  page.on("request", (r) => { if (r.method() === "POST" && new URL(r.url()).pathname.endsWith("/interviews")) createKeys.push(r.headers()["idempotency-key"]); });
  page.on("response", async (r) => {
    if (!new URL(r.url()).pathname.includes("/api/v1/")) return;
    try {
      const text = await r.text();
      bodies.push(text);
      if (/\/api\/v1\/capabilities$/.test(new URL(r.url()).pathname)) modes.push(String((JSON.parse(text) as { ai_provider_mode?: string }).ai_provider_mode));
    } catch { /* a response that cannot be read is not evidence of a leak */ }
  });
  return { bodies, modes, createKeys };
}

for (const variant of FAILURE_VARIANTS) {
  for (const [index, locale] of languagesToRun().entries()) {
    test(`provider ${variant} [${MODE_LABEL}] [${locale}]`, async ({ page, baseURL }) => {
      test.setTimeout(MODE === "real" ? 240_000 : 120_000);
      test.info().annotations.push({ type: "evidence", description: `${MODE_LABEL}; variant ${variant}` });
      const L: JourneyLocale = locale;
      const want = expectations(variant);
      const world = new MockWorld();
      world.provider = variant === "keyless" ? "not_configured" : "down";
      if (MODE === "mocked") await world.install(page);
      const api = watchApi(page);
      const env = makeEnv(L, index);
      const result = await runJourney(page, env, baseURL ?? "http://localhost:3000", { stopAfter: "opportunity" });

      await test.step(`[${MODE}/${L}] the stack states its AI mode truthfully`, async () => {
        await page.goto("/prepare");
        await hydrated(page, "#agent-goal");
        const indicator = page.getByTestId("ai-provider-mode");
        const expectedMode = MODE === "mocked" ? want.mockedMode : want.realMode;
        await expect(indicator).toHaveAttribute("data-mode", expectedMode);
        const label = expectedMode === "not_configured" ? "providerMode.notConfigured" : expectedMode === "live" ? "providerMode.live" : "providerMode.offline";
        await expect(indicator).toContainText(T(L, label));
        expect(api.modes.at(-1)).toBe(expectedMode);
      });

      await test.step(`[${MODE}/${L}] Mo says accurately that it could not run, in the candidate's language`, async () => {
        await page.goto(`/prepare?opportunity=${result.opportunityId}`);
        await hydrated(page, "#agent-goal");
        await page.locator("#agent-goal").fill(FIXTURES.mo.goal);
        await page.getByRole("button", { name: T(L, "prepare.startPreparing") }).click();
        // A hosted keyless stack refuses Mo earlier, while building retrieval (generic 503 not_configured), so there Mo shows the generic unavailable copy; everywhere else the accurate cause.
        const moKey = MODE === "real" && variant === "keyless" ? "states.serviceUnavailable" : want.key;
        await expect(page.getByRole("alert").filter({ hasText: T(L, moKey) })).toBeVisible();
        await expect(page.getByText(T(L, want.other))).toHaveCount(0);                              // the two causes are never confused
        await expect(page.getByText("The assistant isn't configured in this environment.")).toHaveCount(0);   // the server's English fallback is never shown
        await expect(page.getByText(FIXTURES.mo.reply)).toHaveCount(0);                              // and no answer is claimed
      });

      await test.step(`[${MODE}/${L}] START INTERVIEW fails once with the accurate copy, claims nothing and starts nothing`, async () => {
        const before = api.createKeys.length;
        await startInterviewFromOpportunity(page, env, result.opportunityId);
        await expect(page.getByRole("alert").filter({ hasText: T(L, want.key) })).toBeVisible();
        // THE REGRESSION: the defect showed the generic "temporarily unavailable" (and the generic start error) for a keyless stack.
        await expect(page.getByText(T(L, "states.serviceUnavailable"))).toHaveCount(0);
        await expect(page.getByText(T(L, want.other))).toHaveCount(0);
        await expect(page).not.toHaveURL(/session=/);                                              // no success claimed: still on setup
        await expect(page.getByRole("heading", { level: 1, name: FIXTURES.interview.questions[0] })).toHaveCount(0);
        // No silent retry: one click made exactly one request (a short settle so a delayed automatic retry would show).
        await page.waitForTimeout(600);
        expect(api.createKeys.length - before).toBe(1);
      });

      await test.step(`[${MODE}/${L}] pressing Start again re-sends the SAME idempotency key (one setup, never two)`, async () => {
        const before = api.createKeys.length;
        await page.getByRole("button", { name: T(L, "practice.start") }).click();
        await expect(page.getByRole("alert").filter({ hasText: T(L, want.key) })).toBeVisible();
        expect(api.createKeys.length - before).toBe(1);
        const [first, second] = api.createKeys.slice(-2);
        expect(first).toBeTruthy();
        expect(second).toBe(first);
      });

      await test.step(`[${MODE}/${L}] nothing was recorded as practice and no secret reached the page`, async () => {
        await page.goto("/history");
        await expect(page.getByRole("heading", { name: T(L, "history.emptyTitle") })).toBeVisible();
        const everything = api.bodies.join("\n") + (await page.content());
        expect(everything).not.toMatch(SECRET_SHAPES);
      });
    });
  }
}

// The Mo run list in the failure variants: a failed run is listed as such, and only this candidate's own runs are listed.
if (MODE === "mocked") {
  test("the owner-scoped run list marks a failed run and shows nothing of another candidate", async ({ page, baseURL }) => {
    test.setTimeout(120_000);
    const world = new MockWorld();
    world.provider = "down";
    await world.install(page);
    const env = makeEnv("en", 0);
    const result = await runJourney(page, env, baseURL ?? "http://localhost:3000", { stopAfter: "opportunity" });
    await page.goto(`/prepare?opportunity=${result.opportunityId}`);
    await hydrated(page, "#agent-goal");
    await page.locator("#agent-goal").fill(FIXTURES.mo.goal);
    await page.getByRole("button", { name: T("en", "prepare.startPreparing") }).click();
    await expect(page.getByTestId("mo-ai-failure")).toBeVisible();
    await page.goto("/prepare");
    await hydrated(page, "#agent-goal");
    await expect(page.getByTestId("recent-run")).toHaveCount(1);
    await expect(page.getByTestId("recent-run").first()).toContainText(T("en", "recentRuns.stateFailed"));
  });

  test("a malformed run-list response shows the explicit error state, never a silent empty list", async ({ page, baseURL }) => {
    test.setTimeout(120_000);
    const world = new MockWorld();
    await world.install(page);
    await runJourney(page, makeEnv("en", 1), baseURL ?? "http://localhost:3000", { stopAfter: "opportunity" });
    await page.route("**/api/v1/agent/runs?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ oops: true }) }));
    await page.goto("/prepare");
    await hydrated(page, "#agent-goal");
    await expect(page.getByText(T("en", "recentRuns.loadError"))).toBeVisible();
    await expect(page.getByTestId("recent-runs-empty")).toHaveCount(0);
  });
}
