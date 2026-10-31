import { readFileSync } from "node:fs";
import { expect, test, type Browser, type Page } from "@playwright/test";

const api = process.env.WORKSPACE_API_URL!;
const accounts = JSON.parse(readFileSync(process.env.WORKSPACE_ACCOUNTS_FILE!, "utf8")) as Record<string, { id: number; email: string }>;
const password = "Synthetic-Workspace-Test-Password-42";
async function context(browser: Browser) {
  const ctx = await browser.newContext();
  await ctx.route("**/*", route => {
    const host = new URL(route.request().url()).hostname;
    return host === "localhost" || host === "127.0.0.1" ? route.continue() : route.abort("blockedbyclient");
  });
  return ctx;
}
async function request(page: Page, path: string, method = "GET", body?: object) {
  return page.evaluate(async ({ base, path, method, body }) => {
    const r = await fetch(base + path, { method, credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, json: await r.json() };
  }, { base: api, path, method, body });
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in");
  await page.locator("#email").fill(email); await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect.poll(async () => (await request(page, "/auth/me")).status).toBe(200);
}

test("two Candidates invite, consent, view and revoke through real API", async ({ browser }) => {
  const owner = await context(browser), recipient = await context(browser);
  try {
    const a = await owner.newPage(), b = await recipient.newPage();
    await login(a, accounts.owner.email); await login(b, accounts.other.email);
    const story = await request(a, "/stories", "POST", { title: "Synthetic shared story", situation: "Synthetic shared content", status: "user_created" });
    const privateStory = await request(a, "/stories", "POST", { title: "Synthetic unshared story", status: "user_created" });
    expect(story.status).toBe(201); expect(privateStory.status).toBe(201);
    const id = story.json.id as number, privateId = privateStory.json.id as number;
    await a.goto("/workspaces"); await a.getByLabel(/Workspace name/i).fill("Synthetic team");
    const created = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces" && r.request().method() === "POST");
    await a.getByRole("button", { name: "Create workspace" }).click();
    const createResponse = await created; expect(createResponse.status()).toBe(200);
    const workspace = await createResponse.json(); const wid = workspace.id as number;
    await a.getByRole("link", { name: "Open workspace: Synthetic team" }).click();
    await a.getByLabel("Email address").fill(accounts.other.email);
    const invited = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/workspaces/${wid}/invite` && r.request().method() === "POST");
    await a.getByRole("button", { name: "Send invitation" }).click();
    const inviteResponse = await invited; expect(inviteResponse.status()).toBe(200);
    const invite = await inviteResponse.json();
    expect(invite.email_delivery).toBe("submitted"); expect(JSON.stringify(invite)).not.toMatch(/token|code|secret/i);
    expect((await request(b, `/workspaces/${wid}`)).status).toBe(404);
    expect((await request(b, `/shares/resource/story/${id}`)).status).toBe(404);
    const noConsent = await request(a, "/shares", "POST", { workspace_id: wid, resource_type: "story", resource_id: String(id), consent: false });
    expect(noConsent.status).toBe(422); expect((await request(a, "/shares/mine")).json.shares).toHaveLength(0);
    await expect(a.getByRole("option", { name: "Synthetic shared story" })).toBeAttached();
    await a.getByLabel("Item", { exact: true }).selectOption(String(id));
    const shareButton = a.getByRole("button", { name: "Share item" }); await expect(shareButton).toBeDisabled();
    await a.getByRole("checkbox", { name: /every current and future member/i }).check();
    const shared = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/shares" && r.request().method() === "POST");
    await shareButton.click(); const sharedResponse = await shared; expect(sharedResponse.status()).toBe(200);
    const grant = await sharedResponse.json(); expect(grant.permission).toBe("view");
    expect((await request(b, `/shares/resource/story/${id}`)).status).toBe(404);
    await b.goto("/workspaces");
    const accepted = b.waitForResponse(r => /\/workspaces\/invitations\/\d+\/accept$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
    await b.getByRole("button", { name: "Accept: Synthetic team" }).click(); expect((await accepted).status()).toBe(200);
    await expect(b.getByText("You joined the workspace.")).toBeVisible();
    const memberList = await request(b, "/shares/with-me"); expect(memberList.json.shares).toHaveLength(1); expect(String(memberList.json.shares[0].resource_id)).toBe(String(id));
    expect((await request(b, `/shares/resource/story/${id}`)).status).toBe(200);
    expect((await request(b, `/shares/resource/story/${privateId}`)).status).toBe(404);
    expect((await request(b, `/stories/${id}`)).status).toBe(404);
    expect((await request(b, `/stories/${id}`, "PATCH", { title: "Unauthorized" })).status).toBe(404);
    expect((await request(b, `/shares/${grant.share_id}`, "DELETE")).status).toBe(404);
    expect((await request(b, "/shares", "POST", { workspace_id: wid, resource_type: "story", resource_id: String(privateId), consent: true })).status).toBe(403);
    expect((await request(a, `/stories/${id}`)).json.title).toBe("Synthetic shared story");
    expect((await request(a, "/shares/mine")).json.shares).toHaveLength(1);
    await b.reload(); await expect(b.getByText(new RegExp(`Story #${id}`))).toBeVisible();
    await b.getByRole("button", { name: new RegExp(`View: Story #${id}`) }).click();
    await expect(b.getByText("Synthetic shared content")).toBeVisible();
    const revoked = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/shares/${grant.share_id}` && r.request().method() === "DELETE");
    await a.getByRole("button", { name: new RegExp(`Stop sharing: Story #${id}`) }).click(); expect((await revoked).status()).toBe(200);
    expect((await request(b, `/shares/resource/story/${id}`)).status).toBe(404);
    expect((await request(b, "/shares/with-me")).json.shares).toHaveLength(0);
    expect((await request(a, `/stories/${id}`)).json.title).toBe("Synthetic shared story");

    // Establish both directions before removal; the original revoked grant remains revoked.
    const ownerStory = await request(a, "/stories", "POST", { title: "Synthetic owner removal control", status: "user_created" });
    const memberStory = await request(b, "/stories", "POST", { title: "Synthetic member removal control", status: "user_created" });
    expect(ownerStory.status).toBe(201); expect(memberStory.status).toBe(201);
    const aid = ownerStory.json.id as number, bid = memberStory.json.id as number;
    const ownerGrant = await request(a, "/shares", "POST", { workspace_id: wid, resource_type: "story", resource_id: String(aid), consent: true });
    const memberGrant = await request(b, "/shares", "POST", { workspace_id: wid, resource_type: "story", resource_id: String(bid), consent: true });
    expect(ownerGrant.status).toBe(200); expect(ownerGrant.json.permission).toBe("view");
    expect(memberGrant.status).toBe(200); expect(memberGrant.json.permission).toBe("view");
    expect((await request(b, `/shares/resource/story/${aid}`)).status).toBe(200);
    expect((await request(a, `/shares/resource/story/${bid}`)).status).toBe(200);
    expect((await request(a, `/stories/${aid}`)).status).toBe(200);
    expect((await request(b, `/stories/${bid}`)).status).toBe(200);
    expect((await request(b, `/stories/${privateId}`)).status).toBe(404);
    // Refused actions happen before removal and must not alter the controls.
    expect((await request(b, `/workspaces/${wid}/members/${accounts.owner.id}/remove`, "POST")).status).toBe(403);
    expect((await request(b, `/workspaces/${wid}/members/${accounts.other.id}/remove`, "POST")).status).toBe(403);
    expect((await request(a, `/workspaces/${wid}/members/${accounts.owner.id}/remove`, "POST")).status).toBe(422);
    expect((await request(b, `/shares/resource/story/${aid}`)).status).toBe(200);
    expect((await request(a, `/shares/resource/story/${bid}`)).status).toBe(200);
    const detail = await request(a, `/workspaces/${wid}`);
    const target = detail.json.members.find((m: { user_id: number }) => m.user_id === accounts.other.id);
    expect(target).toBeTruthy();
    await a.reload();
    await a.getByRole("button", { name: `Remove: ${target.label}` }).click();
    const dialog = a.getByTestId("workspace-confirm");
    const removed = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/workspaces/${wid}/members/${accounts.other.id}/remove` && r.request().method() === "POST");
    await dialog.getByRole("button", { name: "Remove member" }).click();
    const removal = await removed; expect(removal.status()).toBe(200);
    const removalResult = await removal.json(); expect(removalResult.status).toBe("removed"); expect(removalResult.shares_revoked).toBe(1);
    // The very next requests use the same, still-authenticated member session.
    expect((await request(b, `/workspaces/${wid}`)).status).toBe(404);
    expect((await request(b, `/shares/resource/story/${aid}`)).status).toBe(404);
    expect((await request(b, `/workspaces/${wid}/members/${accounts.owner.id}/remove`, "POST")).status).toBe(404);
    expect((await request(b, "/shares", "POST", { workspace_id: wid, resource_type: "story", resource_id: String(bid), consent: true })).status).toBe(403);
    expect((await request(b, "/auth/me")).status).toBe(200);
    expect((await request(b, `/stories/${bid}`)).status).toBe(200);
    expect((await request(a, `/shares/resource/story/${bid}`)).status).toBe(404);
    expect((await request(a, `/workspaces/${wid}`)).status).toBe(200);
    expect((await request(a, `/stories/${aid}`)).status).toBe(200);
    await b.reload();
    expect((await request(b, `/workspaces/${wid}`)).status).toBe(404);
    expect((await request(b, `/shares/resource/story/${aid}`)).status).toBe(404);
  } finally { await owner.close(); await recipient.close(); }
});
