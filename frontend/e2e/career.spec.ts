import { expect, test, type Page } from "@playwright/test";

// Real Next.js → API browser flow with CONTROLLED responses. We mock the FastAPI
// /api/v1/* endpoints at the network layer (page.route) so there are no paid
// provider calls and the flow is deterministic — the frontend code path is real.

const CHAT = {
  answer: "Focus on executive communication and commercial ownership.",
  citations: [],
  sources: [{ title: "O*NET Product manager", source_url: "https://example.org/onet", reference_year: 2024 }],
  tools: [],
  input_flagged: false,
  has_evidence: true,
  preparation_available: true,
};

const JOB_ANALYSIS = {
  ok: true,
  tool_name: "job_description_analyzer",
  status: "ok",
  result: { role_title: "Senior Product Manager", seniority: "Senior", required_skills: ["Roadmapping", "Discovery"], likely_interview_themes: ["Prioritisation"] },
  error: null,
};

const SESSION = {
  session_id: "sess_demo_1",
  state: "AWAITING_ANSWER",
  question_number: 1,
  questions_planned: 5,
  current_question: { question_id: 1, question: "Tell me about aligning executives behind a roadmap.", question_type: "behavioural", competency: "influence", difficulty: "moderate" },
  report_available: false,
  target_role: "Senior Product Manager",
};

async function mockApi(page: Page, overrides: Record<string, unknown> = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_test" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: false, agent_memory: false, human_in_the_loop: false });
    if (url.includes("/career/chat")) return json(overrides.chat ?? CHAT);
    if (url.includes("/career/job-analysis")) return json(JOB_ANALYSIS);
    if (url.includes("/interviews/")) return json(SESSION);
    if (url.endsWith("/interviews")) return json(SESSION);
    if (url.includes("/knowledge/sources")) return json({ sources: [{ source_id: "onet", title: "O*NET", group: "Occupation profiles" }] });
    if (url.includes("/knowledge/snapshot")) return json({ documents: 12, chunks: 240, document_types: 4 });
    return json({});
  });
}

test("prepare: submit a request and render the grounded response + sources", async ({ page }) => {
  await mockApi(page);
  await page.goto("/prepare");
  await page.getByLabel("Ask the coach").fill("What should I focus on?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/executive communication/i)).toBeVisible();
  // Source disclosure works.
  await page.getByText(/Career evidence: 1 source/i).click();
  await expect(page.getByRole("link", { name: /O\*NET Product manager/i })).toBeVisible();
});

test("prepare: insufficient evidence shows a calm state, not a fabricated answer", async ({ page }) => {
  await mockApi(page, { chat: { ...CHAT, has_evidence: false, sources: [] } });
  await page.goto("/prepare");
  await page.getByLabel("Ask the coach").fill("obscure question");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/don.t have enough reliable evidence/i)).toBeVisible();
});

test("prepare tools → start practice creates a session and lands on /practice with real role", async ({ page }) => {
  await mockApi(page);
  await page.goto("/prepare");
  await page.getByText("Preparation tools").click();
  await page.getByLabel("Job description").fill("We need a senior PM to own the roadmap.");
  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByText(/Role:\s*Senior Product Manager/i)).toBeVisible();
  await page.getByRole("button", { name: /Start interview practice/i }).click();
  await expect(page).toHaveURL(/\/practice\?session=sess_demo_1/);
  await expect(page.getByText("Senior Product Manager")).toBeVisible();
  await expect(page.getByRole("heading", { name: /aligning executives behind a roadmap/i })).toBeVisible();
});

test("prepare: backend error shows a safe message with no raw internals", async ({ page }) => {
  await page.route("**/api/v1/capabilities", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: false, agent_memory: false, human_in_the_loop: false }) }));
  await page.route("**/api/v1/career/chat", (r) =>
    r.fulfill({ status: 503, contentType: "application/json", headers: { "x-request-id": "req_err" }, body: JSON.stringify({ error: { code: "not_configured", message: "The career assistant is temporarily unavailable.", request_id: "req_err" } }) }),
  );
  await page.goto("/prepare");
  await page.getByLabel("Ask the coach").fill("hi");
  await page.getByRole("button", { name: "Ask" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).not.toContainText(/Traceback/i);
  await expect(alert).not.toContainText(/sql/i);
});

test("sources page renders career evidence from the knowledge API", async ({ page }) => {
  await mockApi(page);
  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "O*NET" })).toBeVisible();
});
