import { expect, test, type Page } from "@playwright/test";

import { translate } from "../../lib/i18n/catalog";
import { EXPECTED_AI_MODE, FIXTURES, type JourneyEnv } from "./env";

/**
 * THE Candidate journey (04D, REQ-CAND-01): ONE definition, run by the spec in two modes (mocked network, real stack) and once per language.
 *
 *   register (WITH a valid invitation, hosted-like) -> sign in -> onboarding -> Opportunity -> reload persistence -> Prepare with Mo
 *   -> START INTERVIEW (the owner-named regression) -> answer -> evaluation -> next question -> complete -> report -> History -> Progress
 *
 * Selectors are language independent (ids, test ids, placeholders and labels resolved through the catalogue for the run's locale), and every step is a named
 * `test.step`, so a failure names the exact step and the language. Nothing here knows which mode it runs in, except the optional hooks the caller passes.
 */

export const T = (locale: string, key: string, vars?: Record<string, string | number>) => translate(locale as never, key, vars);

/** React has attached its handlers to this element: a deterministic hydration gate (never a sleep, never network idleness). */
export async function hydrated(page: Page, selector: string): Promise<void> {
  await page.waitForFunction((target) => {
    const el = document.querySelector(target);
    return !!el && Object.keys(el).some((k) => k.startsWith("__reactProps$"));
  }, selector, { timeout: 20_000 });
}

export interface JourneyRecord {
  step: string;
  ok: boolean;
}

export interface JourneyResult {
  opportunityId: number;
  sessionId: string;
  interviewStartRequests: number;
  records: JourneyRecord[];
}

/** Console errors and uncaught page errors recorded for the whole journey: an uncaught exception is a failure even when the visible text looked right. */
export function watchPage(page: Page) {
  const pageErrors: string[] = [];
  const posts: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  page.on("request", (r) => { if (r.method() === "POST") posts.push(new URL(r.url()).pathname.replace(/^.*\/api\/v1/, "")); });
  return { pageErrors, posts };
}

export async function setLocale(page: Page, baseURL: string, locale: string): Promise<void> {
  await page.context().addCookies([{ name: "ask4mo_locale", value: locale, url: baseURL }]);
}

export async function registerWithInvitation(page: Page, env: JourneyEnv): Promise<void> {
  const L = env.locale;
  // Opening the invitation link is a fresh navigation (a new tab): from /register itself it would only change the hash and never re-run the page.
  await page.goto("about:blank");
  await page.goto(`/register#invitation=${encodeURIComponent(env.invitationCode)}`);
  await hydrated(page, "#email");
  // The invitation link prefills the code and removes it from the address bar.
  await expect(page.locator("#invitation")).toHaveValue(env.invitationCode);
  await expect.poll(() => new URL(page.url()).hash).toBe("");
  await page.locator("#name").fill(env.displayName);
  await page.locator("#email").fill(env.email);
  await page.locator("#password").fill(env.password);
  await page.getByRole("button", { name: T(L, "auth.createAccount") }).click();
  await expect(page.getByText(T(L, "auth.registerSent"))).toBeVisible();
}

export async function signIn(page: Page, env: JourneyEnv): Promise<void> {
  await page.goto("/sign-in");
  await hydrated(page, "#email");
  await page.locator("#email").fill(env.email);
  await page.locator("#password").fill(env.password);
  await page.getByRole("button", { name: T(env.locale, "common.signIn") }).click();
}

export async function startInterviewFromOpportunity(page: Page, env: JourneyEnv, opportunityId: number): Promise<void> {
  const L = env.locale;
  await page.goto(`/practice?opportunity=${opportunityId}`);
  await hydrated(page, "input[type=number]");
  // The Opportunity pre-populates the role (an initial value, never an override); the candidate completes the rest.
  await expect(page.getByPlaceholder(T(L, "practice.targetRolePlaceholder"))).toHaveValue(FIXTURES.opportunity.role);
  await page.getByPlaceholder(T(L, "practice.industryPlaceholder")).fill(FIXTURES.interview.industry);
  await page.getByRole("combobox", { name: T(L, "practice.careerLevel") }).selectOption("senior");
  await page.locator("input[type=number]").fill("2");
  await page.getByRole("button", { name: T(L, "practice.start") }).click();
}

/** Runs the whole journey. Returns what a caller may want to assert on afterwards. */
export interface JourneyOptions {
  /** Stop after the Opportunity has been created and its persistence checked (the provider-failure specs continue from there with their own steps). */
  stopAfter?: "opportunity";
}

