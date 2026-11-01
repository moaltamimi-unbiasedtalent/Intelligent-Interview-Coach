import { noPrivateFields } from "./privacy-assertions";
import { assessRefusal, type RefusalFacts } from "./auth-refusal";
import { readFileSync, existsSync, appendFileSync } from "node:fs";
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
async function refusal(page: Page, scenario: "anonymous" | "logged_out", logoutSuccess: boolean | null) {
  const result = await page.evaluate(async (base) => {
    try {
      const response = await fetch(base + "/auth/account/export", { credentials: "include" });
      let body: unknown = null;
      try { body = await response.json(); } catch { /* invalid JSON is an assertion failure */ }
      return { status: response.status, contentType: response.headers.get("content-type"), attachment: response.headers.get("content-disposition"), body };
    } catch { return { status: 0, contentType: null, attachment: null, body: null }; }
  }, api);
  const facts: RefusalFacts = assessRefusal({ scenario, ...result, logoutSuccess });
  appendFileSync(join(process.env.STORY_OUTPUT_DIR!, "auth-refusal-facts.jsonl"), JSON.stringify(facts) + "\n", { mode: 0o600 });
  check(facts.passed, `${scenario} authentication refusal failed`);
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in"); await page.locator("#email").fill(email); await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect.poll(async () => (await request(page, "/auth/me")).status).toBe(200);
}

