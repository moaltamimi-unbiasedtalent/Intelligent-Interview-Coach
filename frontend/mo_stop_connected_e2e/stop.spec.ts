import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { T, hydrated } from "../e2e/journey/definition";
import { refusal } from "../history_identity_connected_e2e/assertions";
import { createSseHeaderObserver, installMoStopObservation, realProgressObserved, stoppingStreamObserved, completeStreamObserved } from "./observation";

// ENGLISH — DISPOSABLE CONNECTED STACK — SYNTHETIC OFFLINE MODEL.
// Requests, SSE, persistence and authorization are real; there are no response mocks.
const api = process.env.STORY_API_URL!, state = process.env.MO_STOP_STATE_DIR!;
const accounts = JSON.parse(readFileSync(process.env.STORY_ACCOUNTS_FILE!, "utf8")) as Record<string, { id: number; email: string }>;
const password = "Synthetic-Story-Test-Password-42", lateAnswer = "Synthetic late fixture completion";
function check(value: unknown, label: string): asserts value { if (!value) throw new Error(label); }
async function isolated(browser: Browser): Promise<BrowserContext> {
  const context = await browser.newContext();
  await context.route("**/*", route => ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort("blockedbyclient"));
  return context;
}
async function call(context: BrowserContext, path: string, method = "GET") {
  const response = await context.request.fetch(api + path, { method });
  return { status: response.status(), json: await response.json() as Record<string, any> };
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in"); await hydrated(page, "#email");
  await page.locator("#email").fill(email); await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect.poll(async () => (await call(page.context(), "/auth/me")).status).toBe(200);
}
function stopped(value: Record<string, any>, runId: string) {
  return value.run_id === runId && value.status === "cancelled" && value.response === "" && Array.isArray(value.conversation)
    && !value.conversation.some((row: Record<string, unknown>) => row.content === lateAnswer)
    && value.pending_action === null && value.awaiting_human_input === false;
}
function settled(value: Record<string, any>) {
  return !!value.usage && Array.isArray(value.usage.missing_usage_sources) && !value.usage.missing_usage_sources.includes("stream_settlement_pending");
}
function safeForeign(value: { status: number; json: Record<string, any> }) {
  return refusal(value, 404, "not_found") && value.json.error.message === "Run not found.";
}

