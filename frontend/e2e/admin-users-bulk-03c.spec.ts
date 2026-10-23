import { expect, test, type Page } from "@playwright/test";

// 03C bulk Admin user actions, mocked at the network layer. Server-side preview binding, protection rules, partial failure, audit atomicity, idempotency, rate limit
// and the persona matrix are proven by tests/test_admin_users_bulk_03c.py; these browser tests prove the governed UI flow and the malformed-200 error state.

const OWNER = ["platform.overview.read", "platform.users.read", "platform.users.manage", "platform.users.sessions.revoke"];
const VIEWER = ["platform.overview.read", "platform.users.read"];
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const REV = "0123456789abcdef";

const row = (id: number, email: string) => ({ user_id: id, email, display_name: null, status: "active", platform_role: "user", tier: "basic", onboarding_completed: true,
  interface_locale: "en", email_verified: false, created_at: null, updated_at: null, workspace_count: 0, active_session_count: 1, last_activity: "7d" });
const PREVIEW = { action: "force-signout", requested: 2, unique: 2, eligible: 1, excluded: 1,
  excluded_by_reason: { self: 0, higher_authority: 0, last_active_platform_admin: 0, not_found: 0, no_live_sessions: 1 }, max_batch: 100, preview_revision: REV };
const RESULT = { action: "force-signout", batch_id: "b".repeat(16), status: "partial", requested: 2, unique: 2, applied: 1, skipped: 0, skipped_by_reason: {},
  failed: 1, failed_by_reason: { apply_error: 1 }, replayed: false };

type Seen = { previews: string[]; executes: { path: string; body: Record<string, unknown>; key: string | undefined }[] };

async function mock(page: Page, perms: string[], seen: Seen, over: { preview?: unknown; execute?: unknown } = {}) {
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
    if (/\/admin\/users\/bulk\/[a-z-]+\/preview$/.test(path) && method === "GET") {
      seen.previews.push(url.search);
      return json(over.preview ?? PREVIEW);
    }
    if (/\/admin\/users\/bulk\/[a-z-]+\/execute$/.test(path) && method === "POST") {
      const body = JSON.parse(route.request().postData() ?? "{}");
      seen.executes.push({ path, body, key: route.request().headers()["idempotency-key"] });
      return json(over.execute ?? RESULT);
    }
    if (path.endsWith("/admin/users")) return json({ items: [row(2, "jane@example.com"), row(3, "omar@example.com")], total: 2, page: 1, page_size: 25 });
    return json({});
  });
}

test("select, preview counts, confirm with a reason, see applied, skipped and failed", async ({ page }) => {
  const seen: Seen = { previews: [], executes: [] };
  await mock(page, OWNER, seen);
  await page.goto("/admin/users");
  await expect(page.getByRole("link", { name: "jane@example.com" })).toBeVisible();
  await page.getByLabel("Select all accounts on this page").check();
  await page.getByLabel("Action").selectOption("force-signout");
  await page.getByRole("button", { name: "Preview effect" }).click();
  await expect(page.getByText("Preview: 1 of 2 accounts would be changed, 1 excluded.")).toBeVisible();
  expect(seen.previews).toEqual(["?ids=2%2C3"]);
  expect(seen.executes).toHaveLength(0);
  await page.getByRole("button", { name: "Apply to 1 accounts" }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Apply" }).click();
  await expect(dialog.getByRole("alert")).toContainText("A reason is required.");
  await dialog.getByLabel(/Reason/).fill("shared device report");
  await dialog.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText("Partly applied: some accounts were not changed.")).toBeVisible();
  await expect(page.getByText("Applied 1, skipped 0, failed 1.")).toBeVisible();
  expect(seen.executes).toHaveLength(1);
  expect(seen.executes[0].body).toEqual({ account_ids: [2, 3], preview_revision: REV, reason: "shared device report" });
  expect(seen.executes[0].key).toMatch(/^bulk-[A-Za-z0-9_-]{8,}/);
});

test("a malformed 200 preview is the explicit error state, not a silent success", async ({ page }) => {
  const seen: Seen = { previews: [], executes: [] };
  await mock(page, OWNER, seen, { preview: {} });
  await page.goto("/admin/users");
  await page.getByLabel("Select account 2").check();
  await page.getByLabel("Action").selectOption("expire-verification");
  await page.getByRole("button", { name: "Preview effect" }).click();
  await expect(page.getByText(/unexpected response/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Apply to/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "jane@example.com" })).toBeVisible();     // the Users page itself stays usable
});

test("a malformed 200 execute response is an error in the dialog and shows no result", async ({ page }) => {
  const seen: Seen = { previews: [], executes: [] };
  await mock(page, OWNER, seen, { execute: { status: "complete" } });
  await page.goto("/admin/users");
  await page.getByLabel("Select account 2").check();
  await page.getByLabel("Action").selectOption("force-signout");
  await page.getByRole("button", { name: "Preview effect" }).click();
  await page.getByRole("button", { name: "Apply to 1 accounts" }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByLabel(/Reason/).fill("operator review");
  await dialog.getByRole("button", { name: "Apply" }).click();
  await expect(dialog.getByRole("alert")).toContainText("unexpected response");
  await expect(page.getByText(/Completed|Partly applied|Nothing was changed/)).toHaveCount(0);
});

test("a read-only role sees no selection controls", async ({ page }) => {
  const seen: Seen = { previews: [], executes: [] };
  await mock(page, VIEWER, seen);
  await page.goto("/admin/users");
  await expect(page.getByRole("link", { name: "jane@example.com" })).toBeVisible();
  await expect(page.getByLabel(/Select account/)).toHaveCount(0);
  await expect(page.getByText(/Bulk actions/)).toHaveCount(0);
});
