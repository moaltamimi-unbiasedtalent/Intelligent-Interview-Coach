import { expect, test, type Page } from "@playwright/test";

// P2/E2 return journey + response experience, mocked at the network layer (no backend,
// no paid calls). A closure holds the response-detail preference so PATCH is observable.

const ACCOUNT = (responseDetail: string) => ({
  user_id: 1, email: "user@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: ["current_market_research"], response_detail: responseDetail,
});

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
  live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true,
  agent_coach_enabled: true,
};

const RUN = {
  run_id: "run_e2e", status: "completed",
  response: "Here is your brief answer.\n\nHere is the supporting detail behind show more.",
  tools_used: ["SearchCareerKnowledge"], retrieval_used: true,
  sources: [{ title: "O*NET", source_url: "https://example.org/onet", reference_year: 2024, evidence_type: "role" }],
  citations: [], memory_used: false, memory_count: 0, awaiting_human_input: false,
  pending_action: null, handoff_approved: false, events: [], tool_calls: [], warnings: [],
  step_count: 2, turn_step_count: 2,
  conversation: [
    { role: "user", content: "Prep for a PM interview" },
    { role: "assistant", content: "Here is your brief answer.\n\nHere is the supporting detail behind show more." },
  ],
  preparation_context: null, resolved_occupation: "Product manager", resolved_geography: null,
  presentation: {
    answer: "Here is your brief answer.",
    details: "Here is the supporting detail behind show more.",
    has_details: true,
    next_step: null,
  },
};

async function mock(page: Page, opts: { active?: boolean } = {}) {
  const state = { detail: "brief" };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });

    if (url.includes("/auth/me")) return json(ACCOUNT(state.detail));
    if (url.includes("/auth/preferences") && method === "PATCH") {
      const body = JSON.parse(route.request().postData() || "{}");
      state.detail = body.response_detail || state.detail;
      return json(ACCOUNT(state.detail));
    }
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.includes("/agent/run") && method === "POST") return json(RUN);
    if (url.match(/\/interviews(\?|$)/) && method === "GET") {
      return json({ sessions: opts.active
        ? [{ session_id: "s1", target_role: "Backend Engineer", state: "AWAITING_ANSWER", question_number: 3, questions_planned: 6, updated_at: null }]
        : [] });
    }
    if (url.includes("/history/interviews")) return json({ interviews: opts.active ? [{}] : [] });
    if (url.includes("/progress")) return json({ interviews_completed: opts.active ? 1 : 0, answers_evaluated: opts.active ? 4 : 0, recent_interviews: [] });
    if (url.includes("/memory")) return json({ memories: [] });
    return json({});
  });
}

test("returning user sees a continue-practice card on Home", async ({ page }) => {
  await mock(page, { active: true });
  await page.goto("/app");
  await expect(page.getByText("Welcome back")).toBeVisible();
  await expect(page.getByText(/Backend Engineer/)).toBeVisible();
  const cont = page.getByRole("link", { name: /Continue practice/i });
  await expect(cont).toHaveAttribute("href", "/practice?session=s1");
});

test("first-use Home shows no return card", async ({ page }) => {
  await mock(page, { active: false });
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: /Prepare for the interview that matters/i })).toBeVisible();
  await expect(page.getByText("Welcome back")).toHaveCount(0);
});

test("Settings can switch response detail to Detailed (persisted server-side)", async ({ page }) => {
  await mock(page);
  await page.goto("/settings");
  await expect(page.getByText("Response detail")).toBeVisible();
  const detailed = page.getByLabel(/Detailed/);
  await detailed.check();
  await expect(detailed).toBeChecked();
});

test("Coach answer collapses details behind Show more in Brief mode", async ({ page }) => {
  await mock(page);
  // Start a run through the Home CTA (sets the prepare draft → auto-starts on /prepare).
  await page.goto("/app");
  await page.getByLabel("What interview are you preparing for?").fill("Prep for a PM interview");
  await page.getByRole("button", { name: "Ask Mo" }).click();
  await expect(page).toHaveURL(/\/prepare/);
  // The brief answer is visible; the detail is behind Show more (brief mode default).
  await expect(page.getByText("Here is your brief answer.")).toBeVisible();
  await expect(page.getByText("Here is the supporting detail behind show more.")).toHaveCount(0);
  await page.getByRole("button", { name: "Show more" }).click();
  await expect(page.getByText("Here is the supporting detail behind show more.")).toBeVisible();
});
