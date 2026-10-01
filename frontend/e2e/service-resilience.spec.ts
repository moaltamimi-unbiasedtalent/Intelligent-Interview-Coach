import { expect, test, type Page } from "@playwright/test";

// P10B-W9.1 - Service resilience & truthful error handling (E2E).
// Proves the transport foundation on a surface that already has a wired Retry (Opportunities):
//  1. when Ask4Mo's API is unreachable, the candidate sees TRUTHFUL Ask4Mo-service wording;
//  2. it never tells them to "check your connection" while the browser is online;
//  3. there is no infinite spinner and no crash (the error state renders);
//  4. Retry recovers once the service is restored.
// It also covers the browser-offline case (navigator offline -> offline wording).
// This uses the existing Opportunities API seam + its wired Retry; page-level Progress/History
// recovery and duplicate-error removal are explicitly W9.2, not this wave.

function account() {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en",
    conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0,
  };
}

// `down` starts true: the opportunities list request fails (aborted) as if the backend is
// unreachable. Auth/capabilities always succeed so the app shell loads.
async function mock(page: Page, ctrl: { down: boolean }) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    if (url.includes("/opportunities")) {
      if (ctrl.down) return route.abort("failed"); // fetch() rejects -> classified truthfully
      return json({ opportunities: [] });
    }
    if (url.includes("/documents")) return json({ documents: [] });
    return json({});
  });
}

test("unreachable API shows truthful Ask4Mo wording, not 'check your connection', then recovers", async ({ page }) => {
  const ctrl = { down: true };
  await mock(page, ctrl);

  await page.goto("/opportunities");

  // The error state renders (no infinite spinner, no crash). Scope to the ErrorState alert
  // (Next.js also renders an empty aria-live route-announcer with role="alert").
  const alert = page.getByRole("alert").filter({ hasText: /something went wrong/i });
  await expect(alert).toBeVisible();
  // Truthful: names Ask4Mo, and NEVER blames the user's internet while the browser is online.
  await expect(alert).toContainText(/ask4mo/i);
  await expect(alert).not.toContainText(/check your (internet|connection)/i);

  // Restore the service and retry in place -> recovery without a full reload.
  ctrl.down = false;
  await page.getByRole("button", { name: /try again/i }).click();

  await expect(page.getByText(/Start with an opportunity/i)).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /something went wrong/i })).toHaveCount(0);
});

test("browser offline shows offline wording", async ({ page }) => {
  const ctrl = { down: true };
  await mock(page, ctrl);

  // Load the shell while online so auth resolves, showing the (unreachable) error first.
  await page.goto("/opportunities");
  const alert = page.getByRole("alert").filter({ hasText: /something went wrong/i });
  await expect(alert).toBeVisible();

  // Now emulate the device going offline and retry: the classifier must say "offline".
  await page.context().setOffline(true);
  await page.getByRole("button", { name: /try again/i }).click();
  await expect(alert).toContainText(/offline/i);

  await page.context().setOffline(false);
});
