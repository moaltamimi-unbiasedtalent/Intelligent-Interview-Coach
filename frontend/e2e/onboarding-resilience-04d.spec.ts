import { expect, test, type Page } from "@playwright/test";

// 04D regression: onboarding progress must survive a late /auth/me, a late route update, a remount and a reload, and a failed save must never advance.
// ROOT CAUSE (proved with a throttled production build and mount logging): the shell wrapped RouteGuard in <Suspense fallback={children}>. RouteGuard suspended on useSearchParams,
// so the fallback was a SECOND copy of the page. The candidate used the first copy (click -> POST {"step":1} -> 200), then the boundary resolved, the used copy was unmounted and a fresh
// copy mounted from the stale /auth/me account (onboarding_step 0): "Step 1 of 7 . Welcome" with "Get started" again, and the next "Continue" never appeared.
// The deterministic proof of the mechanism lives in tests/onboarding-resilience-04d.test.tsx (it fails on the old shell). These browser scenarios cover the same contract end to end; the
// swap itself is timing dependent in a browser (it needs a slow client), so they are scenario coverage, not the only guard.
// Mocked at the network layer; no backend, no provider calls, no arbitrary sleeps, no raised timeouts, no forced clicks.

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: false, onboarding_step: 0, ...over,
  };
}

interface World {
  step: number;
  completed: boolean;
  failStepPosts: number;            // the next N step saves answer 500
  posts: Array<Record<string, unknown>>;
  meHold: Promise<void> | null;     // /auth/me answers are held until this resolves; each answer carries the state AT REQUEST TIME (a stale read)
}

async function mock(page: Page, w: World, opts: { meLatencyMs?: number } = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) {
      const snapshot = account({ onboarding_completed: w.completed, onboarding_step: w.step });
      if (w.meHold) await w.meHold;
      if (opts.meLatencyMs) await new Promise((r) => setTimeout(r, opts.meLatencyMs));   // network latency of the identity read
      return json(snapshot);
    }
    if (url.includes("/auth/onboarding") && method === "POST") {
      const body = route.request().postDataJSON() as { step?: number; complete?: boolean };
      w.posts.push(body);
      if (typeof body.step === "number") {
        if (w.failStepPosts > 0) { w.failStepPosts -= 1; return json({ error: { code: "server_error", message: "x" } }, 500); }
        w.step = Math.max(w.step, body.step);
      }
      if (body.complete) w.completed = true;
      return json(account({ onboarding_completed: w.completed, onboarding_step: w.step }));
    }
    if (url.includes("/auth/preferences") && method === "PATCH") return json(account({ onboarding_completed: w.completed, onboarding_step: w.step }));
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: true, realtime_voice_enabled: false });
    if (url.includes("/memory")) return json({ memories: [], items: [] });
    return json({});
  });
}

const fresh = (): World => ({ step: 0, completed: false, failStepPosts: 0, posts: [], meHold: null });
const stepText = (page: Page, n: number) => page.getByText(new RegExp(`Step ${n} of 7`));

test("on a slow device with a delayed /auth/me, a saved step is not reverted when the shell finishes resolving", async ({ page, context }) => {
  // The exact CI failure: soft redirect /prepare -> /onboarding, click "Get started", POST {"step":1} answers 200, then the page falls back to "Step 1 of 7 . Welcome". It needs a slow
  // client (CI runs on 2 vCPUs), simulated with CDP CPU throttling (a load condition, not a sleep) and a slow identity response.
  const w = fresh();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 20 });
  await mock(page, w, { meLatencyMs: 2500 });
  await page.goto("/prepare");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: /set up Mo around you/i })).toBeVisible();
  await page.getByRole("button", { name: "Get started" }).click();
  await expect(stepText(page, 2)).toBeVisible();                       // the save succeeded and the UI advanced
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();
  expect(w.posts).toEqual([{ step: 1 }]);                              // exactly one write
  await expect(stepText(page, 2)).toBeVisible();                       // and Step 2 is still what the candidate sees
});

test("a successful save followed by a late route update (delayed soft navigation, hard-navigation fallback) keeps the step", async ({ page }) => {
  const w = fresh();
  await mock(page, w);
  let settled!: () => void;
  const rscDone = new Promise<void>((r) => { settled = r; });
  let delayed = 0;
  await page.route(/onboarding\?_rsc=/, async (route) => {
    delayed += 1;
    if (delayed <= 2) await new Promise((r) => setTimeout(r, 700 * delayed));   // the guard's soft retry and its hard-navigation fallback both fire before the soft navigation lands
    await route.continue();
    if (delayed >= 2) settled();
  });
  await page.goto("/prepare");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: /set up Mo around you/i })).toBeVisible();
  await page.getByRole("button", { name: "Get started" }).click();
  await expect(stepText(page, 2)).toBeVisible();
  await rscDone;
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();
  await expect(stepText(page, 2)).toBeVisible();
});

test("a failed step save never advances, shows a recoverable error and does not duplicate writes; the retry succeeds", async ({ page }) => {
  const w = fresh();
  w.failStepPosts = 1;
  await mock(page, w);
  await page.goto("/onboarding");
  await page.getByRole("button", { name: "Get started" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /couldn’t save this step/i })).toBeVisible();
  await expect(stepText(page, 1)).toBeVisible();
  await expect(page.getByRole("button", { name: "Get started" })).toBeVisible();
  expect(w.step).toBe(0);
  expect(w.posts).toEqual([{ step: 1 }]);                              // exactly one attempt so far
  await page.getByRole("button", { name: "Get started" }).click();
  await expect(stepText(page, 2)).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /couldn’t save this step/i })).toHaveCount(0);
  expect(w.posts).toEqual([{ step: 1 }, { step: 1 }]);
});

test("an intentional reload resumes from the persisted server step and the full flow still completes to the Welcome handoff", async ({ page }) => {
  const w = fresh();
  await mock(page, w);
  await page.goto("/prepare");
  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByRole("button", { name: "Get started" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(stepText(page, 4)).toBeVisible();
  expect(w.step).toBe(3);
  await page.reload();
  await expect(stepText(page, 4)).toBeVisible();                       // resumed at the saved step, not at Welcome
  for (let i = 0; i < 3; i++) await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("button", { name: "Enter Ask4Mo" })).toBeVisible();
  await page.getByRole("button", { name: "Enter Ask4Mo" }).click();
  await expect(page.getByRole("heading", { name: /Mo is ready/i })).toBeVisible();   // the intentional Welcome handoff, not an immediate /app redirect
  await Promise.all([page.waitForURL(/\/app$/), page.getByRole("button", { name: /Go to your workspace/i }).click()]);
});
