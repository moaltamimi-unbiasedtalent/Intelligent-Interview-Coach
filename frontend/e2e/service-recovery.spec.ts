import { expect, test, type Page } from "@playwright/test";

// P10B-W9.2 - Progress/History outage recovery (E2E). Proves the Pilot failure is closed:
// during a backend outage the candidate sees ONE truthful, recoverable error (never the duplicate
// "Couldn't load practice progress." + big "Something went wrong / check your connection"), and a
// single Retry recovers in place - same route, no full reload, no re-login.
//
// The outage is simulated with deterministic request interception (no flaky sleeps); this proves
// FRONTEND recovery behaviour, not real process supervision. Auth stays valid throughout, proving a
// temporary outage never forces sign-in.

function account() {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en",
    conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0,
  };
}
const PRACTICE = {
  interviews_completed: 2, answers_evaluated: 5, average_practice_score: 70,
  most_common_improvement_area: null, average_answer_seconds: 60, recent_interviews: [],
};

async function mock(page: Page, ctrl: { down: boolean }) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "rid-1" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account()); // auth ALWAYS valid (no forced logout)
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    // Read data regions honour the outage switch.
    if (url.includes("/progress") || url.includes("/memory") || url.includes("/history")) {
      if (ctrl.down) return route.abort("failed");
      if (url.includes("/progress")) return json(PRACTICE);
      if (url.includes("/memory")) return json({ memories: [] });
      if (url.includes("/history")) return json({ interviews: [] });
    }
    return json({});
  });
}

test("Progress: outage shows ONE truthful recoverable error, then Retry recovers in place", async ({ page }) => {
  const ctrl = { down: true };
  await mock(page, ctrl);

  await page.goto("/progress");

  // Exactly ONE page-level catastrophic error - never the Pilot's duplicate pattern.
  const alert = page.getByRole("alert").filter({ hasText: /something went wrong/i });
  await expect(alert).toHaveCount(1);
  await expect(alert).not.toContainText(/check your (internet|connection)/i);
  await expect(page.getByText(/Couldn.t load practice progress\./i)).toHaveCount(0);
  const retry = page.getByRole("button", { name: /try again/i });
  await expect(retry).toHaveCount(1);

  // Restore the backend and retry in place.
  ctrl.down = false;
  await retry.click();

  // Recovered content appears; the error is gone; still on /progress; auth intact (no sign-in).
  await expect(page.getByRole("heading", { name: "Practice progress" })).toBeVisible();
  await expect(page.getByText(/Nothing saved yet\./i)).toBeVisible(); // memory empty state, not an error
  await expect(page.getByRole("alert").filter({ hasText: /something went wrong/i })).toHaveCount(0);
  expect(new URL(page.url()).pathname).toBe("/progress");
});

test("Progress: one region can fail while the other stays usable (memory ok, practice fails)", async ({ page }) => {
  // Practice fails, memory succeeds (empty) -> memory region usable, a compact section error for
  // practice with Retry, and NO page-level catastrophic card.
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    if (url.includes("/progress")) return route.abort("failed");
    if (url.includes("/memory")) return json({ memories: [] });
    return json({});
  });

  await page.goto("/progress");
  await expect(page.getByText(/Nothing saved yet\./i)).toBeVisible(); // memory region usable
  await expect(page.getByRole("button", { name: /try again/i })).toHaveCount(1); // practice section retry
  await expect(page.getByText("Something went wrong")).toHaveCount(0); // not the giant page card
});

test("History: outage shows a truthful recoverable error, then Retry recovers in place", async ({ page }) => {
  const ctrl = { down: true };
  await mock(page, ctrl);

  await page.goto("/history");
  const alert = page.getByRole("alert").filter({ hasText: /something went wrong/i });
  await expect(alert).toBeVisible();
  await expect(alert).not.toContainText(/check your (internet|connection)/i);

  ctrl.down = false;
  await page.getByRole("button", { name: /try again/i }).click();

  await expect(page.getByText(/No completed interviews yet/i)).toBeVisible(); // empty state, not an error
  await expect(page.getByRole("alert").filter({ hasText: /something went wrong/i })).toHaveCount(0);
  expect(new URL(page.url()).pathname).toBe("/history");
});

test("Progress recovery error/retry renders at mobile width (390px)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  const ctrl = { down: true };
  await mock(page, ctrl);
  await page.goto("/progress");
  const retry = page.getByRole("button", { name: /try again/i });
  await expect(retry).toBeVisible();
  // The Retry control is reachable and not clipped off-screen at phone width.
  const box = await retry.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
});
