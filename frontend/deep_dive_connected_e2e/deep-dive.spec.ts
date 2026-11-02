import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { T, hydrated } from "../e2e/journey/definition";
import fixtures from "../e2e/journey/fixtures.json";
import { refusal } from "../history_identity_connected_e2e/assertions";
import type { EvaluationOut, InterviewStateResponse, ReportResponse } from "../lib/api/types";

// Only the model boundary is scripted. Browser requests and authentication use the real application.
const api = process.env.STORY_API_URL!, state = process.env.DEEP_DIVE_STATE_DIR!;
const accounts = JSON.parse(readFileSync(process.env.STORY_ACCOUNTS_FILE!, "utf8")) as Record<string, { id: number; email: string }>;
const password = "Synthetic-Story-Test-Password-42";
const role = "Synthetic Deep Dive Owner Role";
const mainAnswer = "Synthetic main answer with distinct detail";
const branchAnswer = "Synthetic deep dive answer with distinct detail";
const branchQuestion = "Which synthetic decision trade-off did you make?";
const mode = "deepen_reasoning";
const branchEvaluation = { ...fixtures.interview.evaluation, overall_score: 81, strengths: ["Synthetic branch reasoning made explicit"] };

interface PrivateIdentity { session_id: string; history_id: number; branch_id: string; parent_question_id: number }
interface HistoryQuestion {
  position: number; canonical_question: string; is_deep_dive: boolean; parent_position: number | null;
  answer: { text: string; evaluation: EvaluationOut } | null;
}
interface HistoryRecord {
  id: number; configuration: { target_role: string }; questions: HistoryQuestion[];
  report: { report: Record<string, unknown> };
}
function check(value: unknown, label: string): asserts value { if (!value) throw new Error(label); }
function same(a: unknown, b: unknown) { return isDeepStrictEqual(a, b); }
function modelCalls() { return readFileSync(join(state, "model-stages.jsonl"), "utf8").split("\n").filter(Boolean).length; }
function facts(name: string, value: Record<string, boolean | number>) {
  const encoded = JSON.stringify(value);
  check(Buffer.byteLength(encoded) <= 2048, "Bounded facts retention");
  writeFileSync(join(state, name), encoded, { mode: 0o600 });
}
async function isolated(browser: Browser) {
  const context = await browser.newContext();
  await context.route("**/*", route => ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname)
    ? route.continue() : route.abort("blockedbyclient"));
  return context;
}
async function call<T = Record<string, unknown>>(context: BrowserContext, path: string, method = "GET", body?: object) {
  // APIRequestContext shares the actual HttpOnly session without emitting expected refusal console errors.
  const response = await context.request.fetch(api + path, { method, data: body });
  return { status: response.status(), json: await response.json() as T };
}
async function login(page: Page, context: BrowserContext, email: string) {
  await page.goto("/sign-in");
  await hydrated(page, "#email");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect.poll(async () => (await call(context, "/auth/me")).status).toBe(200);
}
function observed(page: Page) {
  const counters = { console_errors: 0, page_errors: 0, navigations: 0, mutations: 0, creations: 0, branch_starts: 0, branch_answers: 0, reports: 0 };
  page.on("console", message => { if (message.type() === "error") counters.console_errors++; });
  page.on("pageerror", () => counters.page_errors++);
  page.on("framenavigated", frame => { if (frame === page.mainFrame()) counters.navigations++; });
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET" && /^\/api\/v1\/(interviews|history)(\/|$)/.test(path)) counters.mutations++;
    if (request.method() === "POST") {
      if (path === "/api/v1/interviews") counters.creations++;
      if (/\/interviews\/[^/]+\/deep-dive$/.test(path)) counters.branch_starts++;
      if (/\/interviews\/[^/]+\/deep-dive\/answers$/.test(path)) counters.branch_answers++;
      if (/\/interviews\/[^/]+\/report$/.test(path)) counters.reports++;
    }
  });
  return counters;
}
function noErrors(counters: ReturnType<typeof observed>) {
  check(counters.console_errors === 0, "No unexpected browser console errors");
  check(counters.page_errors === 0, "No browser page errors");
}
function safeForeign(value: { status: number; json: Record<string, unknown> }, status: number, code: string) {
  check(refusal(value, status, code), "Exact bounded foreign refusal");
  const error = value.json.error as Record<string, unknown>;
  check(![mainAnswer, branchAnswer, branchQuestion, role, accounts.owner.email].some(canary => JSON.stringify(value.json).includes(canary)), "Foreign response excludes owner content");
  if (status === 422) check(error.message === "Unknown interview session.", "Indistinguishable unknown or foreign session");
}
function historyIdentity(value: HistoryRecord, identity: PrivateIdentity) {
  check(value.id === identity.history_id && value.configuration.target_role === role, "History record identity");
  check(value.questions.length === 2, "Exactly one main and one branch History question");
  const main = value.questions.filter(question => question.is_deep_dive === false);
  const branch = value.questions.filter(question => question.is_deep_dive === true);
  check(main.length === 1 && branch.length === 1, "Distinct main and Deep Dive History records");
  check(main[0].canonical_question === fixtures.interview.questions[0] && main[0].answer?.text === mainAnswer && same(main[0].answer.evaluation, fixtures.interview.evaluation), "Main History content and evaluation");
  check(branch[0].canonical_question === branchQuestion && branch[0].answer?.text === branchAnswer && same(branch[0].answer.evaluation, branchEvaluation), "Branch History content and evaluation");
  // parent_position names a persisted question position; do not normalize an incorrect relationship into a pass.
  check(branch[0].parent_position === main[0].position, "History branch parent linkage");
  check(Object.entries(fixtures.interview.report).every(([key, expected]) => same(value.report.report[key], expected)), "Persisted report identity");
}

