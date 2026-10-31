import { execFileSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";
import fixtures from "../e2e/journey/fixtures.json";

const api = process.env.STORY_API_URL!;
const file = process.env.STORY_ACCOUNTS_FILE!;
const accounts = JSON.parse(readFileSync(file, "utf8")) as Record<string, { id: number; email: string }>;
const password = "Synthetic-Story-Test-Password-42";
const markers = ["SYNTH_SELECTED_CEDAR", "SYNTH_UNSELECTED_MAPLE", "SYNTH_FOREIGN_WILLOW"];
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

function facts(a: number, b: number, session: string) {
  return JSON.parse(execFileSync("python", ["../scripts/e2e/story_deletion_snapshot.py", dirname(file), String(a), String(b), session], { encoding: "utf8" }));
}
test("deletion selectively removes used story and revokes sharing", async ({ browser }) => {
  const owner = await context(browser), other = await context(browser);
  try {
    const a = await owner.newPage(), b = await other.newPage();
    await login(a, accounts.owner.email); await login(b, accounts.other.email);
    const create = (title: string, situation: string) => request(a, "/stories", "POST", { title, situation, status: "user_created" });
    const selected = await create("Selected synthetic story", markers[0]);
    const retained = await create("Unselected synthetic story", markers[1]);
    expect([selected.status, retained.status]).toEqual([201, 201]);
    const sid = selected.json.id as number, kid = retained.json.id as number;
    await a.goto("/practice");
    await a.getByPlaceholder(/Senior Product Manager/i).fill("Registered Nurse");
    await a.getByPlaceholder(/fintech/i).fill("healthcare");
    await a.getByRole("combobox", { name: "Career level" }).selectOption("senior");
    await a.getByRole("checkbox", { name: /Selected synthetic story/ }).check();
    await a.getByRole("checkbox", { name: /Unselected synthetic story/ }).check();
    await a.getByRole("checkbox", { name: /I understand that the stories I selected/i }).check();
    const created = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/interviews" && r.request().method() === "POST");
    await a.getByRole("button", { name: "Start interview" }).click();
    const sessionResponse = await created; expect(sessionResponse.status()).toBe(200);
    const cfg = sessionResponse.request().postDataJSON().configuration;
    expect(cfg.story_ids).toEqual([sid, kid]); expect(cfg.confirm_story_use).toBe(true); expect(cfg.use_candidate_evidence ?? false).toBe(false);
    const session = (await sessionResponse.json()).session_id as string;
    await expect(a.getByRole("heading", { level: 1, name: fixtures.interview.questions[0] })).toBeVisible();
    expect(facts(sid, kid, session)).toMatchObject({ a_row: true, b_row: true, one_session: true, a_use: 1, b_use: 1, same_session: true, a_context: true, a_marker: true, b_context: true, expected_owner_session: true });
    await a.goto("/workspaces"); await a.getByLabel(/Workspace name/i).fill("Synthetic team");
    const wsCreated = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces" && r.request().method() === "POST");
    await a.getByRole("button", { name: "Create workspace" }).click();
    const wr = await wsCreated; expect(wr.status()).toBe(200); const wid = (await wr.json()).id as number;
    await a.getByRole("link", { name: "Open workspace: Synthetic team" }).click();
    await a.getByLabel("Email address").fill(accounts.other.email);
    const invited = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/workspaces/${wid}/invite` && r.request().method() === "POST");
    await a.getByRole("button", { name: "Send invitation" }).click(); expect((await invited).status()).toBe(200);
    await a.getByLabel("Item", { exact: true }).selectOption(String(sid));
    await a.getByRole("checkbox", { name: /every current and future member/i }).check();
    const shared = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/shares" && r.request().method() === "POST");
    await a.getByRole("button", { name: "Share item" }).click(); const grant = await shared; expect(grant.status()).toBe(200); expect((await grant.json()).permission).toBe("view");
    await b.goto("/workspaces");
    const accepted = b.waitForResponse(r => /\/workspaces\/invitations\/\d+\/accept$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
    await b.getByRole("button", { name: "Accept: Synthetic team" }).click(); expect((await accepted).status()).toBe(200);
    expect((await request(b, `/shares/resource/story/${sid}`)).status).toBe(200);
    expect((await request(b, `/shares/resource/story/${kid}`)).status).toBe(404);
    const before = facts(sid, kid, session);
    expect((await request(b, `/stories/${sid}`, "DELETE")).status).toBe(404);
    expect(facts(sid, kid, session)).toEqual(before);
    await a.goto("/documents");
    const card = a.getByTestId(`story-${sid}`); await card.getByRole("button", { name: "Delete" }).click();
    const dialog = a.getByRole("alertdialog", { name: /Selected synthetic story/ });
    await expect(dialog).toContainText("Text copied into your practice sessions");
    const deletion = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/stories/${sid}` && r.request().method() === "DELETE");
    await dialog.getByRole("button", { name: "Delete" }).click(); expect((await deletion).status()).toBe(200);
    expect(facts(sid, kid, session)).toMatchObject({ a_row: false, b_row: true, one_session: true, a_use: 0, b_use: 1, same_session: true, a_context: false, a_marker: false, b_context: true, expected_owner_session: true });
    expect(facts(sid, kid, session).other_config_digest).toBe(before.other_config_digest);
    expect(facts(sid, kid, session).a_grant).toEqual([["view", "revoked"]]);
    expect((await request(a, `/stories/${kid}`)).json).toMatchObject({ title: "Unselected synthetic story", situation: markers[1], status: "user_created", verification: "unverified", use_count: 1 });
    expect((await request(b, `/shares/resource/story/${sid}`)).status).toBe(404);
    expect((await request(b, "/auth/me")).status).toBe(200);
    expect((await request(b, `/workspaces/${wid}`)).status).toBe(200);
    expect((await request(b, `/shares/resource/story/${kid}`)).status).toBe(404);
    await a.reload(); await expect(a.getByTestId(`story-${sid}`)).toHaveCount(0); await expect(a.getByTestId(`story-${kid}`)).toBeVisible();
    await a.goto(`/practice?session=${encodeURIComponent(session)}`);
    await expect(a.getByRole("heading", { level: 1, name: fixtures.interview.questions[0] })).toBeVisible();
    await a.reload();
    expect((await request(a, `/interviews/${session}`)).status).toBe(200);
    expect((await request(a, "/interviews")).json.sessions).toHaveLength(1);
    expect(facts(sid, kid, session)).toMatchObject({ a_row: false, a_use: 0, a_context: false, a_marker: false, b_row: true, b_use: 1, b_context: true, expected_owner_session: true, one_session: true });
  } finally { await owner.close(); await other.close(); }
});