export async function runJourney(page: Page, env: JourneyEnv, baseURL: string, options: JourneyOptions = {}): Promise<JourneyResult> {
  const L = env.locale;
  const { pageErrors, posts } = watchPage(page);
  const records: JourneyRecord[] = [];
  const step = async (name: string, body: () => Promise<void>) => {
    await test.step(`[${env.mode}/${env.locale}] ${name}`, async () => { await body(); });
    records.push({ step: name, ok: true });
  };
  let opportunityId = 0;
  let sessionId = "";

  await setLocale(page, baseURL, L);

  if (env.probeUninvited) {
    await step("registration without an invitation is refused with one calm, localized message", async () => {
      await page.goto("/register");
      await hydrated(page, "#email");
      await expect(page.locator("#invitation")).toBeVisible();
      await page.locator("#email").fill(`uninvited-${env.email}`);
      await page.locator("#password").fill(env.password);
      await page.getByRole("button", { name: T(L, "auth.createAccount") }).click();
      await expect(page.getByRole("alert").filter({ hasText: T(L, "auth.invitationRequired") })).toBeVisible();
      await expect(page.getByText(T(L, "auth.registerSent"))).toHaveCount(0);
    });
  }

  await step("register with a valid invitation", () => registerWithInvitation(page, env));

  await step("sign in lands in onboarding (a new account is gated)", async () => {
    await signIn(page, env);
    await expect(page).toHaveURL(/\/onboarding$/);
  });

  await step("onboarding completes and offers the Welcome handoff", async () => {
    await hydrated(page, "main button, #main button");
    // Walk forward until the last step is showing (never a fixed number of clicks: a late account load or a remount may legitimately put the candidate on a different step, and the saved
    // step is what counts). Bounded, so a page that never advances still fails.
    const finish = page.getByRole("button", { name: T(L, "onboarding.finish") });
    const forward = page.getByRole("button", { name: T(L, "onboarding.getStarted") }).or(page.getByRole("button", { name: T(L, "onboarding.next"), exact: true }));
    for (let i = 0; i < 40 && !(await finish.isVisible()); i++) {
      await forward.first().click({ timeout: 3_000 }).catch(() => undefined);
    }
    await expect(finish).toBeVisible();
    await finish.click();
    await expect(page.getByRole("heading", { name: T(L, "onboarding.completeTitle") })).toBeVisible();
  });

  await step("create an Opportunity from the Welcome handoff", async () => {
    await page.getByRole("button", { name: T(L, "tutorial.welcomeCreate") }).click();
    await expect(page).toHaveURL(/\/opportunities\?create=1/);
    await page.getByPlaceholder(T(L, "opportunity.rolePlaceholder")).fill(FIXTURES.opportunity.role);
    await page.getByRole("button", { name: T(L, "opportunity.next") }).click();
    await page.getByPlaceholder(T(L, "opportunity.companyPlaceholder")).fill(FIXTURES.opportunity.company);
    await page.getByRole("button", { name: T(L, "opportunity.next") }).click();
    await page.getByRole("button", { name: T(L, "opportunity.next") }).click();
    await Promise.all([
      page.waitForResponse((r) => new URL(r.url()).pathname.endsWith("/opportunities") && r.request().method() === "POST"),
      page.getByRole("button", { name: T(L, "opportunity.createButton") }).click(),
    ]);
    const title = `${FIXTURES.opportunity.role} - ${FIXTURES.opportunity.company}`;
    await page.getByText(title).first().click();
    await expect(page).toHaveURL(/\/opportunities\/\d+$/);
    opportunityId = Number(new URL(page.url()).pathname.split("/").pop());
    expect(opportunityId).toBeGreaterThan(0);
  });

  await step("the Opportunity survives a reload and is listed again", async () => {
    const title = `${FIXTURES.opportunity.role} - ${FIXTURES.opportunity.company}`;
    await page.reload();
    await expect(page.getByText(title).first()).toBeVisible();
    await page.goto("/opportunities");
    await expect(page.getByText(title).first()).toBeVisible();
  });

  if (options.stopAfter === "opportunity") {
    expect(pageErrors, "uncaught page errors during the journey").toEqual([]);
    return { opportunityId, sessionId, interviewStartRequests: posts.filter((p) => p === "/interviews").length, records };
  }

  await step("Prepare with Mo returns an answer", async () => {
    await page.goto(`/prepare?opportunity=${opportunityId}`);
    await hydrated(page, "#agent-goal");
    await page.locator("#agent-goal").fill(FIXTURES.mo.goal);
    await page.getByRole("button", { name: T(L, "prepare.startPreparing") }).click();
    await expect(page.getByText(FIXTURES.mo.reply)).toBeVisible();
  });

  await step("the AI mode is shown and the run list holds only this candidate's own run", async () => {
    await page.goto("/prepare");
    await hydrated(page, "#agent-goal");
    // Both modes use offline fixtures unless the stack says otherwise: the stack must SAY so (a keyless or offline stack can never look live).
    await expect(page.getByTestId("ai-provider-mode")).toHaveAttribute("data-mode", EXPECTED_AI_MODE);
    await expect(page.getByTestId("ai-provider-mode")).toContainText(T(L, EXPECTED_AI_MODE === "live" ? "providerMode.live" : "providerMode.offline"));
    // Each language is a different candidate on the same stack: only the run just made may be listed (owner scoping, seen through the real UI).
    await expect(page.getByTestId("recent-run")).toHaveCount(1);
    await expect(page.getByTestId("recent-run").first()).toContainText(T(L, "recentRuns.stateReady"));
  });

  await step("START INTERVIEW creates exactly one session and shows the first question", async () => {
    const before = posts.filter((p) => p === "/interviews").length;
    await startInterviewFromOpportunity(page, env, opportunityId);
    await expect(page).toHaveURL(/\/practice\?session=/);
    sessionId = new URL(page.url()).searchParams.get("session") ?? "";
    expect(sessionId).not.toBe("");
    await expect(page.getByRole("heading", { level: 1, name: FIXTURES.interview.questions[0] })).toBeVisible();
    // No silent duplicate: one click produced one create request.
    expect(posts.filter((p) => p === "/interviews").length - before).toBe(1);
  });

  await step("answering shows a labelled evaluation with the seven rubric dimensions", async () => {
    await hydrated(page, "#answer");
    await page.locator("#answer").fill(FIXTURES.interview.answer);
    await page.getByRole("button", { name: T(L, "practice.submitAnswer") }).click();
    await expect(page.getByTestId("answer-score-value")).toContainText(String(FIXTURES.interview.evaluation.overall_score));
    await expect(page.getByTestId("rubric-scores").locator("[data-dimension]")).toHaveCount(7);
  });

  await step("next question, second answer, then the interview completes", async () => {
    await page.getByRole("button", { name: T(L, "practice.nextQuestion") }).click();
    await expect(page.getByRole("heading", { level: 1, name: FIXTURES.interview.questions[1] })).toBeVisible();
    await page.locator("#answer").fill(FIXTURES.interview.answer);
    await page.getByRole("button", { name: T(L, "practice.submitAnswer") }).click();
    await expect(page.getByTestId("answer-score-value")).toBeVisible();
    await page.getByRole("button", { name: T(L, "practice.nextQuestion") }).click();
    await expect(page.getByRole("heading", { name: T(L, "practice.interviewComplete") })).toBeVisible();
  });

  await step("the performance review is generated", async () => {
    await page.getByRole("button", { name: T(L, "practice.generateReport") }).click();
    await expect(page.getByRole("heading", { name: T(L, "practice.reportTitle") })).toBeVisible();
    await expect(page.getByText(FIXTURES.interview.report.performance_summary)).toBeVisible();
  });

  await step("History lists the interview and opens its review", async () => {
    await page.goto("/history");
    const row = page.locator("a[href^='/history/']").filter({ hasText: FIXTURES.opportunity.role });
    await expect(row).toHaveCount(1);
    await row.click();
    await expect(page).toHaveURL(/\/history\/\d+$/);
    await expect(page.getByText(FIXTURES.interview.report.performance_summary)).toBeVisible();
  });

  await step("Progress counts the completed practice", async () => {
    await page.goto("/progress");
    await expect(page.getByText(T(L, "progress.practiceSessions"), { exact: true }).locator("..")).toContainText("1");
    await expect(page.getByText(T(L, "progress.answersEvaluated"), { exact: true }).locator("..")).toContainText("2");
  });

  expect(pageErrors, "uncaught page errors during the journey").toEqual([]);
  return { opportunityId, sessionId, interviewStartRequests: posts.filter((p) => p === "/interviews").length, records };
}