function check(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

async function download(page: Page) {
  await page.goto("/account/data");
  const link = page.getByTestId("dp-export-link"); await expect(link).toBeVisible();
  await expect(page.getByText(/other people's data/i).first()).toBeVisible();
  const [item, response] = await Promise.all([
    page.waitForEvent("download"),
    page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/auth/account/export" && r.request().method() === "GET"),
    link.click(),
  ]);
  check(response.status() === 200, "export status");
  const headers = response.headers();
  check(headers["content-type"]?.startsWith("application/json"), "export content type");
  check(headers["content-disposition"] === 'attachment; filename="ask4mo-my-data.json"', "export attachment header");
  check(headers["cache-control"]?.includes("no-store"), "export cache policy");
  check(item.suggestedFilename() === "ask4mo-my-data.json", "download filename");
  const stream = await item.createReadStream(); check(stream, "download stream");
  const chunks: Buffer[] = []; for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  const data = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  await item.delete();
  check(data.format === "ask4mo.candidate-export.v1", "export format");
  check(Array.isArray(data.scope?.included) && Array.isArray(data.scope?.not_included), "export scope");
  check(data.scope.included.includes("stories") && data.scope.not_included.includes("other people's data, including content shared with you"), "scope guidance");
  check(noPrivateFields(data), "sensitive field present");
  return data;
}
test("real account download exports only caller-owned records despite VIEW access", async ({ browser }) => {
  const owner = await context(browser), other = await context(browser), anon = await context(browser);
  try {
    const a = await owner.newPage(), b = await other.newPage(), guest = await anon.newPage();
    await login(a, accounts.owner.email); await login(b, accounts.other.email);
    const oppA = await request(a, "/opportunities", "POST", { target_role: "SYNTH_A_ROLE", company_name: "SYNTH_A_COMPANY" });
    const oppB = await request(b, "/opportunities", "POST", { target_role: "SYNTH_B_ROLE", company_name: "SYNTH_B_COMPANY" });
    check(oppA.status === 201 && oppB.status === 201, "opportunity creation");
    const oa = oppA.json.id as number, ob = oppB.json.id as number;
    const story = (page: Page, title: string, situation: string, opportunity_id: number) => request(page, "/stories", "POST", { title, situation, status: "user_created", opportunity_id });
    const sa = await story(a, "Selected synthetic story", markers[0], oa);
    const sb = await story(a, "Unselected synthetic story", markers[1], oa);
    const sc = await story(b, "Foreign synthetic story", markers[2], ob);
    check(sa.status === 201 && sb.status === 201 && sc.status === 201, "story creation");
    const sid = sa.json.id as number, uid = sb.json.id as number, fid = sc.json.id as number;
    await a.goto("/practice");
    await a.getByPlaceholder(/Senior Product Manager/i).fill("Registered Nurse"); await a.getByPlaceholder(/fintech/i).fill("healthcare");
    await a.getByRole("combobox", { name: "Career level" }).selectOption("senior");
    await a.getByRole("checkbox", { name: /Selected synthetic story/ }).check();
    await a.getByRole("checkbox", { name: /I understand that the stories I selected/i }).check();
    const creation = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/interviews" && r.request().method() === "POST");
    await a.getByRole("button", { name: "Start interview" }).click();
    const sessionResponse = await creation; check(sessionResponse.status() === 200, "practice creation");
    const payload = sessionResponse.request().postDataJSON().configuration;
    check(JSON.stringify(payload.story_ids) === JSON.stringify([sid]) && payload.confirm_story_use === true && !(payload.use_candidate_evidence ?? false), "practice consent");
    const sessionId = (await sessionResponse.json()).session_id as string;
    await expect(a.getByRole("heading", { level: 1, name: fixtures.interview.questions[0] })).toBeVisible();
    await b.goto("/workspaces"); await b.getByLabel(/Workspace name/i).fill("Synthetic shared workspace");
    const workspaceResponse = b.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces" && r.request().method() === "POST");
    await b.getByRole("button", { name: "Create workspace" }).click(); const wr = await workspaceResponse; check(wr.status() === 200, "workspace creation");
    const wid = (await wr.json()).id as number;
    await b.getByRole("link", { name: "Open workspace: Synthetic shared workspace" }).click();
    await b.getByLabel("Email address").fill(accounts.owner.email);
    const invited = b.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/workspaces/${wid}/invite` && r.request().method() === "POST");
    await b.getByRole("button", { name: "Send invitation" }).click(); check((await invited).status() === 200, "invitation");
    await b.getByLabel("Item", { exact: true }).selectOption(String(fid));
    await b.getByRole("checkbox", { name: /every current and future member/i }).check();
    const shared = b.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/shares" && r.request().method() === "POST");
    await b.getByRole("button", { name: "Share item" }).click(); const gr = await shared; check(gr.status() === 200 && (await gr.json()).permission === "view", "view sharing");
    await a.goto("/workspaces");
    const accepted = a.waitForResponse(r => /\/workspaces\/invitations\/\d+\/accept$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
    await a.getByRole("button", { name: "Accept: Synthetic shared workspace" }).click(); check((await accepted).status() === 200, "invitation acceptance");
    check((await request(a, `/shares/resource/story/${fid}`)).status === 200, "shared story readable");
    const snapshot = async () => JSON.stringify([(await request(a, "/stories")).json, (await request(b, "/stories")).json, (await request(a, "/opportunities")).json, (await request(b, "/opportunities")).json, (await request(a, "/interviews")).json, (await request(b, "/shares/mine")).json, (await request(a, "/auth/me")).json, (await request(b, "/auth/me")).json, (await request(a, `/workspaces/${wid}`)).json, (await request(a, "/privacy/requests?page=1&page_size=20")).json, (await request(b, "/privacy/requests?page=1&page_size=20")).json]);
    const before = await snapshot();
    const exportedA = await download(a), exportedB = await download(b);
    check(exportedA.account.user_id === accounts.owner.id && exportedB.account.user_id === accounts.other.id, "caller identity");
    check(exportedA.opportunities.length === 1 && exportedB.opportunities.length === 1 && exportedA.stories.length === 2 && exportedB.stories.length === 1, "expected record counts");
    check(exportedA.opportunities.some((x: { id: number }) => x.id === oa) && exportedB.opportunities.some((x: { id: number }) => x.id === ob), "owned opportunity presence");
    check(!exportedA.opportunities.some((x: { id: number }) => x.id === ob) && !exportedB.opportunities.some((x: { id: number }) => x.id === oa), "foreign opportunity exclusion");
    const x = exportedA.stories.find((v: { id: number }) => v.id === sid), y = exportedA.stories.find((v: { id: number }) => v.id === uid), z = exportedB.stories.find((v: { id: number }) => v.id === fid);
    check(x?.situation === markers[0] && y?.situation === markers[1] && z?.situation === markers[2], "owned story inclusion");
    check(x.opportunity_id === oa && y.opportunity_id === oa && z.opportunity_id === ob, "story opportunity links");
    check(x.practice_uses.length === 1 && x.practice_uses[0].session_id === sessionId && y.practice_uses.length === 0 && z.practice_uses.length === 0, "story use attribution");
    check(x.evidence_claim_ids.length === 0 && x.evidence_answer_ids.length === 0 && y.evidence_claim_ids.length === 0 && z.evidence_claim_ids.length === 0, "story evidence link projections");
    check(!exportedA.stories.some((v: { id: number }) => v.id === fid) && !exportedB.stories.some((v: { id: number }) => v.id === sid || v.id === uid), "foreign story ids");
    check(!JSON.stringify(exportedA).includes(markers[2]) && !JSON.stringify(exportedB).includes(markers[0]) && !JSON.stringify(exportedB).includes(markers[1]), "foreign story content");
    check(exportedA.data?.user?.id === accounts.owner.id && exportedB.data?.user?.id === accounts.other.id, "legacy owner projection");
    check(Array.isArray(exportedA.interviews) && exportedA.interviews.length === 0 && Array.isArray(exportedA.data?.interviews) && exportedA.data.interviews.length === 0, "active session is not completed history");
    check(Array.isArray(exportedB.interviews) && exportedB.interviews.length === 0 && Array.isArray(exportedB.data?.interviews) && exportedB.data.interviews.length === 0, "foreign completed history control");
    const hinted = await request(a, `/auth/account/export?user_id=${accounts.other.id}`);
    check(hinted.status === 200 && hinted.json.account.user_id === accounts.owner.id && !JSON.stringify(hinted.json).includes(markers[2]), "owner selector ignored");
    await guest.goto("/sign-in"); await refusal(guest, "anonymous", null);
    check(await snapshot() === before, "export changed source state");
    await b.goto("/account");
    check((await request(b, "/auth/me")).status === 200, "pre-logout authentication");
    const logoutResponse = b.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/auth/logout" && r.request().method() === "POST");
    await b.getByRole("button", { name: /sign out|log out/i }).first().click();
    const logout = await logoutResponse;
    let logoutBody: { message?: string } = {};
    try { logoutBody = await logout.json(); } catch { /* malformed logout is not success */ }
    const logoutSuccess = logout.status() === 200 && logoutBody.message === "Signed out.";
    await refusal(b, "logged_out", logoutSuccess);
  } finally { await owner.close(); await other.close(); await anon.close(); }
});
