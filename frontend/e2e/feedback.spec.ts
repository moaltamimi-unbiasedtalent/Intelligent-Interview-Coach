import { expect, test, type Page } from "@playwright/test";

// P5 candidate-feedback flows, mocked at the network layer (stateful feedback store).
// No backend, no paid calls.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

function agentRun(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_e2e", status: "completed", response: "Grounded guidance.",
    tools_used: [], retrieval_used: false, sources: [], citations: [],
    memory_used: false, memory_count: 0, memory_loaded: [], awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [], warnings: [],
    step_count: 1, turn_step_count: 1,
    conversation: [{ role: "user", content: "Prep" }, { role: "assistant", content: "Grounded guidance.", response_id: "run_e2e:1" }],
    preparation_context: null, resolved_occupation: null, resolved_geography: null,
    cache_hits: 0, cache_misses: 0, ...over,
  };
}

function interviewState(over: Record<string, unknown> = {}) {
  return {
    session_id: "sess_e2e", state: "AWAITING_ANSWER", question_number: 2, questions_planned: 5,
    target_role: "Senior PM",
    current_question: { question_id: 2, question: "Describe a conflict.", question_type: "behavioural", competency: "x", difficulty: "moderate" },
    report_available: false, last_evaluation: null, deep_dive: null, ...over,
  };
}

const EVAL = {
  overall_score: 74, relevance: 7, structure: 7, evidence: 7, role_knowledge: 7,
  problem_solving: 7, communication: 7, credibility: 7,
  strengths: ["Clear structure"], improvement_areas: ["Add metrics"], missing_evidence: [],
  stronger_answer_structure: "Use STAR-plus-learning.", improved_example_answer: "", follow_up_question: "And then?",
};

async function mock(page: Page, opts: { onGetRun?: Record<string, unknown>; onInterview?: Record<string, unknown> } = {}) {
  const feedback: Record<string, { surface: string; target_id: string; rating: string; comment: string | null }> = {};
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });

    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/interviews/options")) return json({ career_levels: ["senior"], interview_types: [], deep_dive_modes: [] });

    // Feedback (stateful).
    if (path.endsWith("/feedback")) {
      if (method === "POST") {
        const b = route.request().postDataJSON();
        const key = `${b.surface}:${b.target_id}`;
        feedback[key] = { surface: b.surface, target_id: b.target_id, rating: b.rating, comment: b.comment ?? null };
        return json({ id: 1, ...feedback[key], created_at: null, updated_at: null }, 201);
      }
      if (method === "GET") {
        const key = `${url.searchParams.get("surface")}:${url.searchParams.get("target_id")}`;
        return json(feedback[key] ? { id: 1, ...feedback[key], created_at: null, updated_at: null } : null);
      }
    }

    if (path.endsWith("/agent/run")) return json(agentRun());
    if (path.match(/\/agent\/runs\/[^/]+$/) && method === "GET") return json(opts.onGetRun ?? agentRun());
    if (path.match(/\/agent\/runs\/[^/]+\/messages/)) return json(agentRun());

    if (path.endsWith("/interviews") && method === "POST") return json(interviewState());
    if (path.match(/\/interviews\/[^/]+\/answers$/)) return json(interviewState({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL }));
    if (path.match(/\/interviews\/[^/]+\/report$/)) return json({ session_id: "sess_e2e", saved_report_id: 1, save_failed: false, report: { overall_readiness_score: 72, performance_summary: "Good progress.", strongest_competencies: ["clarity"] } });
    if (path.match(/\/interviews\/[^/]+$/) && method === "GET") return json(opts.onInterview ?? interviewState());
    return json({});
  });
}

test("Flow 1: Agent answer → Helpful → persists across refresh", async ({ page }) => {
  await mock(page, { onGetRun: agentRun() });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await expect(page.getByText("Grounded guidance.")).toBeVisible();

  await page.getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(page.getByRole("button", { name: "Helpful", exact: true })).toHaveAttribute("aria-pressed", "true");

  // Refresh the run: the saved rating is restored.
  await page.goto("/prepare?run=run_e2e");
  await expect(page.getByText("Grounded guidance.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Helpful", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("Flow 2: Agent answer → Not helpful → comment → conversation continues", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await page.getByRole("button", { name: "Not helpful" }).click();
  await page.getByLabel(/What could be better/).fill("Too generic");
  await page.getByRole("button", { name: "Save comment" }).click();
  await expect(page.getByRole("button", { name: "Not helpful" })).toHaveAttribute("aria-pressed", "true");
  // The coach still works normally after feedback (behaviour unchanged).
  await page.getByLabel("Message Mo").fill("Tell me more");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Grounded guidance.")).toBeVisible();
});

test("Flow 3: Interview evaluation → Helpful", async ({ page }) => {
  await mock(page);  // starts at AWAITING_ANSWER; submitting an answer reveals the eval
  await page.goto("/practice?session=sess_e2e");
  await page.getByLabel("Your answer").fill("My structured answer using STAR.");
  await page.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByText("Answer feedback")).toBeVisible();
  const group = page.getByRole("group", { name: "Was this feedback helpful?" });
  await group.getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(group.getByRole("button", { name: "Helpful", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("Flow 4: Final report → Helpful", async ({ page }) => {
  await mock(page, { onInterview: interviewState({ state: "REPORT_READY" }) });
  await page.goto("/practice?session=sess_e2e");
  await expect(page.getByText("Performance review")).toBeVisible();
  const group = page.getByRole("group", { name: "Was this report useful?" });
  await group.getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(group.getByRole("button", { name: "Helpful", exact: true })).toHaveAttribute("aria-pressed", "true");
});