test("owned Deep Dive returns to the original evaluation and remains linked in History", async ({ browser }) => {
  const ownerContext = await isolated(browser), foreignContext = await isolated(browser);
  try {
    const owner = await ownerContext.newPage(), foreign = await foreignContext.newPage();
    await login(owner, ownerContext, accounts.owner.email);
    await login(foreign, foreignContext, accounts.other.email);
    const errors = observed(owner), foreignErrors = observed(foreign);
    if (process.env.DEEP_DIVE_PHASE === "create") {
      await owner.goto("/practice");
      await hydrated(owner, "input[type=number]");
      await owner.getByPlaceholder(/Senior Product Manager/i).fill(role);
      await owner.getByPlaceholder(/fintech/i).fill("healthcare");
      await owner.getByRole("combobox", { name: "Career level" }).selectOption("senior");
      await owner.getByLabel("Number of questions").fill("1");
      const creation = owner.waitForResponse(response => new URL(response.url()).pathname === "/api/v1/interviews" && response.request().method() === "POST");
      await owner.getByRole("button", { name: "Start interview", exact: true }).click();
      const created = await creation;
      check(created.status() === 200, "Interview created through UI");
      const initial = await created.json() as InterviewStateResponse;
      check(typeof initial.session_id === "string" && !!initial.session_id && initial.current_question?.question_id === 1, "Initial main identity");
      const session = initial.session_id, parent = initial.current_question.question_id;
      await hydrated(owner, "#answer");
      const beforeRefusals = await call<InterviewStateResponse>(ownerContext, `/interviews/${session}`), callsBeforeRefusals = modelCalls();
      const preEvaluation = await call(ownerContext, `/interviews/${session}/deep-dive`, "POST", { mode });
      check(refusal(preEvaluation, 422, "invalid_transition"), "Deep Dive requires evaluated main answer");
      const foreignActive = await call(foreignContext, `/interviews/${session}`);
      const foreignBranch = await call(foreignContext, `/interviews/${session}/deep-dive`, "POST", { mode });
      safeForeign(foreignActive, 422, "validation_error"); safeForeign(foreignBranch, 422, "validation_error");
      const afterRefusals = await call<InterviewStateResponse>(ownerContext, `/interviews/${session}`);
      check(beforeRefusals.status === 200 && afterRefusals.status === 200 && same(beforeRefusals.json, afterRefusals.json) && modelCalls() === callsBeforeRefusals, "Refusals preserve owner state and make no model call");

      await owner.locator("#answer").fill(mainAnswer);
      const answer = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/interviews/${session}/answers` && response.request().method() === "POST");
      await owner.getByRole("button", { name: T("en", "practice.submitAnswer"), exact: true }).click();
      const answered = await answer; check(answered.status() === 200, "Main answer accepted through UI");
      const evaluated = await answered.json() as InterviewStateResponse;
      check(same(evaluated.last_evaluation, fixtures.interview.evaluation), "Original main evaluation identity");
      await expect(owner.getByRole("heading", { name: "Answer feedback", exact: true })).toBeVisible();
      await expect(owner.getByText(T("en", "practice.questionProgress", { current: 1, total: 1 }), { exact: true })).toBeVisible();
      await owner.locator("#dd-mode").selectOption(mode);
      const start = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/interviews/${session}/deep-dive` && response.request().method() === "POST");
      await owner.getByRole("button", { name: /^Go deeper$/ }).click();
      const started = await start; check(started.status() === 200, "Deep Dive started through UI");
      const branched = await started.json() as InterviewStateResponse, branch = branched.deep_dive?.current_branch_question;
      check(branched.deep_dive?.active && branched.question_number === 1 && branched.questions_planned === 1 && branch?.parent_question_id === parent && branch.question === branchQuestion && !!branch.branch_id && branch.depth === 1 && branch.branch_mode === mode, "Branch identity and unchanged main counter");
      await expect(owner.getByRole("heading", { name: branchQuestion, exact: true })).toBeVisible();
      const beforeForeignBranch = await call<InterviewStateResponse>(ownerContext, `/interviews/${session}`), callsBeforeForeignBranch = modelCalls();
      for (const [suffix, body] of [["", { mode }], ["/answers", { answer: branchAnswer }], ["/next", {}], ["/return", {}]] as const) {
        const denied = await call(foreignContext, `/interviews/${session}/deep-dive${suffix}`, "POST", body);
        const unknown = await call(foreignContext, `/interviews/synthetic-missing-session/deep-dive${suffix}`, "POST", body);
        safeForeign(denied, 422, "validation_error"); safeForeign(unknown, 422, "validation_error");
      }
      const afterForeignBranch = await call<InterviewStateResponse>(ownerContext, `/interviews/${session}`);
      check(beforeForeignBranch.status === 200 && afterForeignBranch.status === 200 && same(beforeForeignBranch.json, afterForeignBranch.json) && modelCalls() === callsBeforeForeignBranch, "All foreign branch operations preserve owner state without model calls");
      await owner.getByLabel("Your answer", { exact: true }).fill(branchAnswer);
      const evaluation = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/interviews/${session}/deep-dive/answers` && response.request().method() === "POST");
      await owner.getByRole("button", { name: /Submit deep-dive answer/i }).click();
      const branchResponse = await evaluation; check(branchResponse.status() === 200, "Branch answer accepted through UI");
      const branchEvaluated = await branchResponse.json() as InterviewStateResponse;
      check(same(branchEvaluated.last_evaluation, branchEvaluation) && !same(branchEvaluated.last_evaluation, evaluated.last_evaluation) && branchEvaluated.deep_dive?.active && branchEvaluated.question_number === 1 && branchEvaluated.questions_planned === 1, "Distinct branch feedback and unchanged main counter");
      await expect(owner.getByRole("heading", { name: "Deep-dive feedback", exact: true })).toBeVisible();
      await expect(owner.getByText(T("en", "practice.questionProgress", { current: 1, total: 1 }), { exact: true })).toBeVisible();
      const navigationCount = errors.navigations;
      const returnedResponse = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/interviews/${session}/deep-dive/return` && response.request().method() === "POST");
      await owner.getByRole("button", { name: /Return to interview/i }).click();
      const returned = await returnedResponse; check(returned.status() === 200, "Return accepted through UI");
      const restored = await returned.json() as InterviewStateResponse;
      check(restored.deep_dive === null && restored.state === "INTERVIEW_IN_PROGRESS" && restored.question_number === 1 && same(restored.last_evaluation, evaluated.last_evaluation), "Return restores original main evaluation");
      await expect(owner.getByRole("heading", { name: "Answer feedback", exact: true })).toBeVisible();
      await expect(owner.getByRole("button", { name: T("en", "practice.nextQuestion"), exact: true })).toBeEnabled();
      await expect(owner.getByRole("button", { name: /End interview/i })).toBeVisible();
      check(errors.navigations === navigationCount, "Main feedback restored without document navigation or reload");
      const completion = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/interviews/${session}/next-question` && response.request().method() === "POST");
      await owner.getByRole("button", { name: T("en", "practice.nextQuestion"), exact: true }).click();
      check((await completion).status() === 200, "Main interview completed through UI");
      await expect(owner.getByRole("heading", { name: T("en", "practice.interviewComplete"), exact: true })).toBeVisible();
      const saving = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/interviews/${session}/report` && response.request().method() === "POST");
      await owner.getByRole("button", { name: T("en", "practice.generateReport"), exact: true }).click();
      const saved = await saving; check(saved.status() === 200, "Report generated through UI");
      const report = await saved.json() as ReportResponse;
      check(report.save_failed === false && Number.isInteger(report.saved_report_id) && Number(report.saved_report_id) > 0, "Report saved once");
      await expect(owner.getByText(fixtures.interview.report.performance_summary, { exact: true })).toBeVisible();
      check(errors.creations === 1 && errors.branch_starts === 1 && errors.branch_answers === 1 && errors.reports === 1, "Exactly one UI interview, branch, branch answer and report request");
      noErrors(errors); noErrors(foreignErrors);
      writeFileSync(join(state, "deep-dive-private.json"), JSON.stringify({ session_id: session, history_id: report.saved_report_id, branch_id: branch.branch_id, parent_question_id: parent }), { mode: 0o600 });
      facts("create-facts.json", { main_answer: true, branch_question: true, branch_evaluation: true, return_without_reload: true, original_evaluation: true, main_counter_unchanged: true, report_saved: true, pre_evaluation: 422, foreign_active: 422, foreign_deep_dive: 422, foreign_refusal_safe: true, foreign_state_unchanged: true, console_errors: 0, page_errors: 0 });
    } else {
      const identity = JSON.parse(readFileSync(join(state, "deep-dive-private.json"), "utf8")) as PrivateIdentity;
      const callsBeforeRead = modelCalls();
      await owner.goto("/history");
      const link = owner.locator(`a[href='/history/${identity.history_id}']`);
      await expect(link).toHaveCount(1); await expect(link).toContainText(role);
      const opening = owner.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/history/interviews/${identity.history_id}`);
      await link.click();
      const opened = await opening; check(opened.status() === 200, "Real History link reads owned report");
      await expect(owner).toHaveURL(new RegExp(`/history/${identity.history_id}$`));
      await expect(owner.getByText(fixtures.interview.report.performance_summary, { exact: true })).toBeVisible();
      historyIdentity((await opened.json()).interview as HistoryRecord, identity);
      const foreignHistory = await call(foreignContext, `/history/interviews/${identity.history_id}`);
      safeForeign(foreignHistory, 404, "not_found");
      await owner.reload();
      await expect(owner.getByText(fixtures.interview.report.performance_summary, { exact: true })).toBeVisible();
      const freshContext = await isolated(browser);
      try {
        const fresh = await freshContext.newPage();
        await login(fresh, freshContext, accounts.owner.email);
        const freshErrors = observed(fresh);
        await fresh.goto(`/history/${identity.history_id}`);
        await expect(fresh.getByText(fixtures.interview.report.performance_summary, { exact: true })).toBeVisible();
        const detail = await call<{ interview: HistoryRecord }>(freshContext, `/history/interviews/${identity.history_id}`);
        check(detail.status === 200, "Fresh authenticated History retrieval"); historyIdentity(detail.json.interview, identity);
        check(freshErrors.mutations === 0, "Fresh session read-only retrieval"); noErrors(freshErrors);
      } finally { await freshContext.close(); }
      check(errors.mutations === 0 && foreignErrors.mutations === 0 && modelCalls() === callsBeforeRead, "History read phase has no interview mutation or model replay");
      noErrors(errors); noErrors(foreignErrors);
      facts("read-facts.json", { branch_parent_link: true, branch_identity: true, fresh_auth: true, read_only: true, foreign_refusal_safe: true, foreign_history: 404, console_errors: 0, page_errors: 0 });
    }
  } finally { await ownerContext.close(); await foreignContext.close(); }
});
