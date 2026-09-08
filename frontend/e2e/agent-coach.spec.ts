import { expect, test, type Page } from "@playwright/test";

// Real Next.js → API browser flow for the Agent Coach, with CONTROLLED responses
// mocked at the network layer (page.route). No backend, no paid provider calls.

const CAPS = (agentCoach: boolean) => ({
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: agentCoach,
});

function runBody(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_e2e", status: "completed", response: "Here is your grounded guidance.",
    tools_used: ["SearchCareerKnowledge"], retrieval_used: true,
    sources: [{ title: "O*NET Product manager", source_url: "https://example.org/onet", reference_year: 2024, evidence_type: "role" }],
    citations: [], memory_used: false, memory_count: 0, awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 2, turn_step_count: 2,
    conversation: [
      { role: "user", content: "Prep for a Senior PM interview" },
      { role: "assistant", content: "Here is your grounded guidance." },
    ],
    preparation_context: null, resolved_occupation: "Product manager", resolved_geography: null,
    ...over,
  };
}

async function mock(page: Page, opts: {
  agentCoach?: boolean;
  onRun?: Record<string, unknown>;
  onResume?: Record<string, unknown>;
  onGet?: Record<string, unknown>;
} = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json(CAPS(opts.agentCoach ?? true));
    if (url.match(/\/agent\/runs\/[^/]+\/resume/)) return json(opts.onResume ?? runBody());
    if (url.match(/\/agent\/runs\/[^/]+\/messages/)) return json(opts.onRun ?? runBody());
    if (url.match(/\/agent\/runs\/[^/]+$/) && method === "GET") return json(opts.onGet ?? runBody());
    if (url.endsWith("/agent/run")) return json(opts.onRun ?? runBody());
    if (url.endsWith("/interviews")) return json({ session_id: "sess_e2e", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 5, current_question: { question_id: 1, question: "Q1", question_type: "behavioural", competency: "x", difficulty: "moderate" }, report_available: false, target_role: "Senior PM" });
    return json({});
  });
}

test("agent coach: start shows grounded conversation and evidence", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep for a Senior PM interview");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await expect(page.getByText("Here is your grounded guidance.")).toBeVisible();
  await page.getByText(/Career evidence: 1 source/i).click();
  await expect(page.getByRole("link", { name: /O\*NET Product manager/i })).toBeVisible();
});

test("agent coach: role confirmation pauses and resumes the same run", async ({ page }) => {
  await mock(page, {
    onRun: runBody({
      status: "awaiting_human_input", awaiting_human_input: true, response: "",
      pending_action: { action_id: "a1", type: "confirm_role", message: "Which role are you preparing for?", options: ["Product Manager", "Technical Product Manager"], data: {} },
      conversation: [{ role: "user", content: "Prep" }],
    }),
    onResume: runBody(),
  });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await expect(page.getByText("Which role are you preparing for?")).toBeVisible();
  await page.getByLabel("Product Manager", { exact: true }).check();
  await page.getByRole("button", { name: "Confirm role" }).click();
  await expect(page.getByText("Here is your grounded guidance.")).toBeVisible();
});

test("agent coach: practice handoff creates an interview and redirects", async ({ page }) => {
  await mock(page, {
    onRun: runBody({ handoff_approved: true, preparation_context: { target_role: "Senior PM", industry: "Tech" } }),
  });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Ready to practise");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await page.waitForURL(/\/practice\?session=sess_e2e/);
  expect(page.url()).toContain("/practice?session=sess_e2e");
});

test("agent coach: refresh restores the pending approval", async ({ page }) => {
  await mock(page, {
    onGet: runBody({
      status: "awaiting_human_input", awaiting_human_input: true, response: "",
      pending_action: { action_id: "a1", type: "approve_memory", message: "Remember this?", options: [], data: { category: "recurring_gap", summary: "Executive communication", target_role: "Head of People" } },
    }),
  });
  await page.goto("/prepare?run=run_e2e");
  await expect(page.getByText("Executive communication")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
});

test("agent inspector: shows a safe execution timeline", async ({ page }) => {
  await mock(page, {
    onGet: runBody({
      events: [
        { event_type: "run_started" },
        { event_type: "tool_completed", tool_name: "SearchCareerKnowledge", source_count: 1 },
        { event_type: "run_completed" },
      ],
      tool_calls: [{ tool: "SearchCareerKnowledge", status: "ok" }],
    }),
  });
  await page.goto("/review/agent?run=run_e2e");
  await expect(page.getByText("Run summary")).toBeVisible();
  await expect(page.getByText("Execution timeline")).toBeVisible();
  await expect(page.getByText("Tool completed")).toBeVisible();
});

test("deterministic fallback: /prepare stays on the Career flow when disabled", async ({ page }) => {
  await mock(page, { agentCoach: false });
  await page.goto("/prepare");
  // The agent first-message prompt is not shown; the deterministic coach is.
  await expect(page.getByLabel("What interview are you preparing for?")).toHaveCount(0);
  await expect(page.getByLabel("Ask the coach")).toBeVisible();
});
