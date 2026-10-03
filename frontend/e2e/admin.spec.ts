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
  "platform.overview.read", "platform.users.read", "platform.users.manage", "platform.users.role.assign",
  "platform.users.sessions.revoke", "platform.workspaces.read", "platform.workspaces.manage", "platform.audit.read",
  "platform.support.read", "platform.support.reply", "platform.support.manage", "platform.support.note",
  "platform.plans.read", "platform.plans.manage", "platform.subscriptions.manage", "platform.integrations.manage",
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

const USER_ROW = { user_id: 2, email: "jane@example.com", display_name: null, status: "active", platform_role: "user", tier: "basic",
  onboarding_completed: true, interface_locale: "en", email_verified: false, created_at: null, updated_at: null,
  workspace_count: 1, active_session_count: 1 };
const USER_DETAIL = {
  plan: { current: { plan_code: "basic", version: 1, display_name: "Basic", status: "active", source: "system_default", started_at: "2026-10-01", ended_at: null }, history: [] },
  account: USER_ROW,
  access: { platform_role: "user", capabilities: [], assignable_roles: ["user", "support_operator"], is_self: false },
  sessions: { active_count: 1, recent: [{ created_at: "2026-10-01T10:00:00", last_used_at: null, expires_at: "2026-10-30T10:00:00" }] },
  workspaces: [{ workspace_id: 3, name: "Team Alpha", workspace_status: "active", role: "workspace_member", membership_status: "active", joined_at: null }],
  audit: [],
};
const itState = { tested: false };
const INT_ROW = (tested: boolean) => ({
  code: "openrouter", name: "OpenRouter (language models)", category: "ai_model", category_label: "AI / model", adapter: "OpenRouter chat API",
  description: "Chat model provider.", classification: "runtime_active", configuration_status: "configured",
  slots: [{ slot: "api_key", label: "API key", external_name: "OPENROUTER_API_KEY", configured: true, source: "environment", writable: false }],
  settings: [], runtime: { enabled: true, managed: "environment", toggle_supported: false, note: "Runtime state is owned by the deployment environment." },
  store: { name: "environment", writable: false },
  health: tested ? { status: "healthy", last_tested_at: "2026-10-03T10:00:00", category: "ok", latency_ms: 11 } : { status: "not_tested", last_tested_at: null, category: null, latency_ms: null },
  test: { supported: true, note: "Calls one key-information endpoint." }, validation_note: "Healthy only after a successful manual test." });
const INT_GOOGLE = { ...INT_ROW(false), code: "google_oidc", name: "Google sign-in (OIDC)", category: "authentication", category_label: "Authentication",
  classification: "code_present_not_validated", test: { supported: false, note: "No manual probe." },
  validation_note: "Backend support present; end-to-end sign-in is not validated." };
