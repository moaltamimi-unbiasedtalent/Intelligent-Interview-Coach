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

test("explicit story selection and consent reach the offline model without other owners' context", async ({ browser }) => {
  const owner = await context(browser), other = await context(browser);
  try {
    const a = await owner.newPage(), b = await other.newPage();
    await login(a, accounts.owner.email); await login(b, accounts.other.email);
    const makeStory = (page: Page, title: string, marker: string) => request(page, "/stories", "POST", { title, situation: marker, status: "user_created" });
    const selected = await makeStory(a, "Selected synthetic story", markers[0]);
    const unselected = await makeStory(a, "Unselected synthetic story", markers[1]);
    const foreign = await makeStory(b, "Foreign synthetic story", markers[2]);
    expect([selected.status, unselected.status, foreign.status]).toEqual([201, 201, 201]);
    const sid = selected.json.id as number, uid = unselected.json.id as number, fid = foreign.json.id as number;
    const cfg = { target_role: "Registered Nurse", industry_or_sector: "healthcare", career_level: "senior", number_of_questions: 2 };
    const baseline = await request(a, "/interviews"); expect(baseline.status).toBe(200); expect(baseline.json.sessions).toHaveLength(0);
    const observer = join(dirname(file), "observer.jsonl");
    expect((await request(a, "/interviews")).json.sessions).toHaveLength(0);
    for (const id of [sid, uid]) expect((await request(a, `/stories/${id}`)).json.use_count).toBe(0);
    expect((await request(b, `/stories/${fid}`)).json.use_count).toBe(0);
    expect(existsSync(observer)).toBe(false);
    await a.goto("/practice");
    await a.getByPlaceholder(/Senior Product Manager/i).fill("Registered Nurse");
    await a.getByPlaceholder(/fintech/i).fill("healthcare");
    await a.getByRole("combobox", { name: "Career level" }).selectOption("senior");
    await expect(a.getByRole("checkbox", { name: /Selected synthetic story/ })).toBeVisible();
    await expect(a.getByText("Foreign synthetic story")).toHaveCount(0);
    await a.getByRole("checkbox", { name: /Selected synthetic story/ }).check();
    await expect(a.getByRole("checkbox", { name: /Unselected synthetic story/ })).not.toBeChecked();
    const start = a.getByRole("button", { name: "Start interview" });
    const consent = a.getByRole("checkbox", { name: /I understand that the stories I selected/i });
    await expect(consent).not.toBeChecked(); await expect(start).toBeDisabled();
    let posts = 0;
    a.on("request", r => { if (r.method() === "POST" && new URL(r.url()).pathname === "/api/v1/interviews") posts++; });
    expect(posts).toBe(0);
    await consent.check(); await expect(start).toBeEnabled();
    const created = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/interviews" && r.request().method() === "POST");
    await start.click(); const response = await created; expect(response.status()).toBe(200);
    const payload = response.request().postDataJSON();
    expect(payload.configuration.story_ids).toEqual([sid]); expect(payload.configuration.confirm_story_use).toBe(true);
    expect(payload.configuration.use_candidate_evidence ?? false).toBe(false);
    expect(payload.configuration.job_description_document_id ?? null).toBeNull();
    expect(payload.configuration.candidate_background ?? "").toBe("");
    expect(payload.configuration.job_description ?? "").toBe("");
    expect(payload.configuration.target_role).toBe(cfg.target_role); expect(payload.configuration.industry_or_sector).toBe(cfg.industry_or_sector);
    for (const marker of [...markers, "Selected synthetic story", "Unselected synthetic story", "Foreign synthetic story"]) expect(JSON.stringify(payload)).not.toContain(marker);
    const session = (await response.json()).session_id as string;
    expect(session).toBeTruthy(); expect(posts).toBe(1);
    await expect(a).toHaveURL(/\/practice\?session=/);
    await expect(a.getByRole("heading", { level: 1, name: fixtures.interview.questions[0] })).toBeVisible();
    const question = fixtures.interview.questions[0], answer = fixtures.interview.answer;
    for (const marker of [...markers, "[[STORY"]) {
      expect(question).not.toContain(marker); expect(answer).not.toContain(marker);
    }
    const evaluationCount = () => readFileSync(observer, "utf8").trim().split("\n").map(x => JSON.parse(x)).filter(x => x.stage === "AnswerEvaluation").length;
    expect(evaluationCount()).toBe(0);
    let answerPosts = 0;
    a.on("request", r => { if (r.method() === "POST" && new URL(r.url()).pathname === `/api/v1/interviews/${session}/answers`) answerPosts++; });
    await a.locator("#answer").fill(answer);
    const submitted = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/interviews/${session}/answers` && r.request().method() === "POST");
    await a.getByRole("button", { name: "Submit answer" }).click();
    const answerResponse = await submitted; expect(answerResponse.status()).toBe(200);
    expect(answerResponse.request().postDataJSON()).toEqual({ answer });
    const feedback = (await answerResponse.json()).last_evaluation;
    expect(feedback).toMatchObject(fixtures.interview.evaluation);
    await expect(a.getByTestId("answer-score-value")).toContainText(String(feedback.overall_score));
    await expect(a.getByTestId("rubric-scores").locator("[data-dimension]")).toHaveCount(7);
    await expect(a.getByText(feedback.strengths[0], { exact: true })).toBeVisible();
    expect(answerPosts).toBe(1);
    expect(evaluationCount()).toBe(1);
    const ownerSession = await request(a, `/interviews/${session}`); expect(ownerSession.status).toBe(200);
    expect(ownerSession.json.last_evaluation).toMatchObject(feedback);
    const foreignSession = await request(b, `/interviews/${session}`);
    const missingSession = await request(b, "/interviews/synthetic-unknown-session");
    expect(foreignSession.status).toBe(422); expect(missingSession.status).toBe(422);
    expect(foreignSession.json.error.code).toBe(missingSession.json.error.code);
    expect(foreignSession.json.error.message).toBe(missingSession.json.error.message);
    expect((await request(a, `/stories/${sid}`)).json).toMatchObject({ use_count: 1, status: "user_created", verification: "unverified" });
    expect((await request(a, `/stories/${uid}`)).json.use_count).toBe(0);
    expect((await request(b, `/stories/${fid}`)).json.use_count).toBe(0);
    const foreignAnswer = await request(b, `/interviews/${session}/answers`, "POST", { answer });
    const missingAnswer = await request(b, "/interviews/synthetic-unknown-session/answers", "POST", { answer });
    expect(foreignAnswer.status).toBe(missingAnswer.status); expect(foreignAnswer.json.error.code).toBe(missingAnswer.json.error.code);
    expect(foreignAnswer.json.error.message).toBe(missingAnswer.json.error.message);
    for (const sensitive of [...markers, "Selected synthetic story", fixtures.interview.evaluation.strengths[0]]) {
      expect(JSON.stringify([foreignSession.json, foreignAnswer.json])).not.toContain(sensitive);
    }
    expect(evaluationCount()).toBe(1);
    await a.reload();
    await expect(a.getByTestId("answer-score-value")).toContainText(String(feedback.overall_score));
    expect((await request(a, `/interviews/${session}`)).json.last_evaluation).toMatchObject(feedback);
    expect(answerPosts).toBe(1); expect(evaluationCount()).toBe(1);
    expect((await request(a, `/stories/${sid}`)).json.use_count).toBe(1);
    expect((await request(a, "/interviews")).json.sessions).toHaveLength(1);
    expect((await request(b, `/stories/${sid}`)).status).toBe(404);
  } finally { await owner.close(); await other.close(); }
});
