import { dirname, join } from "node:path";
import { readFileSync } from "node:fs";
import { expect, test, type Browser, type Page } from "@playwright/test";

const api = process.env.LINK_API_URL!;
const accountsFile = process.env.LINK_ACCOUNTS_FILE!;
const accounts = JSON.parse(readFileSync(accountsFile, "utf8")) as Record<string, { id: number; email: string }>;
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
    const r = await fetch(base + path, { method, credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, json: await r.json() };
  }, { base: api, path, method, body });
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in"); await page.locator("#email").fill(email); await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect.poll(async () => (await request(page, "/auth/me")).status).toBe(200);
}
function linkFor(name: string) {
  // Runtime-only private file; never attach, log, include in errors or preserve it.
  return (JSON.parse(readFileSync(join(dirname(accountsFile), `mail-${name}.json`), "utf8")) as { link: string }).link;
}
async function openCapturedLink(page: Page, link: string) {
  await page.goto("/workspaces/accept");
  // Browser opens the actual captured URL. Never pass it to goto's call log.
  await page.evaluate(url => { window.location.assign(url); }, link);
}

test("captured invitation link enforces verified recipient, expiry, revocation and replay", async ({ browser }) => {
  const contexts = await Promise.all(["owner", "recipient", "wrong", "unverified", "expired", "revoked"].map(() => context(browser)));
  try {
    const pages = await Promise.all(contexts.map(ctx => ctx.newPage()));
    const [owner, recipient, wrong, unverified, expired, revoked] = pages;
    let idAcceptanceCalls = 0;
    recipient.on("request", req => { if (/\/workspaces\/invitations\/\d+\/accept$/.test(new URL(req.url()).pathname)) idAcceptanceCalls++; });
    for (const [i, name] of ["owner", "recipient", "wrong", "unverified", "expired", "revoked"].entries()) await login(pages[i], accounts[name].email);
    const ws = await request(owner, "/workspaces", "POST", { name: "Synthetic link team" }); expect(ws.status).toBe(200); const wid = ws.json.id as number;
    const story = await request(owner, "/stories", "POST", { title: "Synthetic private story", status: "user_created" }); expect(story.status).toBe(201); const sid = story.json.id as number;
    const invitations: Record<string, number> = {};
    for (const name of ["recipient", "unverified", "expired", "revoked"]) {
      const response = await request(owner, `/workspaces/${wid}/invite`, "POST", { email: accounts[name].email });
      expect(response.status).toBe(200); expect(response.json.email_delivery).toBe("submitted");
      expect(JSON.stringify(response.json)).not.toMatch(/token|secret|code/i); invitations[name] = response.json.invitation_id;
    }
    const link = linkFor("recipient");
    expect(new URL(link).origin === new URL(process.env.BASE_URL!).origin, "captured invitation origin must match the configured synthetic application origin").toBe(true);
    const token = new URL(link).searchParams.get("token")!;
    // Opening or presenting someone else's link cannot create membership or consume it.
    const wrongPreview = await request(wrong, "/workspaces/invitations/preview", "POST", { token });
    const wrongAccept = await request(wrong, "/workspaces/invitations/accept", "POST", { token });
    expect(wrongPreview.status).toBe(403); expect(wrongAccept.status).toBe(403);
    expect((await request(wrong, `/workspaces/${wid}`)).status).toBe(404);
    const noVerifyToken = new URL(linkFor("unverified")).searchParams.get("token")!;
    expect((await request(unverified, "/workspaces/invitations/preview", "POST", { token: noVerifyToken })).status).toBe(403);
    expect((await request(unverified, "/workspaces/invitations/accept", "POST", { token: noVerifyToken })).status).toBe(403);
    const expiredToken = new URL(linkFor("expired")).searchParams.get("token")!;
    expect((await request(expired, "/workspaces/invitations/preview", "POST", { token: expiredToken })).status).toBe(409);
    expect((await request(expired, "/workspaces/invitations/accept", "POST", { token: expiredToken })).status).toBe(409);
    const revokedToken = new URL(linkFor("revoked")).searchParams.get("token")!;
    expect((await request(owner, `/workspaces/${wid}/invitations/${invitations.revoked}/revoke`, "POST")).status).toBe(200);
    expect((await request(revoked, "/workspaces/invitations/preview", "POST", { token: revokedToken })).status).toBe(409);
    expect((await request(revoked, "/workspaces/invitations/accept", "POST", { token: revokedToken })).status).toBe(409);
    expect((await request(recipient, "/workspaces/invitations/preview", "POST", { token: "invalid-synthetic-token" })).status).toBe(404);
    await recipient.goto("/workspaces/accept"); await expect(recipient.getByText(/invitation link is incomplete/i)).toBeVisible();
    expect((await request(recipient, `/workspaces/${wid}`)).status).toBe(404);
    expect((await request(recipient, `/stories/${sid}`)).status).toBe(404);
    const preview = recipient.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces/invitations/preview" && r.request().method() === "POST");
    await openCapturedLink(recipient, link); expect((await preview).status()).toBe(200);
    await expect(recipient.getByText("Synthetic link team")).toBeVisible();
    expect((await request(recipient, `/workspaces/${wid}`)).status).toBe(404); // preview is not acceptance
    const accept = recipient.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces/invitations/accept" && r.request().method() === "POST");
    await recipient.getByRole("button", { name: "Accept invitation" }).click(); expect((await accept).status()).toBe(200);
    await expect(recipient.getByText("You joined the workspace.")).toBeVisible();
    expect(idAcceptanceCalls).toBe(0);
    expect((await request(recipient, `/workspaces/${wid}`)).json.my_role).toBe("workspace_member");
    expect((await request(recipient, `/stories/${sid}`)).status).toBe(404);
    expect((await request(recipient, `/shares/resource/story/${sid}`)).status).toBe(404);
    expect((await request(recipient, "/workspaces/invitations/accept", "POST", { token })).status).toBe(409);
    await recipient.getByRole("link", { name: "Open the workspace" }).click(); await recipient.reload();
    expect((await request(recipient, `/workspaces/${wid}`)).json.my_role).toBe("workspace_member");
    for (const page of [wrong, unverified, expired, revoked]) expect((await request(page, `/workspaces/${wid}`)).status).toBe(404);

    // A second verified invitee declines the unmodified captured email link.
    const declinedInvite = await request(owner, `/workspaces/${wid}/invite`, "POST", { email: accounts.wrong.email });
    expect(declinedInvite.status).toBe(200);
    expect(declinedInvite.json.email_delivery).toBe("submitted");
    expect(JSON.stringify(declinedInvite.json)).not.toMatch(/token|secret|code/i);
    const declineLink = linkFor("wrong");
    expect(new URL(declineLink).origin === new URL(process.env.BASE_URL!).origin).toBe(true);
    const declineToken = new URL(declineLink).searchParams.get("token")!;
    // The existing member cannot use an invitation addressed to another account.
    expect((await request(recipient, "/workspaces/invitations/preview", "POST", { token: declineToken })).status).toBe(403);
    expect((await request(recipient, "/workspaces/invitations/decline", "POST", { token: declineToken })).status).toBe(403);
    const declinePreview = wrong.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces/invitations/preview" && r.request().method() === "POST");
    await openCapturedLink(wrong, declineLink);
    expect((await declinePreview).status()).toBe(200);
    await expect(wrong.getByText("Synthetic link team")).toBeVisible();
    expect((await request(wrong, `/workspaces/${wid}`)).status).toBe(404);
    expect((await request(wrong, `/stories/${sid}`)).status).toBe(404);
    const decline = wrong.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces/invitations/decline" && r.request().method() === "POST");
    await wrong.getByRole("button", { name: "Decline invitation" }).click();
    expect((await decline).status()).toBe(200);
    await expect(wrong.getByText(/Invitation declined\. Nothing was shared/i)).toBeVisible();
    expect((await request(wrong, `/workspaces/${wid}`)).status).toBe(404);
    expect((await request(wrong, `/stories/${sid}`)).status).toBe(404);
    expect((await request(wrong, `/shares/resource/story/${sid}`)).status).toBe(404);
    expect((await request(wrong, "/workspaces/invitations/accept", "POST", { token: declineToken })).status).toBe(409);
    expect((await request(wrong, "/workspaces/invitations/decline", "POST", { token: declineToken })).status).toBe(409);
    const afterReload = wrong.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces/invitations/preview" && r.request().method() === "POST");
    await wrong.reload();
    expect((await afterReload).status()).toBe(409);
    expect((await request(wrong, `/workspaces/${wid}`)).status).toBe(404);
  } finally { await Promise.all(contexts.map(ctx => ctx.close())); }
});
