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

test("agent coach: practice handoff creates an interview (idempotency key) and redirects", async ({ page }) => {
  const interviewKeys: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json(CAPS(true));
    if (url.endsWith("/agent/run")) return json(runBody({ handoff_approved: true, preparation_context: { target_role: "Senior PM", industry: "Tech", seniority: "senior" } }));
    if (url.endsWith("/interviews")) {
      interviewKeys.push(route.request().headers()["idempotency-key"] ?? "");
      return json({ session_id: "sess_e2e", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 5, current_question: { question_id: 1, question: "Q1", question_type: "behavioural", competency: "x", difficulty: "moderate" }, report_available: false, target_role: "Senior PM" });
    }
    return json({});
  });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Ready to practise");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await page.waitForURL(/\/practice\?session=sess_e2e/);
  // The interview creation carried a stable idempotency key derived from the run id.
  expect(interviewKeys.some((k) => k.startsWith("agent-handoff:"))).toBeTruthy();
});

test("agent coach: missing-config handoff asks for industry/level then starts practice", async ({ page }) => {
  let interviewPosts = 0;
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json(CAPS(true));
    if (url.endsWith("/interviews/options")) return json({ career_levels: ["entry", "mid", "senior", "executive"], interview_types: ["behavioural"] });
    // The context lacks industry/career level → the FIRST create is refused with the
    // dedicated stable code (not a generic 422); after the candidate supplies them the
    // SECOND create succeeds.
    if (url.endsWith("/agent/run")) return json(runBody({ handoff_approved: true, preparation_context: { target_role: "Senior PM" } }));
    if (url.endsWith("/interviews") && method === "POST") {
      interviewPosts += 1;
      if (interviewPosts === 1) {
        return json({ error: { code: "missing_interview_handoff_config", message: "Add the missing industry and career level to start practice.", request_id: "req_e2e" } }, 422);
      }
      return json({ session_id: "sess_e2e", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 5, current_question: { question_id: 1, question: "Q1", question_type: "behavioural", competency: "x", difficulty: "moderate" }, report_available: false, target_role: "Senior PM" });
    }
    return json({});
  });

  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Ready to practise");
  await page.getByRole("button", { name: "Start preparing" }).click();

  // The completion form appears ONLY because of the specific missing-config code.
  await expect(page.getByText("One last detail before practice")).toBeVisible();
  await page.getByLabel("Industry / sector").fill("Fashion");
  await page.getByLabel("Career level").selectOption("executive");
  await page.getByRole("button", { name: /Start practice/ }).click();

  await page.waitForURL(/\/practice\?session=sess_e2e&from=coach/);
  expect(interviewPosts).toBe(2);
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
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit before saving" })).toBeVisible();
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

function usageBody() {
  return {
    agent_model_calls: 2, tool_model_calls: 1, model_calls: 3,
    input_tokens: 5420, output_tokens: 1104, total_tokens: 6524,
    estimated_cost_usd: 0.018, usage_complete: true, missing_usage_sources: [],
  };
}

test("P1: Fast profile is sent, retrieval + citation + usage shown, then evidence reuse", async ({ page }) => {
  const sentProfiles: (string | undefined)[] = [];
  let turn = 0;
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json(CAPS(true));
    if (url.endsWith("/agent/run")) {
      const body = route.request().postDataJSON?.() ?? {};
      sentProfiles.push(body.profile);
      // First factual turn: retrieval ran and produced a citation.
      return json(runBody({
        profile: "fast", usage: usageBody(), latency_ms: 4100, cache_hits: 0, cache_misses: 1,
        citations: [{ marker: "[1]", title: "O*NET Product manager", source: "O*NET", page: null }],
        response: "Median pay varies by region [1].",
        conversation: [
          { role: "user", content: "What do PMs earn in Germany?" },
          { role: "assistant", content: "Median pay varies by region [1]." },
        ],
      }));
    }
    if (url.match(/\/agent\/runs\/[^/]+\/messages/)) {
      turn += 1;
      // "Explain that more simply" reuses the prior evidence — a cache hit, no new retrieval.
      return json(runBody({
        profile: "fast", usage: usageBody(), latency_ms: 900, cache_hits: 1, cache_misses: 1,
        response: "In plain terms: pay depends on where you work.",
        conversation: [
          { role: "user", content: "What do PMs earn in Germany?" },
          { role: "assistant", content: "Median pay varies by region [1]." },
          { role: "user", content: "Explain that more simply" },
          { role: "assistant", content: "In plain terms: pay depends on where you work." },
        ],
      }));
    }
    return json({});
  });

  await page.goto("/prepare");
  await page.getByRole("radio", { name: /Fast/ }).click();
  await page.getByLabel("What interview are you preparing for?").fill("What do PMs earn in Germany?");
  await page.getByRole("button", { name: "Start preparing" }).click();

  await expect(page.getByText("Median pay varies by region [1].")).toBeVisible();
  // A subtle, honest usage line is shown after the turn.
  await expect(page.getByLabel("Run usage")).toContainText("Fast");
  await expect(page.getByLabel("Run usage")).toContainText("3 AI calls");
  expect(sentProfiles).toContain("fast");  // the chosen tier reached the API

  // Follow-up restatement → served from reuse; the flow completes without a new run.
  await page.getByLabel("Message Mo").fill("Explain that more simply");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("In plain terms: pay depends on where you work.")).toBeVisible();
  expect(turn).toBe(1);
});

test("P1: inspector shows the safe usage & performance breakdown", async ({ page }) => {
  await mock(page, {
    onGet: runBody({
      profile: "advanced", usage: usageBody(), latency_ms: 5200, cache_hits: 2, cache_misses: 1,
    }),
  });
  await page.goto("/review/agent?run=run_e2e");
  await expect(page.getByText("Usage & performance")).toBeVisible();
  await expect(page.getByText("Complete", { exact: true })).toBeVisible();
  await expect(page.getByText("6,524")).toBeVisible();  // total tokens, localised
});

test("deterministic fallback: /prepare stays on the Career flow when disabled", async ({ page }) => {
  await mock(page, { agentCoach: false });
  await page.goto("/prepare");
  // The agent first-message prompt is not shown; the deterministic coach is.
  await expect(page.getByLabel("What interview are you preparing for?")).toHaveCount(0);
  await expect(page.getByLabel("Ask the coach")).toBeVisible();
});
