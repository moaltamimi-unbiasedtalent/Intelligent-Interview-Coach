import { expect, test, type Page } from "@playwright/test";

// P10B-W10.1 Admin shell + Command Center UX, mocked at the network layer. Server-side authorization,
// atomic audit and the safe provider schema are proven by the Python suites
// (tests/test_admin_foundation_w10_1.py, scripts/eval_admin_foundation.py); these browser tests prove the
// capability-aware navigation, the truthful Command Center and the candidate denial.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

const ADMIN_PERMS = [
  "platform.overview.read", "platform.users.read", "platform.workspaces.read", "platform.audit.read",
  "platform.integrations.read", "platform.ai.read", "platform.knowledge.read",
];

function account(role: string, perms: string[]) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: role,
    tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief",
    interface_locale: "en", conversation_language: "en",
  };
}

const HOME = {
  build: { version: "0.1.0", git_sha: "abc1234", build_time: "2026-10-02T10:00:00Z", environment: "staging", source: "x" },
  migrations: { repository_head: "0014_opportunities", database_revision: "0014_opportunities", state: "match", warning: null },
  health: { database: "reachable", providers_probed: false, note: "" },
  rate_limit: { mode: "in_memory_process_local", distributed: false, shared_store_requested: false, note: "" },
  pause: { paused: {}, durable: false, note: "Process-local and non-durable." },
  privacy_requests: { status: "not_operational", note: "Privacy-request administration is not available yet." },
  accounts: { users_total: 5, platform_admins: 1, premium_accounts: 2 },
  workspaces: { workspaces_total: 3 },
  diagnostics_links: [{ label: "Knowledge readiness", path: "/review/rag" }],
  boundary: "Operational metadata only. No candidate-private content is accessible here.",
};

async function mockAdmin(page: Page, role: string, perms: string[], authed = true) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });

    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      if (!authed) return json({ error: { code: "unauthorized", message: "x" } }, 401);
      return json(account(role, perms));
    }
    if (path.endsWith("/admin/home")) return json(HOME);
    if (path.endsWith("/admin/users"))
      return json({ users: [{ user_id: 1, email: "u@example.com", platform_role: "user", tier: "basic", status: "active", email_verified: true }] });
    if (path.endsWith("/admin/workspaces"))
      return json({ workspaces: [{ id: 1, name: "Team Alpha", status: "active", member_count: 2 }] });
    if (path.endsWith("/admin/providers"))
      return json({
        providers: [{ provider_id: "openrouter", label: "Language model provider (OpenRouter)", configured: true, enabled: true,
          externally_managed: true, writable: false, status: "configured_health_not_tested", health: "Health not tested",
          live_validation: "UNVALIDATED", mode: null }],
        speech: {}, ocr: { engine: "tesseract", available: true, pdf_ocr_available: true, poppler_available: true, live_quality: "UNVALIDATED" },
        pause: {}, pause_durable: false, rate_limit_mode: "in_memory_process_local", rate_limit_distributed: false,
        note: "Configured does not mean healthy; no provider is contacted here.",
      });
    if (path.endsWith("/admin/audit"))
      return json({ events: [{ event_type: "admin.account_status_change", result: "success", actor_user_id: 1, target_type: "user",
        target_id: "2", request_id: "req-abc", context: { before: "active", after: "deactivated" }, created_at: null }] });
    return json({});
  });
}

test("platform admin journey: Command Center, build metadata, audit, provider status, diagnostic link", async ({ page }) => {
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByText("abc1234")).toBeVisible();
  await expect(page.getByText("Up to date")).toBeVisible();
  await expect(page.getByText("Health not tested").first()).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Admin" });
  for (const label of ["Overview", "Users", "Workspaces", "Review / Diagnostics", "Audit", "Provider status"]) {
    await expect(nav.getByRole("link", { name: new RegExp(label) })).toBeVisible();
  }
  for (const future of ["Billing", "Support", "Subscriptions", "Jobs", "Incidents", "Feature Flags"]) {
    await expect(nav.getByRole("link", { name: new RegExp(future) })).toHaveCount(0);
  }
  await expect(page.getByRole("link", { name: "Knowledge readiness" })).toHaveAttribute("href", "/review/rag");

  await nav.getByRole("link", { name: /Audit/ }).click();
  await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
  await expect(page.getByText("req-abc")).toBeVisible();
  await expect(page.getByText("active to deactivated")).toBeVisible();

  await nav.getByRole("link", { name: /Provider status/ }).click();
  await expect(page.getByText("Language model provider (OpenRouter)")).toBeVisible();
  await expect(page.getByText("Health not tested")).toBeVisible();
  await expect(page.getByText(/sk-[a-z0-9]/i)).toHaveCount(0);
  // No candidate-private content anywhere on the admin surface.
  await expect(page.getByText(/curriculum vitae|raw answer|memory summary|password_hash/i)).toHaveCount(0);
});

test("a limited admin role sees only the destinations the server granted", async ({ page }) => {
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.users.read"]);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(nav.getByRole("link", { name: /Users/ })).toBeVisible();
  await expect(nav.getByRole("link", { name: /Audit/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /Provider status/ })).toHaveCount(0);
});

test("candidate is denied the admin area", async ({ page }) => {
  await mockAdmin(page, "user", []);
  await page.goto("/admin");
  await expect(page.getByText(/not available|access/i).first()).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Admin" })).toHaveCount(0);
  await expect(page.getByText("abc1234")).toHaveCount(0);
});

test("unauthenticated access to admin is redirected to sign-in", async ({ page }) => {
  await mockAdmin(page, "user", [], false);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/sign-in/);
});
