import { expect, test, type Page } from "@playwright/test";

// Full Interview Practice browser flow with CONTROLLED responses mocked at the
// network layer (page.route). No backend, no paid provider calls. Covers the
// lifecycle (question → answer → feedback → Deep Dive → return → next → complete →
// report), refresh-restore, and standalone setup.

const SID = "sess_e2e";

const OPTIONS = {
  career_levels: ["junior", "mid", "senior"],
  interview_types: ["behavioural"],
  deep_dive_modes: ["deepen_reasoning", "challenge_assumptions"],
};

const EVAL = {
  overall_score: 74, relevance: 7, structure: 7, evidence: 7, role_knowledge: 7,
  problem_solving: 7, communication: 7, credibility: 7,
  strengths: ["Clear structure"], improvement_areas: ["Add metrics"], missing_evidence: [],
  stronger_answer_structure: "Use STAR-plus-learning.", improved_example_answer: "", follow_up_question: "What did you learn?",
};

function question(id: number) {
  return { question_id: id, question: `Question ${id}: tell me about a decision.`, question_type: "behavioural", competency: "judgement", difficulty: "moderate" };
}

function baseState(over: Record<string, unknown> = {}) {
  return {
    session_id: SID, state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
    current_question: question(1), report_available: false, last_evaluation: null,
    target_role: "Senior Product Manager", deep_dive: null, error: null,
    error_recoverable: false, cumulative_cost_usd: 0, ...over,
  };
}

/** A stateful mock that advances a single interview through its lifecycle. */
async function mockInterview(page: Page) {
  const store = { current: baseState() };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });

    if (url.includes("/capabilities"))
      return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
        live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: false });
    if (url.endsWith("/interviews/options")) return json(OPTIONS);

    // create
    if (url.endsWith("/interviews") && method === "POST") { store.current = baseState(); return json(store.current); }
    // list
    if (url.endsWith("/interviews") && method === "GET")
      return json({ sessions: [{ session_id: SID, target_role: "Senior Product Manager", state: store.current.state, question_number: store.current.question_number, questions_planned: 2, updated_at: "2026-09-08T00:00:00Z" }] });

    if (url.match(/\/interviews\/[^/]+\/answers$/)) {
      store.current = baseState({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL });
      return json(store.current);
    }
    if (url.endsWith("/deep-dive") && method === "POST") {
      store.current = baseState({ state: "BRANCH_AWAITING_ANSWER", current_question: null, last_evaluation: EVAL,
        deep_dive: { active: true, mode: "deepen_reasoning", depth: 1, max_depth: 2, parent_question_id: 1,
          current_branch_question: { branch_id: "b1", parent_question_id: 1, question: "Why did that approach work?", branch_mode: "deepen_reasoning", focus_area: "reasoning", difficulty: "moderate", depth: 1 },
          last_branch_evaluation: null, can_go_deeper: false } });
      return json(store.current);
    }
    if (url.endsWith("/deep-dive/answers")) {
      store.current = baseState({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL,
        deep_dive: { active: true, mode: "deepen_reasoning", depth: 1, max_depth: 2, parent_question_id: 1,
          current_branch_question: null, last_branch_evaluation: EVAL, can_go_deeper: false } });
      return json(store.current);
    }
    if (url.endsWith("/deep-dive/return")) {
      store.current = baseState({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL, deep_dive: null });
      return json(store.current);
    }
    if (url.endsWith("/next-question")) {
      store.current = baseState({ state: "INTERVIEW_COMPLETE", current_question: null });
      return json(store.current);
    }
    if (url.endsWith("/complete")) { store.current = baseState({ state: "INTERVIEW_COMPLETE", current_question: null }); return json(store.current); }
    if (url.endsWith("/report") && method === "POST") { store.current = baseState({ state: "REPORT_READY", current_question: null, report_available: true }); return json({ session_id: SID, report: reportBody(), saved_report_id: 1, save_failed: false }); }
    if (url.endsWith("/report") && method === "GET") return json({ session_id: SID, report: reportBody(), saved_report_id: 1, save_failed: false });

    // GET session (refresh / resume)
    if (url.match(/\/interviews\/[^/]+$/) && method === "GET") return json(store.current);
    return json({});
  });
}

function reportBody() {
  return {
    overall_readiness_score: 71, performance_summary: "Solid, structured answers overall.",
    strongest_competencies: ["Prioritisation"], development_priorities: ["Quantify impact"],
    recurring_answer_patterns: [], highest_risk_questions: [], evidence_gaps: [],
    recommended_practice_actions: ["Prepare two metric-rich stories"], final_interview_checklist: ["Rehearse the STAR openers"],
  };
}