const PLAN_ROWS = [
  { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", enabled_entitlements: 5, total_entitlements: 5, subscribers: { users: 1, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: null },
  { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", enabled_entitlements: 4, total_entitlements: 5, subscribers: { users: 4, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: null },
];
const PLAN_DETAIL = { id: 3, plan_code: "premium", version: 2, display_name: "Premium (preview)", status: "draft", editable: true,
  entitlements: ["current_market_research", "standard_history", "standard_progress", "standard_model_profiles", "premium_preview"].map((k) => ({ code: k, label: `Label ${k}`, description: "d", type: "boolean", enabled: true, limit: null })),
  subscribers: { users: 0, workspaces: 0 }, created_at: null, activated_at: null, retired_at: null };
const MY_PLAN = { plan_code: "basic", plan_version: 1, entitlements: { current_market_research: { enabled: true, limit: null, unlimited: true }, premium_preview: { enabled: false, limit: null, unlimited: false } } };
const TICKET_ROW = { id: 5, public_id: "d".repeat(32), owner_user_id: 2, owner_email: "jane@example.com", category: "billing", priority: "normal",
  status: "new", subject: "Charged twice", assigned_user_id: null, assignee_email: null, message_count: 1, created_at: null, updated_at: null };
const TICKET_DETAIL = {
  ticket: { ...TICKET_ROW, initial_request_id: "req-1", source_route: "/pricing", source_environment: "test", resolved_at: null, closed_at: null, allowed_statuses: ["triaged", "in_progress", "closed"] },
  messages: [{ id: 1, author_kind: "candidate", author_user_id: 2, body: "I was charged twice.", request_id: "req-1", created_at: null }],
  internal_notes: [{ id: 2, author_user_id: 3, body: "Check the billing log", request_id: null, created_at: null }],
  account: USER_ROW, priorities: ["low", "normal", "high", "urgent"], statuses: [],
};
const WS_ROW = { id: 3, name: "Team Alpha", status: "active", owner_user_id: 1, owner_email: "owner@example.com", member_count: 2, created_at: null };
const WS_DETAIL = {
  workspace: WS_ROW,
  members: [{ user_id: 1, email: "owner@example.com", account_status: "active", role: "workspace_owner", membership_status: "active", joined_at: null },
            { user_id: 2, email: "jane@example.com", account_status: "active", role: "workspace_member", membership_status: "active", joined_at: null }],
  active_share_count: 0, active_owner_count: 1, workspace_roles: ["workspace_owner", "workspace_member"],
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
    const method = route.request().method();
    if (/\/admin\/integrations\/[^/]+\/test$/.test(path) && method === "POST") {
      itState.tested = true;
      return json({ integration: "openrouter", outcome: "success", category: "ok", latency_ms: 11 });
    }
    if (/\/admin\/integrations\/[^/]+$/.test(path)) return json({ ...INT_ROW(itState.tested), audit: [] });
    if (path.endsWith("/admin/integrations")) return json({ items: [INT_ROW(itState.tested), INT_GOOGLE] });
    if (/\/admin\/plans\/versions\/\d+\/(activate|retire)$/.test(path) && method === "POST") return json({ ok: true });
    if (/\/admin\/plans\/versions\/\d+\/entitlements$/.test(path) && method === "PATCH") return json({ id: 3, changed: ["premium_preview"] });
    if (/\/admin\/plans\/[^/]+\/versions$/.test(path) && method === "POST") return json({ id: 3, plan_code: "premium", version: 2 });
    if (path.endsWith("/admin/plans/assignable")) return json([{ plan_code: "basic", version: 1, display_name: "Basic" }, { plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
    if (/\/admin\/plans\/\d+$/.test(path)) return json(PLAN_DETAIL);
    if (path.endsWith("/admin/plans")) return json({ items: PLAN_ROWS });
    if (/\/admin\/users\/\d+\/plan$/.test(path) && method === "POST") return json({ subject_type: "user", subject_id: 2, plan_code: "premium", version: 1, changed: true });
    if (path.endsWith("/auth/plan")) return json(MY_PLAN);
    if (/\/admin\/support\/tickets\/[^/]+\/(assign|status|priority|reply|notes)$/.test(path) && method === "POST") return json({ ok: true });
    if (path.endsWith("/admin/support/assignees")) return json([{ user_id: 3, email: "op@example.com", platform_role: "support_operator" }]);
    if (/\/admin\/support\/tickets\/[^/]+$/.test(path)) return json(TICKET_DETAIL);
    if (path.endsWith("/admin/support/tickets")) {
      const q = new URL(route.request().url()).searchParams;
      const items = [TICKET_ROW].filter((t) => !q.get("status") || t.status === q.get("status"));
      return json({ items, total: items.length, page: 1, page_size: 25 });
    }
    if (/\/admin\/users\/\d+\/status$/.test(path) && method === "POST") return json({ user_id: 2, status: "deactivated", changed: true, sessions_revoked: 1 });
    if (/\/admin\/users\/\d+\/sessions\/revoke$/.test(path) && method === "POST") return json({ user_id: 2, sessions_revoked: 1 });
    if (/\/admin\/users\/\d+$/.test(path)) return json(USER_DETAIL);
    if (path.endsWith("/admin/users")) {
      const q = new URL(route.request().url()).searchParams.get("q") ?? "";
      const items = [USER_ROW].filter((u) => !q || u.email.includes(q));
      return json({ items, users: items, total: items.length, page: 1, page_size: 25 });
    }
    if (/\/admin\/workspaces\/\d+$/.test(path)) return json(WS_DETAIL);
    if (path.endsWith("/admin/workspaces"))
      return json({ items: [WS_ROW], workspaces: [WS_ROW], total: 1, page: 1, page_size: 25 });
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
  for (const future of ["Billing", "Subscriptions", "Jobs", "Incidents", "Feature Flags"]) {
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

test("W10.2: users search, safe detail, governed action with confirmation, workspace membership", async ({ page }) => {
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Users/ }).click();
  await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible();
  await page.getByLabel("Email or account id").fill("jane");
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("link", { name: "jane@example.com" }).click();
  await expect(page.getByRole("heading", { name: "Sessions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Access" })).toBeVisible();
  // No candidate-private content on a user's admin page.
  await expect(page.getByText(/curriculum vitae|interview answer|memory summary|conversation/i)).toHaveCount(0);
  await page.getByRole("button", { name: "Deactivate account" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await dialog.getByRole("button", { name: "Deactivate" }).click();
  await expect(page.getByText(/Account deactivated/)).toBeVisible();
  await page.getByRole("link", { name: "Team Alpha" }).click();
  await expect(page.getByRole("heading", { name: "Members" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove: jane@example.com" })).toBeVisible();
  await page.getByRole("button", { name: "Remove: jane@example.com" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();
});

test("W10.6: integrations inventory, environment-managed credential, manual test, read-only role", async ({ page }) => {
  itState.tested = false;
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Integrations/ }).click();
  await expect(page.getByRole("heading", { name: "Integrations", exact: true })).toBeVisible();
  await expect(page.getByText("Code present, not validated")).toBeVisible();
  await expect(page.getByText("Not tested").first()).toBeVisible();
  await page.getByRole("link", { name: "OpenRouter (language models)" }).click();
  await expect(page.getByText(/Managed outside Ask4Mo/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Replace|Set credential|Reveal|Rotate/ })).toHaveCount(0);
  await expect(page.locator('input[type="password"], input[type="url"]')).toHaveCount(0);
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByText("Connection test succeeded.")).toBeVisible();
  await expect(page.getByText("Last test succeeded")).toBeVisible();

  await page.unroute("**/api/v1/**");
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.integrations.read"]);
  await page.goto("/admin/integrations/openrouter");
  await expect(page.getByRole("heading", { name: "Connection test" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Test connection" })).toHaveCount(0);
});

test("W10.4: plan catalogue, draft version, user plan assignment, candidate plan view", async ({ page }) => {
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Plans/ }).click();
  await expect(page.getByRole("heading", { name: "Plans", exact: true })).toBeVisible();
  await expect(page.getByText("5 of 5 enabled")).toBeVisible();
  await expect(page.getByText(/no prices, payments or invoices/)).toBeVisible();
  await page.getByRole("button", { name: "Create next draft of premium" }).click();
  await expect(page.getByText(/Draft version 2 of premium created/)).toBeVisible();
  await page.goto("/admin/plans/3");
  await expect(page.getByRole("heading", { name: "Entitlements" })).toBeVisible();
  await page.getByRole("button", { name: "Activate this version" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();

  await page.goto("/admin/users/2");
  await expect(page.getByRole("heading", { name: "Plan", exact: true })).toBeVisible();
  await expect(page.getByText("Basic (version 1)")).toBeVisible();
  await page.getByLabel("Change plan").selectOption("premium");
  await page.getByRole("button", { name: "Change plan" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Change plan" }).click();
  await expect(page.getByText(/Plan changed to Premium \(preview\)/)).toBeVisible();
});

test("W10.4: the candidate account page shows the plan truthfully with nothing to buy", async ({ page }) => {
  await mockAdmin(page, "user", []);
  await page.goto("/account");
  await expect(page.getByTestId("plan-summary")).toBeVisible();
  await expect(page.getByText("Premium is a preview.", { exact: false })).toBeVisible();
  await expect(page.getByTestId("plan-summary").getByRole("button")).toHaveCount(0);
  await expect(page.getByTestId("plan-summary").getByRole("link")).toHaveCount(0);
});

test("W10.3: support queue, filter, ticket detail, assign, status, reply and internal note", async ({ page }) => {
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.support.read", "platform.support.reply", "platform.support.manage", "platform.support.note"]);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Support/ }).click();
  await expect(page.getByRole("heading", { name: "Support", exact: true })).toBeVisible();
  await page.getByLabel("Status").selectOption("new");
  await page.getByRole("button", { name: "Apply" }).click();
  await page.getByRole("link", { name: /Charged twice/ }).click();
  await expect(page.getByRole("heading", { name: "Ticket", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Messages (visible to the candidate)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Internal notes (never visible to the candidate)" })).toBeVisible();
  await expect(page.getByText("Check the billing log")).toBeVisible();

  await page.getByLabel("Assignee").focus();
  await page.getByLabel("Assignee").selectOption("3");
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Ticket assigned.")).toBeVisible();
  await page.getByLabel("Move to").selectOption("triaged");
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Change status" }).click();
  await expect(page.getByText("Status changed to triaged.")).toBeVisible();
  await page.getByLabel(/Reply \(the candidate/).fill("We are on it.");
  await page.getByRole("button", { name: "Send reply to candidate" }).click();
  await expect(page.getByText(/candidate sees it/)).toBeVisible();
  await page.getByLabel("Internal note (staff only)").fill("Escalated to billing");
  await page.getByRole("button", { name: "Save internal note" }).click();
  await expect(page.getByText(/never shown to the candidate/).first()).toBeVisible();
});

test("a limited admin role sees only the destinations the server granted", async ({ page }) => {
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.users.read"]);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(nav.getByRole("link", { name: /Users/ })).toBeVisible();
  await expect(nav.getByRole("link", { name: /Audit/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /Provider status/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /Support/ })).toHaveCount(0);   // no support.read: no Support entry
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
