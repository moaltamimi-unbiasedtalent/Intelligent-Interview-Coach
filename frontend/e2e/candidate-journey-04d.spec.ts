import { expect, test } from "@playwright/test";

import { hydrated, runJourney, T } from "./journey/definition";
import { MockWorld } from "./journey/mockWorld";
import { FIXTURES, MODE, MODE_LABEL, VARIANT, languagesToRun, makeEnv } from "./journey/env";

/**
 * 04D (REQ-CAND-01, DEMO-02, PG-06): the real-browser Candidate journey, once per selectable language, from ONE definition (./journey/definition.ts).
 *
 *   mocked (default, always on in CI):  E2E_PORT=3132 npx playwright test e2e/candidate-journey-04d.spec.ts
 *   real local stack:                   python scripts/e2e/journey_stack.py run          (offline fixtures, unique ports, temporary database)
 *   real hosted staging (NOT RUN):      see the docs at the top of scripts/e2e/journey_stack.py
 *
 * Evidence label for every result: MOCKED NETWORK or REAL STACK. Neither is live-model qualification.
 */

test.describe.configure({ mode: "serial" });

const languages = languagesToRun();

for (const [index, locale] of languages.entries()) {
  test(`candidate journey [${MODE_LABEL}] [${locale}]`, async ({ page, baseURL }) => {
    test.skip(VARIANT !== "healthy", `variant ${VARIANT} is covered by candidate-provider-04d.spec.ts`);
    test.setTimeout(MODE === "real" ? 180_000 : 90_000);
    test.info().annotations.push({ type: "evidence", description: MODE_LABEL });
    const env = makeEnv(locale, index);
    const world = new MockWorld();
    if (MODE === "mocked") await world.install(page);

    const result = await runJourney(page, env, baseURL ?? "http://localhost:3000");

    expect(result.opportunityId).toBeGreaterThan(0);
    expect(result.interviewStartRequests).toBe(1);
    if (MODE === "mocked") {
      // The mock served the journey; anything it had to answer with `{}` is UI drift to look at, so it is listed in the report rather than hidden.
      test.info().annotations.push({ type: "unmodelled-api-calls", description: [...new Set(world.unmocked)].join(", ") || "none" });
      expect(world.consumedInvitations.size).toBe(1);                       // the invitation was single use and consumed by exactly this registration
    }
  });
}

// The suite must not be vacuous: with Start Interview failing like the original defect, the very same journey has to fail at exactly that step.
if (MODE === "mocked") {
  test("self-check: the journey fails at START INTERVIEW when interview creation is unavailable", async ({ page, baseURL }) => {
    test.setTimeout(120_000);
    const world = new MockWorld();
    world.failInterviewCreate = true;
    await world.install(page);
    await expect(runJourney(page, makeEnv("en", 99), baseURL ?? "http://localhost:3000")).rejects.toThrow();
    expect(world.calls).toContain("POST /interviews");
    expect(world.calls.some((c) => c.endsWith("/answers"))).toBe(false);
  });
}

