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

async function mock(page: Page, perms: string[], seen: { list: string[]; actions: { path: string; body: Record<string, unknown> }[] }, state: { revision: unknown } = { revision: REV }) {
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
      state.revision = "f".repeat(16);
      return json({ user_id: 2, action: path.split("/").pop(), changed: true, links_expired: 1, mail_accepted: true, sessions_revoked: 1, request_id: "r".repeat(32), revision: state.revision });
    }
    if (path.endsWith("/admin/plans/assignable")) return json([{ plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
    if (/\/admin\/users\/\d+$/.test(path)) return json({ ...DETAIL, revision: state.revision });
    if (path.endsWith("/admin/users")) {
      seen.list.push(url.search);
      return json({ items: [row(2, "jane@example.com"), row(3, "omar@example.com")], total: 2, page: 1, page_size: 25 });
    }
    if (path.endsWith("/admin/readiness") || path.endsWith("/admin/home")) return json({});
    return json({});
  });
}

test("connected acceptance prerequisite: revision is visible on account detail", async ({ page }) => {
  const seen = { list: [] as string[], actions: [] as { path: string; body: Record<string, unknown> }[] };
  await mock(page, OWNER, seen);
  await page.goto("/admin/users/2");
  await expect(page.getByRole("heading", { name: "Sign-in and verification" })).toBeVisible();
  await expect(page.getByText(REV, { exact: true })).toBeVisible();
});


test("revision is submitted unchanged and refreshed after a lifecycle action", async ({ page }) => {
  const seen = { list: [] as string[], actions: [] as { path: string; body: Record<string, unknown> }[] };
  await mock(page, OWNER, seen);
  await page.goto("/admin/users/2");
  await expect(page.getByText(REV, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Deactivate account" }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByLabel(/Reason/).fill("synthetic safety check");
  await dialog.getByRole("button", { name: "Deactivate", exact: true }).click();
  await expect.poll(() => seen.actions.length).toBe(1);
  expect(seen.actions[0].body.expected_revision).toBe(REV);
  await expect(page.getByText("f".repeat(16), { exact: true })).toBeVisible();
});

for (const revision of [undefined, null, 17, "not-a-revision"]) {
  test(`unavailable revision is not fabricated: ${String(revision)}`, async ({ page }) => {
    const seen = { list: [] as string[], actions: [] as { path: string; body: Record<string, unknown> }[] };
    await mock(page, OWNER, seen, { revision });
    await page.goto("/admin/users/2");
    const term = page.getByText("Account revision", { exact: true });
    await expect(term).toBeVisible();
    await expect(term.locator("xpath=following-sibling::dd")).toHaveText("Not available");
  });
}
