import { expect, test, type Page } from "@playwright/test";

// 03C Admin Users, mocked at the network layer. Server authorization, revision handling, self/hierarchy protection and audit are proven by
// tests/test_admin_users_03c.py; these browser tests prove the governed UI flow, the filters sent to the server and the role boundary. No provider is contacted.

const OWNER = ["platform.overview.read", "platform.users.read", "platform.users.manage", "platform.users.role.assign", "platform.users.sessions.revoke",
  "platform.subscriptions.manage", "platform.privacy.execute", "platform.privacy.read", "platform.support.read"];
const VIEWER = ["platform.overview.read", "platform.users.read"];
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const REV = "0123456789abcdef";

const row = (id: number, email: string) => ({ user_id: id, email, display_name: null, status: "active", platform_role: "user", tier: "basic", onboarding_completed: true,
  interface_locale: "en", email_verified: false, created_at: null, updated_at: null, workspace_count: 1, active_session_count: 1, last_activity: "7d" });
const DETAIL = {
  revision: REV, account: row(2, "jane@example.com"), access: { platform_role: "user", capabilities: [], assignable_roles: ["user"], is_self: false },
  sessions: { active_count: 1, recent: [] }, workspaces: [], audit: [],
  plan: { current: { plan_code: "basic", version: 1, display_name: "Basic", status: "active", source: "system_default", started_at: "2026-10-01", ended_at: null }, history: [] },
  auth: { methods: [{ method: "password", email_verified: false, linked_at: null }], local_sign_in: true, email_verified: false, pending_verification_links: 1 },
  activity: { last_active: "7d" },
  cases: { support_open: 1, support_total: 1, privacy_open: 0, privacy_total: 0, pending_role_change: false, open_deletion_request_id: null, open_deletion_status: null },
  membership: { active: 0, total: 0, owner_of_active: 0 },
};

async function mock(page: Page, perms: string[], seen: { list: string[]; actions: { path: string; body: Record<string, unknown> }[] }) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: "platform_admin", tier: "basic", status: "active", email_verified: true, providers: ["password"],
        auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    }
    if (/\/admin\/users\/\d+\/actions\/[a-z-]+$/.test(path) && method === "POST") {
      const body = JSON.parse(route.request().postData() ?? "{}");
      seen.actions.push({ path: path.split("/actions/")[1], body });
      if (!body.reason || body.expected_revision !== REV) return json({ error: { code: "validation_error", message: "reason and revision required" } }, 422);
      return json({ user_id: 2, action: path.split("/").pop(), changed: true, links_expired: 1, mail_accepted: true, sessions_revoked: 1, request_id: "r".repeat(32), revision: "f".repeat(16) });
    }
    if (path.endsWith("/admin/plans/assignable")) return json([{ plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
    if (/\/admin\/users\/\d+$/.test(path)) return json(DETAIL);
    if (path.endsWith("/admin/users")) {
      seen.list.push(url.search);
      return json({ items: [row(2, "jane@example.com"), row(3, "omar@example.com")], total: 2, page: 1, page_size: 25 });
    }
    if (path.endsWith("/admin/readiness") || path.endsWith("/admin/home")) return json({});
    return json({});
  });
}

test("search, sort and filters are server-side; detail is complete and content-free", async ({ page }) => {
  const seen = { list: [] as string[], actions: [] as { path: string; body: Record<string, unknown> }[] };
  await mock(page, OWNER, seen);
  await page.goto("/admin/users");
  await expect(page.getByRole("link", { name: "jane@example.com" })).toBeVisible();
  await page.getByLabel("Sort by").selectOption("last_active");
  await page.getByLabel("Order").selectOption("asc");
  await page.getByLabel("Last active").selectOption("never");
  await page.getByLabel("Open case").selectOption("support");
  await page.getByRole("button", { name: "Search" }).click();
  await expect.poll(() => seen.list.at(-1) ?? "").toContain("sort=last_active");
  expect(seen.list.at(-1)).toContain("direction=asc");
  expect(seen.list.at(-1)).toContain("last_active=never");
  expect(seen.list.at(-1)).toContain("open_case=support");

  await page.getByRole("link", { name: "jane@example.com" }).click();
  await expect(page.getByRole("heading", { name: "Sign-in and verification" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cases and membership" })).toBeVisible();
  await expect(page.getByText("Email and password")).toBeVisible();
  await expect(page.getByText(/curriculum vitae|interview answer|memory summary|conversation/i)).toHaveCount(0);
});

test("resend verification and record a deletion request: reason required, revision sent, nothing deleted", async ({ page }) => {
  const seen = { list: [] as string[], actions: [] as { path: string; body: Record<string, unknown> }[] };
  await mock(page, OWNER, seen);
  await page.goto("/admin/users/2");
  await page.getByRole("button", { name: "Resend verification email" }).click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Resend" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("A reason is required.");
  expect(seen.actions).toHaveLength(0);
  await dialog.getByLabel(/Reason/).fill("user lost the email");
  await dialog.getByRole("button", { name: "Resend" }).click();
  await expect(page.getByText(/Verification email submitted/)).toBeVisible();
  expect(seen.actions[0]).toMatchObject({ path: "resend-verification", body: { expected_revision: REV, reason: "user lost the email" } });

  await page.getByRole("button", { name: "Record deletion request" }).click();
  dialog = page.getByRole("alertdialog");
  await expect(dialog.getByText(/The account stays active and no data is removed/)).toBeVisible();
  await dialog.getByLabel(/Reason/).fill("asked by letter");
  await dialog.getByRole("button", { name: "Record request" }).click();
  await expect(page.getByText(/Deletion request recorded/)).toBeVisible();
  expect(seen.actions[1]).toMatchObject({ path: "request-deletion", body: { reason: "asked by letter" } });
});

test("a view-only role sees the complete detail but no write control", async ({ page }) => {
  const seen = { list: [] as string[], actions: [] as { path: string; body: Record<string, unknown> }[] };
  await mock(page, VIEWER, seen);
  await page.goto("/admin/users/2");
  await expect(page.getByRole("heading", { name: "Sign-in and verification" })).toBeVisible();
  for (const name of [/Resend verification/, /Expire verification/, /Record deletion request/, /Change plan/, /Force logout/, /Deactivate account/]) {
    await expect(page.getByRole("button", { name })).toHaveCount(0);
  }
  expect(seen.actions).toHaveLength(0);
});