if (MODE === "real" && process.env.JOURNEY_LINKED_HANDOFF === "1") {
  test("keeps the selected Opportunity through a reloaded Mo handoff, Practice and History", async ({ page, baseURL }) => {
    test.skip(VARIANT !== "healthy", "the linked handoff uses the healthy offline fixtures");
    test.setTimeout(180_000);
    const env = makeEnv("en", languages.length);
    env.email = `handoff-${env.email}`;
    const web = baseURL ?? "http://localhost:3000";
    const api = process.env.JOURNEY_API_URL;
    if (!api) throw new Error("The isolated journey API URL is required.");
    const result = await runJourney(page, env, web, { stopAfter: "opportunity" });
    const selected = result.opportunityId;
    const other = await page.request.post(`${api}/opportunities`, {
      data: { target_role: "Unselected fixture role" }, headers: { Origin: web },
    });
    expect(other.status()).toBe(201);
    const otherId = (await other.json()).id;

    await page.goto(`/prepare?opportunity=${selected}`);
    await hydrated(page, "#agent-goal");
    await expect(page.locator("#agent-role")).toHaveValue(FIXTURES.opportunity.role);
    await page.locator("#agent-goal").fill("Prepare the offline linked Practice fixture.");
    await page.getByRole("button", { name: T("en", "prepare.startPreparing") }).click();
    await expect(page).toHaveURL(/\/prepare\?run=/);
    const runId = new URL(page.url()).searchParams.get("run");
    expect(runId).toBeTruthy();
    await expect(page.getByRole("button", { name: T("en", "prepare.startPractice") })).toBeVisible();
    await page.goto(`/prepare?run=${runId}&opportunity=${otherId}`);
    await page.reload();
    await page.getByRole("button", { name: T("en", "prepare.startPractice") }).click();
    await page.getByLabel(T("en", "prepare.industrySector")).fill(FIXTURES.interview.industry);
    await page.getByRole("combobox", { name: T("en", "prepare.careerLevel") }).selectOption("senior");
    const [created] = await Promise.all([
      page.waitForResponse((response) => response.url() === `${api}/interviews` && response.request().method() === "POST" && response.ok()),
      page.getByRole("button", { name: T("en", "prepare.startPractice") }).click(),
    ]);
    expect(created.request().postDataJSON().opportunity_id).toBe(selected);
    const key = created.request().headers()["idempotency-key"];
    expect(key).toBe(`agent-handoff:${runId}`);
    const sid = (await created.json()).session_id;
    const retry = await page.request.post(`${api}/interviews`, {
      data: created.request().postDataJSON(), headers: { Origin: web, "Idempotency-Key": key },
    });
    expect(retry.ok()).toBe(true);
    expect((await retry.json()).session_id).toBe(sid);

    await expect(page).toHaveURL(new RegExp(`/practice\\?session=${sid}&from=coach$`));
    const [reopened] = await Promise.all([
      page.waitForResponse((response) => response.url() === `${api}/interviews` && response.request().method() === "POST"),
      page.goto(`/prepare?run=${runId}&opportunity=${otherId}`),
    ]);
    expect(reopened.ok()).toBe(true);
    expect((await reopened.json()).session_id).toBe(sid);
    expect(reopened.request().postDataJSON()).toMatchObject({ opportunity_id: selected });
    expect(reopened.request().postDataJSON()).not.toHaveProperty("career_level");
    expect(reopened.request().postDataJSON()).not.toHaveProperty("industry_or_sector");
    await expect(page).toHaveURL(new RegExp(`/practice\\?session=${sid}&from=coach$`));
    await hydrated(page, "#answer");
    await page.locator("#answer").fill(FIXTURES.interview.answer);
    await page.getByRole("button", { name: T("en", "practice.submitAnswer") }).click();
    await expect(page.getByTestId("answer-score-value")).toBeVisible();
    await page.getByRole("button", { name: T("en", "practice.endInterview") }).click();
    await page.getByRole("button", { name: T("en", "practice.endYes") }).click();
    const [report] = await Promise.all([
      page.waitForResponse((response) => response.url() === `${api}/interviews/${sid}/report` && response.request().method() === "POST" && response.ok()),
      page.getByRole("button", { name: T("en", "practice.generateReport") }).click(),
    ]);
    const reportId = (await report.json()).saved_report_id;
    expect(reportId).toBeGreaterThan(0);
    const selectedOverview = await page.request.get(`${api}/opportunities/${selected}`);
    const otherOverview = await page.request.get(`${api}/opportunities/${otherId}`);
    expect((await selectedOverview.json()).interview_ids).toEqual([reportId]);
    expect((await otherOverview.json()).interview_ids).toEqual([]);
    await page.goto("/history");
    await page.locator(`a[href="/history/${reportId}"]`).click();
    await expect(page.getByText(FIXTURES.interview.report.performance_summary)).toBeVisible();
    await page.goto("/progress");
    await expect(page.getByText(T("en", "progress.practiceSessions"), { exact: true }).locator("..")).toContainText("1");
  });
}
