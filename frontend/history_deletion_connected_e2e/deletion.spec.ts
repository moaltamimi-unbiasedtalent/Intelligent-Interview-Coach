import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { T, hydrated } from "../e2e/journey/definition";
import fixtures from "../e2e/journey/fixtures.json";
import { refusal } from "../history_identity_connected_e2e/assertions";
import type { InterviewStateResponse, ReportResponse } from "../lib/api/types";

const api = process.env.STORY_API_URL!, state = process.env.HISTORY_DELETE_STATE_DIR!;
const accounts = JSON.parse(readFileSync(process.env.STORY_ACCOUNTS_FILE!, "utf8")) as Record<string, { id: number; email: string }>;
const password = "Synthetic-Story-Test-Password-42";
const roles = ["Synthetic Deletion Target", "Synthetic Owner Keeper", "Synthetic Foreign Keeper"];
const answers = ["Synthetic target answer", "Synthetic owner keeper answer", "Synthetic foreign keeper answer"];
interface Identity { ids: number[]; sessions: string[] }
interface HistorySummary { id: number; target_role: string; created_at?: string }
interface HistoryDetail { id: number; configuration: { target_role: string }; questions: unknown[]; report: unknown }
function check(value: unknown, label: string): asserts value { if (!value) throw new Error(label); }
function facts(phase: string, value: Record<string, boolean | number>) {
  const encoded = JSON.stringify(value);
  check(Buffer.byteLength(encoded) <= 2048, "Bounded browser facts");
  writeFileSync(join(state, `${phase}-facts.json`), encoded, { mode: 0o600 });
}
function modelObservations() { return readFileSync(join(state, "model-stages.jsonl"), "utf8"); }
async function isolated(browser: Browser) {
  const context = await browser.newContext();
  await context.route("**/*", route => ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname)
    ? route.continue() : route.abort("blockedbyclient"));
  return context;
}
async function call<T = Record<string, unknown>>(context: BrowserContext, path: string, method = "GET", body?: object) {
  // Actual application requests with the authenticated context's HttpOnly cookie; no API response mocks.
  const response = await context.request.fetch(api + path, { method, data: body });
  return { status: response.status(), json: await response.json() as T };
}
async function login(page: Page, context: BrowserContext, email: string) {
  await page.goto("/sign-in"); await hydrated(page, "#email");
  await page.locator("#email").fill(email); await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect.poll(async () => (await call(context, "/auth/me")).status).toBe(200);
}
function observe(page: Page) {
  const counters = { console_errors: 0, page_errors: 0, deletes: 0, mutations: 0 };
  page.on("console", value => { if (value.type() === "error") counters.console_errors++; });
  page.on("pageerror", () => counters.page_errors++);
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET" && path.startsWith("/api/v1/")) counters.mutations++;
    if (request.method() === "DELETE" && /^\/api\/v1\/history\/interviews\/\d+$/.test(path)) counters.deletes++;
  });
  return counters;
}
function noErrors(counters: ReturnType<typeof observe>) {
  check(counters.console_errors === 0 && counters.page_errors === 0, "No unexpected browser console or page errors");
}
function fixtureTexts(value: unknown): string[] {
  if (typeof value === "string") return value.length >= 16 ? [value] : [];
  if (Array.isArray(value)) return value.flatMap(fixtureTexts);
  if (value && typeof value === "object") return Object.values(value).flatMap(fixtureTexts);
  return [];
}
function safeRefusal(value: { status: number; json: Record<string, unknown> }, status: number, code: string) {
  check(refusal(value, status, code), "Exact bounded refusal envelope");
  const retained = JSON.stringify(value.json);
  check(![...roles, ...answers, password, accounts.owner.email, accounts.other.email, ...fixtureTexts(fixtures.interview)].some(canary => retained.includes(canary)), "Refusal contains no private record or credential canary");
  if (status === 422) check((value.json.error as Record<string, unknown>).message === "Unknown interview session.", "Discarded source remains unknown");
}
async function list(context: BrowserContext, expected: number[], forbidden: number[]) {
  const response = await call<{ interviews: HistorySummary[] }>(context, "/history/interviews");
  check(response.status === 200 && Array.isArray(response.json.interviews), "Authenticated History list");
  const ids = response.json.interviews.map(row => row.id);
  check(isDeepStrictEqual([...ids].sort((a, b) => a - b), [...expected].sort((a, b) => a - b)) && !ids.some(id => forbidden.includes(id)), "Exact owner-scoped History membership");
  return response.json.interviews;
}
async function detail(context: BrowserContext, id: number) {
  const response = await call<{ interview: HistoryDetail }>(context, `/history/interviews/${id}`);
  check(response.status === 200 && response.json.interview.id === id, "Owned completed-interview detail");
  return response.json.interview;
}
async function prepare(context: BrowserContext, index: number) {
  // Reuse the established four-step API fixture setup; the new acceptance boundary is the deletion UI.
  const creation = await call<InterviewStateResponse>(context, "/interviews", "POST", { configuration: {
    target_role: roles[index], industry_or_sector: "healthcare", career_level: "senior", number_of_questions: 1,
  } });
  check(creation.status === 200 && typeof creation.json.session_id === "string" && !!creation.json.session_id, "Synthetic completed-record session setup");
  const session = creation.json.session_id;
  const answer = await call<InterviewStateResponse>(context, `/interviews/${session}/answers`, "POST", { answer: answers[index] });
  check(answer.status === 200 && isDeepStrictEqual(answer.json.last_evaluation, fixtures.interview.evaluation), "Synthetic record evaluated by existing fixture boundary");
  const completion = await call<InterviewStateResponse>(context, `/interviews/${session}/next-question`, "POST", {});
  check(completion.status === 200 && completion.json.state === "INTERVIEW_COMPLETE", "Synthetic record completed");
  const report = await call<ReportResponse>(context, `/interviews/${session}/report`, "POST", {});
  check(report.status === 200 && report.json.save_failed === false && Number.isInteger(report.json.saved_report_id) && Number(report.json.saved_report_id) > 0 && isDeepStrictEqual(report.json.report, fixtures.interview.report), "Synthetic record and report persisted");
  return { id: report.json.saved_report_id as number, session };
}
async function openTarget(page: Page, rows: HistorySummary[], target: number) {
  const row = rows.find(value => value.id === target);
  check(row?.target_role === roles[0], "Deletion selected the intended API record");
  const date = typeof row.created_at === "string" ? row.created_at.slice(0, 10) : "";
  const label = date ? `${row.target_role} (${date})` : row.target_role;
  await page.goto("/account/data");
  const card = page.getByTestId("dp-manage-interviews");
  const button = card.getByRole("button", { name: `${T("en", "dataPrivacy.deleteAction")}: ${label}`, exact: true });
  await expect(button).toHaveCount(1); await hydrated(page, '[data-testid="dp-manage-interviews"] button');
  await expect(card).toContainText(T("en", "dataPrivacy.intNote"));
  await button.click();
  const dialog = page.getByTestId("dp-confirm");
  await expect(dialog).toHaveRole("alertdialog");
  await expect(dialog).toHaveAccessibleName(T("en", "dataPrivacy.confirmDeleteInterviewTitle"));
  await expect(dialog).toHaveAccessibleDescription(T("en", "dataPrivacy.confirmDeleteInterviewBody", { name: label }));
  await expect(dialog.getByRole("button", { name: T("en", "common.cancel"), exact: true })).toBeFocused();
  return { card, dialog, label };
}
async function retainedUI(page: Page, keeper: number, removed: number) {
  await page.goto("/history");
  const link = page.locator(`a[href='/history/${keeper}']`);
  await expect(link).toHaveCount(1); await expect(link).toContainText(roles[1]);
  await expect(page.locator(`a[href='/history/${removed}']`)).toHaveCount(0);
  const opening = page.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/history/interviews/${keeper}`);
  await link.click(); check((await opening).status() === 200, "Retained History link reaches the real API");
  await expect(page).toHaveURL(new RegExp(`/history/${keeper}$`));
  await expect(page.getByText(fixtures.interview.report.performance_summary, { exact: true })).toBeVisible();
}

test("Candidate deletes exactly one completed interview while ownership and retained records remain intact", async ({ browser }) => {
  const ownerContext = await isolated(browser), otherContext = await isolated(browser), anonymous = await isolated(browser);
  try {
    const owner = await ownerContext.newPage(), other = await otherContext.newPage();
    await login(owner, ownerContext, accounts.owner.email); await login(other, otherContext, accounts.other.email);
    const ownerCounters = observe(owner), otherCounters = observe(other);
    if (process.env.HISTORY_DELETE_PHASE === "prepare") {
      const records = [await prepare(ownerContext, 0), await prepare(ownerContext, 1), await prepare(otherContext, 2)];
      const ids = records.map(record => record.id), sessions = records.map(record => record.session);
      check(new Set(ids).size === 3 && new Set(sessions).size === 3, "Distinct completed record and source identities");
      await list(ownerContext, ids.slice(0, 2), [ids[2]]); await list(otherContext, [ids[2]], ids.slice(0, 2));
      check(modelObservations().split("\n").filter(Boolean).length === 12, "Exactly twelve model-boundary fixture calls during setup");
      noErrors(ownerCounters); noErrors(otherCounters);
      writeFileSync(join(state, "history-delete-private.json"), JSON.stringify({ ids, sessions }), { mode: 0o600 });
      facts("prepare", { records: 3, owners: 2, completed: true, distinct_identities: true });
    } else {
      const identity = JSON.parse(readFileSync(join(state, "history-delete-private.json"), "utf8")) as Identity;
      const [target, ownKeeper, foreignKeeper] = identity.ids, source = identity.sessions[0];
      const beforeModel = modelObservations();
      if (process.env.HISTORY_DELETE_PHASE === "refuse") {
        const targetBefore = await detail(ownerContext, target);
        const foreign = await call(otherContext, `/history/interviews/${target}`, "DELETE");
        const guest = await call(anonymous, `/history/interviews/${target}`, "DELETE");
        safeRefusal(foreign, 404, "not_found"); safeRefusal(guest, 401, "unauthorized");
        check(isDeepStrictEqual(await detail(ownerContext, target), targetBefore), "Refused requests preserve exact target detail");
        const rows = await list(ownerContext, [target, ownKeeper], [foreignKeeper]);
        await list(otherContext, [foreignKeeper], [target, ownKeeper]);
        const { card, dialog } = await openTarget(owner, rows, target);
        await dialog.getByRole("button", { name: T("en", "common.cancel"), exact: true }).click();
        await expect(dialog).toHaveCount(0); await expect(card).toContainText(roles[0]);
        check(ownerCounters.deletes === 0 && ownerCounters.mutations === 0, "Cancel issues no destructive or other mutation request");
        check(isDeepStrictEqual(await detail(ownerContext, target), targetBefore) && modelObservations() === beforeModel, "Refusal and cancel preserve target and model execution");
        noErrors(ownerCounters); noErrors(otherCounters);
        facts("refuse", { foreign_status: 404, anonymous_status: 401, cancel_zero_delete: true, selected_identity: true, warning_visible: true, cancel_default_focus: true, foreign_refusal_safe: true });
      } else {
        const ownBefore = await detail(ownerContext, ownKeeper), foreignBefore = await detail(otherContext, foreignKeeper);
        const rows = await list(ownerContext, [target, ownKeeper], [foreignKeeper]);
        const { card, dialog } = await openTarget(owner, rows, target);
        const deleting = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/history/interviews/${target}` && response.request().method() === "DELETE");
        await dialog.getByRole("button", { name: T("en", "dataPrivacy.confirmDelete"), exact: true }).click();
        const deleted = await deleting;
        check(deleted.status() === 200 && isDeepStrictEqual(await deleted.json(), { deleted: true }), "Exact target owner UI deletion succeeds");
        await expect(dialog).toHaveCount(0); await expect(card).not.toContainText(roles[0]); await expect(card).toContainText(roles[1]);
        await expect(owner.getByTestId("dp-count-ints")).toHaveText("1");
        check(ownerCounters.deletes === 1 && ownerCounters.mutations === 1, "Exactly one destructive UI request and no unrelated mutation");
        await list(ownerContext, [ownKeeper], [target, foreignKeeper]); await list(otherContext, [foreignKeeper], [target, ownKeeper]);
        for (const [path, method, status, code] of [
          [`/history/interviews/${target}`, "GET", 404, "not_found"],
          [`/history/interviews/${target}`, "DELETE", 404, "not_found"],
          [`/interviews/${source}`, "GET", 422, "validation_error"],
          [`/interviews/${source}/report`, "GET", 422, "validation_error"],
          [`/interviews/${source}/report`, "POST", 422, "validation_error"],
        ] as const) safeRefusal(await call(ownerContext, path, method, method === "POST" ? {} : undefined), status, code);
        check(isDeepStrictEqual(await detail(ownerContext, ownKeeper), ownBefore) && isDeepStrictEqual(await detail(otherContext, foreignKeeper), foreignBefore), "Both sentinels remain exactly unchanged");
        await owner.reload(); await expect(owner.getByTestId("dp-manage-interviews")).not.toContainText(roles[0]);
        await expect(owner.getByTestId("dp-manage-interviews")).toContainText(roles[1]); await expect(owner.getByTestId("dp-count-ints")).toHaveText("1");
        await retainedUI(owner, ownKeeper, target);
        const freshContext = await isolated(browser);
        try {
          const fresh = await freshContext.newPage(); await login(fresh, freshContext, accounts.owner.email);
          const freshCounters = observe(fresh);
          await fresh.goto("/account/data");
          await expect(fresh.getByTestId("dp-manage-interviews")).toContainText(roles[1]);
          await expect(fresh.getByTestId("dp-manage-interviews")).not.toContainText(roles[0]);
          await expect(fresh.getByTestId("dp-count-ints")).toHaveText("1");
          await list(freshContext, [ownKeeper], [target, foreignKeeper]);
          safeRefusal(await call(freshContext, `/history/interviews/${target}`), 404, "not_found");
          safeRefusal(await call(freshContext, `/interviews/${source}`), 422, "validation_error");
          await retainedUI(fresh, ownKeeper, target);
          check(freshCounters.mutations === 0 && freshCounters.deletes === 0, "Fresh-session retrieval remains read-only"); noErrors(freshCounters);
        } finally { await freshContext.close(); }
        check(modelObservations() === beforeModel, "Deletion, stale identifiers and fresh reads never replay the model");
        check(ownerCounters.deletes === 1 && ownerCounters.mutations === 1 && otherCounters.mutations === 0, "No late or duplicate browser mutation");
        noErrors(ownerCounters); noErrors(otherCounters);
        facts("delete", { owner_status: 200, delete_requests: 1, target_removed: true, owner_keeper_preserved: true, foreign_keeper_preserved: true, history_missing: 404, repeat_delete: 404, source_read: 422, source_report: 422, fresh_auth_absent: true, no_model_replay: true, foreign_refusal_safe: true, console_errors: 0, page_errors: 0 });
      }
    }
  } finally { await ownerContext.close(); await otherContext.close(); await anonymous.close(); }
});
