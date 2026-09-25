import { expect, test, type Page } from "@playwright/test";

// P6.5 Platform Admin console UX, mocked at the network layer. Server-side authorization is
// proven authoritatively by the Python suites (test_platform_admin_p6_5 / eval_platform_admin);
// these browser tests prove the admin-only UX gate + metadata-only rendering.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

function account(role: string) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: role,
    tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], response_detail: "brief",
    interface_locale: "en", conversation_language: "en",
  };
}

async function mockAdmin(page: Page, role: string, authed = true) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });

    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      if (!authed) return json({ error: { code: "unauthorized", message: "x" } }, 401);
      return json(account(role));
    }
    if (path.endsWith("/admin/home"))
      return json({ accounts: { users_total: 5, platform_admins: 1, premium_accounts: 2, deletion_requests_open: 0 },
                    workspaces: { workspaces_total: 3, active_shares: 4, pending_invitations: 1 },
                    knowledge: { overall_readiness: "ready" }, notes: "Operational metadata only." });
    if (path.endsWith("/admin/users"))
      return json({ users: [{ user_id: 1, email: "u@example.com", platform_role: "user", tier: "basic", status: "active", email_verified: true }] });
    if (path.endsWith("/admin/workspaces"))
      return json({ workspaces: [{ id: 1, name: "Team Alpha", status: "active", member_count: 2 }] });
    if (path.endsWith("/admin/providers"))
      return json({ google_oidc: { configured: false, live_validation: "UNVALIDATED" }, note: "Booleans/status only — no keys." });
    if (path.endsWith("/admin/audit"))
      return json({ events: [{ event_type: "admin.entitlement_change", result: "success", actor_user_id: 1, target_type: "user", created_at: null }] });
    return json({});
  });
}

test("platform admin sees the operational console (metadata only)", async ({ page }) => {
  await mockAdmin(page, "platform_admin");
  await page.goto("/admin");
  await expect(page.getByText("Users", { exact: true })).toBeVisible();
  await expect(page.getByText(/Provider status/i)).toBeVisible();
  await expect(page.getByText(/Recent audit events/i)).toBeVisible();
  // No candidate-private content on the admin surface.
  await expect(page.getByText(/curriculum vitae|raw answer|memory summary|password_hash/i)).toHaveCount(0);
  // No obvious secret value tokens in the provider section.
  await expect(page.getByText(/sk-[a-z0-9]/i)).toHaveCount(0);
});

test("normal user does not see the admin console", async ({ page }) => {
  await mockAdmin(page, "user");
  await page.goto("/admin");
  await expect(page.getByText(/requires a platform administrator/i)).toBeVisible();
  // Operational stats are NOT rendered for a normal user.
  await expect(page.getByText(/Recent audit events/i)).toHaveCount(0);
});

test("unauthenticated access to admin is redirected to sign-in", async ({ page }) => {
  await mockAdmin(page, "user", false);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/sign-in/);
});
