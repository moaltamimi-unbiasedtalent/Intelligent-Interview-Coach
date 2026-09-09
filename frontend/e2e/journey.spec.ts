import { expect, test, type Page } from "@playwright/test";

// P4 candidate-journey + handoff-provenance flows, mocked at the network layer.
// No backend, no paid calls.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

const JOURNEY_MID = {
  understand: { status: "complete", role_known: true, requirements_known: true, evidence_used: true },
  prepare: { status: "complete", gaps_known: true, plan_known: true, questions_known: true },
  practise: { status: "in_progress", handoff_approved: false },
};

function baseRun(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_e2e", status: "completed", response: "Here is your grounded guidance.",
    tools_used: ["AnalyzeJobDescription"], retrieval_used: true, sources: [], citations: [],
    memory_used: false, memory_count: 0, memory_loaded: [], awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [], warnings: [],
    step_count: 4, turn_step_count: 4,
    conversation: [{ role: "user", content: "Prep for a Senior PM interview" },
                   { role: "assistant", content: "Here is your grounded guidance." }],
    preparation_context: null, resolved_occupation: "Product manager", resolved_geography: null,
    cache_hits: 0, cache_misses: 0, journey: JOURNEY_MID, handoff_summary: null, ...over,
  };
}

const HANDOFF_PENDING = baseRun({
  status: "awaiting_human_input", awaiting_human_input: true, response: "",
  pending_action: { action_id: "h1", type: "approve_practice_handoff", message: "Ready to practise?", options: [], data: { target_role: "Senior PM" } },
  handoff_summary: {
    target_role: { value: "Senior PM", source: "confirmed_role" },
    focus_areas: [{ value: "Stakeholder leadership", source: "gap_analysis" }],
    question_count: 8, question_source: "question_generator",
  },
});

const HANDOFF_APPROVED = baseRun({
  handoff_approved: true,
  preparation_context: { target_role: "Senior PM", industry: "Tech", seniority: "senior" },
  journey: { ...JOURNEY_MID, practise: { status: "complete", handoff_approved: true } },
});

function interviewState() {
  return { session_id: "sess_e2e", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 5,
           target_role: "Senior PM", current_question: { question_id: 1, question: "Tell me about a project.", question_type: "behavioural", competency: "x", difficulty: "moderate" },
           report_available: false, last_evaluation: null, deep_dive: null };
}

async function mock(page: Page, opts: { onRun?: Record<string, unknown>; onGet?: Record<string, unknown> } = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.endsWith("/interviews/options")) return json({ career_levels: ["senior"], interview_types: [], deep_dive_modes: [] });
    if (url.endsWith("/agent/run")) return json(opts.onRun ?? baseRun());
    if (url.match(/\/agent\/runs\/[^/]+\/resume/)) return json(HANDOFF_APPROVED);
    if (url.match(/\/agent\/runs\/[^/]+$/) && method === "GET") return json(opts.onGet ?? baseRun());
    if (url.endsWith("/interviews") && method === "POST") return json(interviewState());
    if (url.match(/\/interviews\/[^/]+$/) && method === "GET") return json(interviewState());
    return json({});
  });
}

test("Flow 1: connected journey → handoff provenance → approve → Practise", async ({ page }) => {
  await mock(page, { onRun: HANDOFF_PENDING });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep for a Senior PM interview");
  await page.getByRole("button", { name: "Start preparing" }).click();

  // Journey chrome shows UNDERSTAND (complete) + PREPARE via visible labels/hints.
  const nav = page.getByRole("navigation", { name: "Preparation journey" });
  await expect(nav.getByText("Understand", { exact: true })).toBeVisible();
  await expect(nav.getByText("Role understood", { exact: true })).toBeVisible();

  // Handoff provenance is visible before creating the interview.
  await expect(page.getByText("Practise this role")).toBeVisible();
  await expect(page.getByText(/confirmed in Coach/)).toBeVisible();
  await expect(page.getByText(/from your gap analysis/)).toBeVisible();
  await expect(page.getByText(/8 practice questions/)).toBeVisible();

  // Approve → interview is created → Practise, with honest Coach provenance.
  await page.getByRole("button", { name: "Start practice" }).click();
  await page.waitForURL(/\/practice\?session=sess_e2e.*from=coach/);
  await expect(page.getByTestId("coach-provenance")).toHaveText("Prepared in your Coach session");
  await expect(page.getByText("Tell me about a project.")).toBeVisible();
});

test("Flow 2: journey state is restored on refresh", async ({ page }) => {
  await mock(page, { onGet: baseRun({ journey: JOURNEY_MID }) });
  await page.goto("/prepare?run=run_e2e");
  const nav = page.getByRole("navigation", { name: "Preparation journey" });
  await expect(nav.getByText("Role understood", { exact: true })).toBeVisible();
  await expect(nav.getByText("Preparation ready", { exact: true })).toBeVisible();
});

test("Flow 3: standalone Practice has no fake Coach provenance", async ({ page }) => {
  await mock(page);
  await page.goto("/practice?session=sess_e2e");  // no from=coach
  await expect(page.getByText("Tell me about a project.")).toBeVisible();
  await expect(page.getByTestId("coach-provenance")).toHaveCount(0);
});
