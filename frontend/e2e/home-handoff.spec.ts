import { expect, test, type Page } from "@playwright/test";

// Home → Prepare handoff: the goal typed on Home is transferred ephemerally (never via
// the URL) and starts the Coach automatically. Deterministic mocks; no provider calls.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

async function mock(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.endsWith("/agent/run")) {
      // Echo the transferred goal back in the conversation to prove it arrived.
      const body = route.request().postDataJSON?.() ?? {};
      const goal = String(body.goal ?? "");
      return json({
        run_id: "run_home", status: "completed", response: "Here's how we'll prepare.",
        tools_used: [], retrieval_used: false, sources: [], citations: [],
        memory_used: false, memory_count: 0, awaiting_human_input: false,
        pending_action: null, handoff_approved: false, events: [], tool_calls: [],
        warnings: [], step_count: 1, turn_step_count: 1,
        conversation: [
          { role: "user", content: goal },
          { role: "assistant", content: "Here's how we'll prepare." },
        ],
        preparation_context: null, resolved_occupation: null, resolved_geography: null,
      });
    }
    return json({});
  });
}

const GOAL = "Senior Product Manager interview at a fintech";

test("Home Start transfers the goal and auto-starts the Coach (no re-entry)", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await page.getByLabel("What interview are you preparing for?").fill(GOAL);
  await page.getByRole("button", { name: "Start" }).click();

  await expect(page).toHaveURL(/\/prepare/);
  // The Coach started automatically with the exact goal — shown in the conversation.
  await expect(page.getByText(GOAL)).toBeVisible();
  await expect(page.getByText("Here's how we'll prepare.")).toBeVisible();
  // No first-message form waiting for re-entry (the run is live).
  await expect(page.getByRole("button", { name: "Start preparing" })).toHaveCount(0);
});

test("candidate text never appears in the URL", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await page.getByLabel("What interview are you preparing for?").fill(GOAL);
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText(GOAL)).toBeVisible();

  const url = page.url();
  expect(url).not.toContain("Senior Product Manager");
  expect(url).not.toContain("fintech");
  expect(url).toMatch(/\/prepare(\?run=[^&]+)?$/);
});

test("Home 'Paste a job description' opens and focuses the JD field", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await page.getByRole("button", { name: /Paste a job description/ }).click();
  await expect(page).toHaveURL(/\/prepare/);
  const jd = page.getByLabel("Job description (optional)");
  await expect(jd).toBeVisible();
  await expect(jd).toBeFocused();
});

test("Home 'Add your background' opens and focuses the background field", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await page.getByRole("button", { name: /Add your background/ }).click();
  await expect(page).toHaveURL(/\/prepare/);
  const bg = page.getByLabel("Your background (optional)");
  await expect(bg).toBeVisible();
  await expect(bg).toBeFocused();
});