test("interview: full lifecycle — answer, deep dive, next, complete, report", async ({ page }) => {
  await mockInterview(page);
  await page.goto(`/practice?session=${SID}`);

  // Question 1.
  await expect(page.getByRole("heading", { name: /Question 1: tell me about a decision/i })).toBeVisible();
  await page.getByLabel("Your answer").fill("I prioritised by impact and effort and measured the result.");
  await page.getByRole("button", { name: "Submit answer" }).click();

  // Feedback stays visible; candidate chooses next step.
  await expect(page.getByText("Answer feedback")).toBeVisible();
  await expect(page.getByText("74")).toBeVisible();

  // Deep Dive.
  await page.getByRole("button", { name: /^Go deeper$/ }).click();
  await expect(page.getByText("Why did that approach work?")).toBeVisible();
  await page.getByLabel("Your answer").fill("Because it aligned incentives across teams.");
  await page.getByRole("button", { name: /Submit deep-dive answer/i }).click();
  await expect(page.getByText("Deep-dive feedback")).toBeVisible();
  await page.getByRole("button", { name: /Return to interview/i }).click();

  // Next → complete → report.
  await page.getByRole("button", { name: /Next question/i }).click();
  await expect(page.getByText("Interview complete")).toBeVisible();
  await page.getByRole("button", { name: /Generate performance review/i }).click();
  await expect(page.getByRole("heading", { name: "Performance review" })).toBeVisible();
  await expect(page.getByText(/Practice readiness/i)).toBeVisible();
  await expect(page.getByText("Prioritisation")).toBeVisible();
});

test("interview: refresh mid-interview restores the same question", async ({ page }) => {
  await mockInterview(page);
  await page.goto(`/practice?session=${SID}`);
  await expect(page.getByRole("heading", { name: /Question 1/i })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /Question 1/i })).toBeVisible();
});

test("interview: standalone setup starts an interview without the coach", async ({ page }) => {
  await mockInterview(page);
  await page.goto("/practice");
  await expect(page.getByText("Practise an interview")).toBeVisible();
  await page.getByLabel("Target role").fill("Senior Product Manager");
  await page.getByLabel("Industry or sector").fill("fintech");
  await page.getByRole("button", { name: /Start interview/i }).click();
  // Phase 5.1 Defect C(A): the client must auto-transition to Q1 with NO reload — the
  // setup form leaves the DOM and the interview is interactive (previously the form
  // stayed stuck on "Preparing your interview…" until a manual reload).
  await expect(page.getByRole("heading", { name: /Question 1/i })).toBeVisible();
  await expect(page.getByText("Practise an interview")).toHaveCount(0);
  await expect(page.getByLabel("Your answer")).toBeVisible();
  // The URL is still updated so a refresh restores the same session.
  await expect(page).toHaveURL(new RegExp(`/practice\\?session=${SID}`));
});

test("interview: deep-dive return refreshes the main actions without reload", async ({ page }) => {
  // Phase 5.1 Defect C(B): after Return to interview, the main evaluation + actions
  // must render immediately (the backend now surfaces last_evaluation on return).
  await mockInterview(page);
  await page.goto(`/practice?session=${SID}`);
  await page.getByLabel("Your answer").fill("I prioritised by impact and measured the result.");
  await page.getByRole("button", { name: "Submit answer" }).click();
  await page.getByRole("button", { name: /^Go deeper$/ }).click();
  await page.getByLabel("Your answer").fill("Because it aligned incentives.");
  await page.getByRole("button", { name: /Submit deep-dive answer/i }).click();
  await page.getByRole("button", { name: /Return to interview/i }).click();
  // Controls are present with no reload: the evaluation is shown and Next/End work.
  await expect(page.getByText("Answer feedback")).toBeVisible();
  await expect(page.getByRole("button", { name: /Next question/i })).toBeEnabled();
  await expect(page.getByRole("button", { name: /End interview/i })).toBeVisible();
});

test("interview: no fake Record control and no camera claim", async ({ page }) => {
  await mockInterview(page);
  await page.goto(`/practice?session=${SID}`);
  await expect(page.getByRole("button", { name: /^Record$/ })).toHaveCount(0);
  await expect(page.getByText(/No camera/i)).toBeVisible();
});
