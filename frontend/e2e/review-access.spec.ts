import { expect, test, type Page } from "@playwright/test";

// P10B-W9.3 - internal Review/Diagnostics is admin-only. A BASIC candidate must not see the nav item
// and direct navigation must show a safe access-denied (not the diagnostic experience); a platform
// admin still gets the surfaces. Server-side authorization is proven by the Python suite; these
// browser tests prove the UX gate + direct-route behaviour.

function account(role: string) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: role,
    admin_permissions: role === "platform_admin" ? ["platform.overview.read", "platform.ai.read", "platform.knowledge.read"] : [],
    tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], response_detail: "brief",
    interface_locale: "en", conversation_language: "en", coaching_style: "balanced",
    career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0,
  };
}

async function mock(page: Page, role: string) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return json(account(role));
    if (path.endsWith("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    // Admin-only diagnostics (only reached by an admin; a candidate is blocked before the fetch).
    if (path.endsWith("/knowledge/diagnostics"))
      return json({ vectors: 1, documents: 1, retrieval: { passed: 1, total: 1 }, notes: "ok" });
    return json({});
  });
}

test("BASIC candidate: no Review nav item, and direct /review is access-denied", async ({ page }) => {
  await mock(page, "user");
  await page.goto("/app");

  // More menu shows Sources, never internal Review & Diagnostics.
  await page.getByRole("button", { name: /More/ }).first().click();
  const menu = page.getByRole("menu");
  await expect(menu.getByRole("menuitem", { name: /Sources/ })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: /Review & Diagnostics/ })).toHaveCount(0);
  await expect(menu.getByRole("menuitem", { name: /Admin/ })).toHaveCount(0);

  // Direct navigation is safely denied - NOT the reviewer index.
  await page.goto("/review");
  await expect(page.getByText(/access denied/i)).toBeVisible();
  await expect(page.getByText(/For reviewers & developers/i)).toHaveCount(0);

  // Child engineering routes are denied too (no diagnostic experience leaks).
  await page.goto("/review/rag");
  await expect(page.getByText(/access denied/i)).toBeVisible();
  await page.goto("/review/evaluation");
  await expect(page.getByText(/access denied/i)).toBeVisible();

  // BUT the candidate's OWN Agent Inspector stays accessible (owner-scoped self-transparency,
  // reached from the Coach's "View run details") - it must NOT be access-denied.
  await page.goto("/review/agent");
  await expect(page.getByText(/access denied/i)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /Agent Inspector/ })).toBeVisible();
});

test("platform admin: Review nav item present and the surfaces open", async ({ page }) => {
  await mock(page, "platform_admin");
  await page.goto("/app");

  await page.getByRole("button", { name: /More/ }).first().click();
  await expect(page.getByRole("menu").getByRole("menuitem", { name: /Review & Diagnostics/ })).toHaveAttribute("href", "/review");

  await page.goto("/review");
  await expect(page.getByText(/For reviewers & developers/i)).toBeVisible();
  await expect(page.getByText(/access denied/i)).toHaveCount(0);
  // The child engineering surfaces are reachable for an admin (rendering of their content is
  // covered by product-surfaces.spec and navigation.spec Flow 4).
  await expect(page.getByRole("link", { name: /Knowledge & RAG/ })).toHaveAttribute("href", "/review/rag");
});
