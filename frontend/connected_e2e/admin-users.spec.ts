import { readFileSync } from "node:fs";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

type SyntheticAccount = { id: number; email: string };
const accounts = JSON.parse(readFileSync(process.env.ADMIN_ACCOUNTS_FILE!, "utf8")) as Record<string, SyntheticAccount>;
const api = process.env.ADMIN_API_URL!;
const password = "Synthetic-Admin-Test-Password-42";

async function newContext(browser: Browser): Promise<BrowserContext> {
  const context = await browser.newContext();
  // Permit loopback application traffic only. This is not an API mock.
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname !== "localhost" && url.hostname !== "127.0.0.1") return route.abort("blockedbyclient");
    return route.continue();
  });
  return context;
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect.poll(async () => (await request(page, "/auth/me")).status).toBe(200);
}
async function request(page: Page, path: string, body?: Record<string, unknown>) {
  return page.evaluate(async ({ base, path, body }) => {
    const response = await fetch(base + path, { method: body ? "POST" : "GET", credentials: "include",
      headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
    return { status: response.status, json: await response.json() };
  }, { base: api, path, body });
}

test("connected Admin user lifecycle, authorization, revision and audit", async ({ browser }) => {
  const adminContext = await newContext(browser), viewerContext = await newContext(browser), candidateContext = await newContext(browser);
  const securityContext = await newContext(browser), anonymousContext = await newContext(browser);
  try {
    const admin = await adminContext.newPage(), viewer = await viewerContext.newPage(), candidate = await candidateContext.newPage();
    const security = await securityContext.newPage(), anonymous = await anonymousContext.newPage();
    await anonymous.goto("/sign-in");
    expect((await request(anonymous, "/admin/users")).status).toBe(401);
    await login(candidate, accounts.candidate.email);
    await login(security, accounts.security.email);
    await login(viewer, accounts.viewer.email);
    await login(admin, accounts.admin.email);
    const adminId = accounts.admin.id, candidateId = accounts.candidate.id;
    expect((await request(candidate, "/auth/me")).status).toBe(200);
    expect((await request(admin, "/auth/me")).json.user_id).toBe(adminId);

    await admin.goto("/admin");
    await admin.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Users", exact: true }).click();
    await admin.getByLabel("Email or account id").fill(accounts.candidate.email);
    await admin.getByRole("button", { name: "Search", exact: true }).click();
    const candidateLink = admin.getByRole("link", { name: accounts.candidate.email, exact: true });
    await expect(candidateLink).toBeVisible();
    await expect(admin.getByRole("link", { name: accounts.viewer.email, exact: true })).toHaveCount(0);
    await candidateLink.click();
    await expect(admin.getByRole("heading", { name: "Sign-in and verification" })).toBeVisible();
    const before = await request(admin, `/admin/users/${candidateId}`);
    expect(before.status).toBe(200);
    const revision = before.json.revision as string;
    expect(revision).toMatch(/^[0-9a-f]{16}$/);
    await expect(admin.getByText("Account revision", { exact: true }).locator("xpath=following-sibling::dd")).toHaveText(revision);
    await expect(admin.locator("body")).not.toContainText("SYNTHETIC_PRIVATE_SENTINEL");
    const serialized = JSON.stringify(before.json);
    for (const forbidden of ["password_hash", "token_hash", "SYNTHETIC_PRIVATE_SENTINEL"]) expect(serialized).not.toContain(forbidden);

    await viewer.goto(`/admin/users/${candidateId}`);
    await expect(viewer.getByRole("heading", { name: "Sign-in and verification" })).toBeVisible();
    await expect(viewer.getByRole("button", { name: "Deactivate account" })).toHaveCount(0);
    const denied = await request(viewer, `/admin/users/${candidateId}/actions/deactivate`, { expected_revision: revision, reason: "synthetic refusal" });
    expect(denied.status).toBe(403);
    const selfPage = await adminContext.newPage();
    await selfPage.goto(`/admin/users/${adminId}`);
    await expect(selfPage.getByRole("button", { name: "Deactivate account" })).toBeDisabled();
    await selfPage.close();
    const self = await request(admin, `/admin/users/${adminId}`);
    const selfDenied = await request(admin, `/admin/users/${adminId}/actions/deactivate`, { expected_revision: self.json.revision, reason: "synthetic self protection" });
    expect(selfDenied.status).toBe(409);
    const higherDenied = await request(security, `/admin/users/${adminId}/actions/force-signout`, { expected_revision: self.json.revision, reason: "synthetic hierarchy protection" });
    expect(higherDenied.status).toBe(403);
    expect((await request(admin, `/admin/users/${candidateId}`)).json.account.status).toBe("active");

    await admin.getByRole("button", { name: "Deactivate account" }).click();
    const dialog = admin.getByRole("alertdialog");
    await dialog.getByLabel(/Reason/).fill("synthetic lifecycle verification");
    const action = admin.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/admin/users/${candidateId}/actions/deactivate` && r.request().method() === "POST");
    await dialog.getByRole("button", { name: "Deactivate", exact: true }).click();
    const actionResponse = await action;
    expect(actionResponse.status()).toBe(200);
    expect(actionResponse.request().postDataJSON().expected_revision).toBe(revision);
    const result = await actionResponse.json();
    expect(result.changed).toBe(true); expect(result.sessions_revoked).toBeGreaterThanOrEqual(1); expect(result.revision).not.toBe(revision);
    await expect(admin.getByRole("status").filter({ hasText: /Account deactivated/ })).toBeVisible();
    await expect(admin.getByText("Account revision", { exact: true }).locator("xpath=following-sibling::dd")).toHaveText(result.revision);
    expect((await request(candidate, "/auth/me")).status).toBe(401);
    expect((await request(candidate, "/history/interviews")).status).toBe(401);
    expect((await request(admin, "/auth/me")).status).toBe(200);
    const after = await request(admin, `/admin/users/${candidateId}`);
    expect(after.json.account.status).toBe("deactivated");
    const events = after.json.audit.filter((item: { event_type: string }) => item.event_type === "admin.account_status_change");
    expect(events).toHaveLength(1); expect(events[0].actor_user_id).toBe(adminId); expect(events[0].result).toBe("success");
    expect(events[0].context.after).toBe("deactivated");
    expect(events[0].context.reason).toBe("synthetic lifecycle verification");
    expect(events[0].context.sessions_revoked).toBeGreaterThanOrEqual(1);
    expect(JSON.stringify(events[0])).not.toContain(accounts.candidate.email);
    const stale = await request(admin, `/admin/users/${candidateId}/actions/reactivate`, { expected_revision: revision, reason: "synthetic stale check" });
    expect(stale.status).toBe(409);
    const afterStale = await request(admin, `/admin/users/${candidateId}`);
    expect(afterStale.json.account.status).toBe("deactivated");
    expect(afterStale.json.audit.filter((item: { event_type: string }) => item.event_type === "admin.account_status_change")).toHaveLength(1);
  } finally {
    await adminContext.close(); await viewerContext.close(); await candidateContext.close(); await securityContext.close(); await anonymousContext.close();
  }
});