test("Candidate stops one real streamed run, retains ownership and revisits without execution replay", async ({ browser }) => {
  const contexts = [await isolated(browser), await isolated(browser)];
  try {
    const [owner, other] = await Promise.all(contexts.map(context => context.newPage()));
    await login(owner, accounts.owner.email); await login(other, accounts.other.email);
    check((await call(contexts[1], "/auth/me")).status === 200, "other authenticated positive control");
    let startRequests = 0, cancelRequests = 0, consoleErrors = 0, pageErrors = 0;
    for (const page of [owner, other]) {
      page.on("console", message => { if (message.type() === "error") consoleErrors++; });
      page.on("pageerror", () => { pageErrors++; });
    }
    owner.on("request", request => {
      const path = new URL(request.url()).pathname;
      if (request.method() === "POST" && ["/api/v1/agent/run", "/api/v1/agent/run/stream"].includes(path)) startRequests++;
      if (request.method() === "POST" && /^\/api\/v1\/agent\/runs\/[^/]+\/cancel$/.test(path)) cancelRequests++;
    });
    await owner.addInitScript({ content: `(${installMoStopObservation.toString()})(${createSseHeaderObserver.toString()});` });
    await owner.goto("/prepare"); await hydrated(owner, "textarea");
    await owner.getByLabel("What interview are you preparing for?").fill("Prepare for a synthetic interview");
    const streamed = owner.waitForResponse(response => new URL(response.url()).pathname === "/api/v1/agent/run/stream" && response.request().method() === "POST");
    await owner.getByRole("button", { name: "Start preparing", exact: true }).click();
    const startResponse = await streamed;
    check(startResponse.status() === 200 && startResponse.headers()["content-type"]?.startsWith("text/event-stream"), "real SSE accepted");
    await expect(owner).toHaveURL(/\/prepare\?run=[a-f0-9]{32}$/);
    const runId = new URL(owner.url()).searchParams.get("run")!;
    check(/^[a-f0-9]{32}$/.test(runId), "admitted run identity");
    writeFileSync(join(state, "run-id.json"), JSON.stringify({ run_id: runId }), { mode: 0o600 });
    await expect(owner.getByTestId("agent-stream-progress")).toBeVisible();
    await expect(owner.getByRole("button", { name: T("en", "agentStream.stop"), exact: true })).toBeVisible();
    await expect.poll(() => {
      const file = join(state, "barrier-entered.json");
      return existsSync(file) && JSON.parse(readFileSync(file, "utf8")).entered === true;
    }).toBe(true);
    await expect.poll(async () => realProgressObserved(await owner.evaluate(() =>
      window.__moStopSseObservation?.()))).toBe(true);
    const realProgress = true;
    check(startRequests === 1, "one deliberate start request");
    const ownerBefore = await call(contexts[0], `/agent/runs/${runId}`);
    check(ownerBefore.status === 200 && ownerBefore.json.run_id === runId && ownerBefore.json.status === "running", "owner active run positive control");
    const foreignCancel = await call(contexts[1], `/agent/runs/${runId}/cancel`, "POST");
    const foreignRead = await call(contexts[1], `/agent/runs/${runId}`);
    const foreignEvents = await call(contexts[1], `/agent/runs/${runId}/events`);
    check([foreignCancel, foreignRead, foreignEvents].every(safeForeign), "exact safe owner-scoped refusals");
    const ownerAfterForeign = await call(contexts[0], `/agent/runs/${runId}`);
    check(ownerAfterForeign.status === 200 && ownerAfterForeign.json.run_id === runId && ownerAfterForeign.json.status === "running", "foreign refusal leaves active run unchanged");
    const cancellation = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/agent/runs/${runId}/cancel` && response.request().method() === "POST");
    await owner.getByRole("button", { name: T("en", "agentStream.stop"), exact: true }).click();
    const cancelledResponse = await cancellation, cancelBody = await cancelledResponse.json();
    check(cancelledResponse.status() === 200 && cancelBody.run_id === runId && cancelBody.status === "cancelled" && cancelBody.settlement_pending === true, "same-run cooperative cancellation pending");
    await expect(owner.getByTestId("agent-stream-progress")).toContainText(T("en", "agentStream.stopping"));
    await expect(owner.getByRole("button", { name: T("en", "agentStream.stop"), exact: true })).toBeDisabled();
    const pending = await call(contexts[0], `/agent/runs/${runId}`);
    check(pending.status === 200 && stopped(pending.json, runId) && pending.json.usage?.missing_usage_sources?.includes("stream_settlement_pending"), "durable stop is pending settlement");
    check(cancelRequests === 1 && startRequests === 1, "one start and one UI cancellation");
    await expect.poll(async () => stoppingStreamObserved(await owner.evaluate(() =>
      window.__moStopSseObservation?.()))).toBe(true);
    const realStopping = true;
    // Existing private FIFO: release only the already-admitted synthetic model call.
    writeFileSync(join(state, "barrier-release"), "release");
    await expect(owner.getByText(T("en", "agentStream.stopped"), { exact: true })).toBeVisible();
    await expect(owner.getByText(lateAnswer, { exact: true })).toHaveCount(0);
    let terminal: Record<string, any> = {};
    await expect.poll(async () => {
      const result = await call(contexts[0], `/agent/runs/${runId}`); terminal = result.json;
      return result.status === 200 && stopped(result.json, runId) && settled(result.json);
    }).toBe(true);
    check(Array.isArray(terminal.tools_used) && terminal.tools_used.length === 0 && Array.isArray(terminal.tool_calls)
      && !terminal.tool_calls.some((row: Record<string, unknown>) => row.status === "ok"), "late tool work was not exposed as successful");
    await expect.poll(async () => completeStreamObserved(await owner.evaluate(() =>
      window.__moStopSseObservation?.()))).toBe(true);
    const realTerminal = true;
    const beforeRevisit = startRequests;
    await owner.reload();
    await expect(owner.getByText(T("en", "agentStream.stopped"), { exact: true })).toBeVisible();
    check(new URL(owner.url()).searchParams.get("run") === runId, "revisit preserves run identity");
    const revisited = await call(contexts[0], `/agent/runs/${runId}`);
    check(revisited.status === 200 && stopped(revisited.json, runId) && settled(revisited.json), "owner retrieves stopped result");
    check(safeForeign(await call(contexts[1], `/agent/runs/${runId}`)), "foreign revisit remains refused");
    await expect(owner.getByText(lateAnswer, { exact: true })).toHaveCount(0);
    check(startRequests === beforeRevisit && startRequests === 1 && cancelRequests === 1, "revisit issues no new start");
    check(consoleErrors === 0 && pageErrors === 0, "no unexpected browser errors");
    writeFileSync(join(state, "browser-facts.json"), JSON.stringify({
      start_requests: startRequests, cancel_requests: cancelRequests, run_identity_same: true,
      progress_visible: true, real_progress_observed: realProgress, real_stopping_observed: realStopping, real_terminal_observed: realTerminal, foreign_cancel_status: foreignCancel.status, foreign_read_status: foreignRead.status,
      foreign_events_status: foreignEvents.status, foreign_refusal_safe: true, other_authenticated: true,
      foreign_state_unchanged: true, stop_recorded: true, cancel_pending_true: true, stopping_visible: true,
      terminal_cancelled: true, terminal_settled: true, late_answer_hidden: true, late_tool_absent: true,
      revisit_same_run: true, revisit_start_requests: startRequests - beforeRevisit,
      console_errors: consoleErrors, page_errors: pageErrors,
    }), { mode: 0o600 });
  } finally { for (const context of contexts) await context.close(); }
});
