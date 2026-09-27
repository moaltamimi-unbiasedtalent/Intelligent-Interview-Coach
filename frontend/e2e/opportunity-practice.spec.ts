import { expect, test, type Page } from "@playwright/test";

// P10B Wave 8 - integrated candidate journey (the one seam not yet covered end-to-end in the
// browser): launch Practice FROM an Opportunity and prove the Wave 6 governed association survives
// the whole UI path - the opportunity context prefills the setup, and the create request carries
// the owner-scoped `opportunity_id`. Backend/unit/evaluators already prove the server contract;
// this proves the client actually wires the opportunity through to the create call. Mocked at the
// network layer (no backend, no paid calls). Deterministic: client navigations are awaited with
// waitForURL, and the create request is captured directly rather than inferred.

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: ["current_market_research"], response_detail: "brief", interface_locale: "en",
    conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0, ...over,
  };
}

const OPPORTUNITY = {
  id: 1,
  title: "Staff Engineer - Acme GmbH",
  target_role: "Staff Engineer",
  company_name: "Acme GmbH",
  company_location: "Berlin",
  company_country: "DE",
  company_domain: null,
  job_description_document_id: null,
  status: "active",
  notes: null,
  jd_available: false,
  interview_ids: [] as number[],
  interview_count: 0,
};

async function mock(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: true });
    if (url.match(/\/opportunities\/1$/) && method === "GET") return json(OPPORTUNITY);
    if (url.includes("/opportunities") && method === "GET") return json({ opportunities: [OPPORTUNITY] });
    if (url.includes("/interviews/options")) return json({ career_levels: ["senior", "staff"], interview_types: [], difficulty_levels: [] });
    if (url.includes("/interviews") && method === "POST") return json({ session_id: "sess_w8", status: "in_progress" }, 201);
    if (url.includes("/documents")) return json({ documents: [] });
    return json({});
  });
}

test("integrated journey: launching Practice from an Opportunity carries its governed context", async ({ page }) => {
  await mock(page);

  // Opportunity home renders the Practice launch that targets ?opportunity=<id>.
  await page.goto("/opportunities/1");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  const startPractice = page.getByRole("link", { name: "Start practice" });
  await expect(startPractice).toBeVisible();

  // Client-side navigation into Practice with the opportunity in the URL (never candidate content).
  await Promise.all([
    page.waitForURL(/\/practice\?opportunity=1$/),
    startPractice.click(),
  ]);
  await expect(page).toHaveURL(/\/practice\?opportunity=1$/);

  // Setup prefills from the opportunity: the "preparing for this opportunity" note and the role.
  await expect(page.getByText("Preparing for this opportunity")).toBeVisible();
  const roleField = page.getByLabel("Target role");
  await expect(roleField).toHaveValue("Staff Engineer");

  // The candidate still supplies the remaining required field; the role is not overridden.
  await page.getByLabel("Industry or sector").fill("fintech");
  await expect(roleField).toHaveValue("Staff Engineer");

  // The create request carries the owner-scoped opportunity_id and the prefilled configuration.
  const [createReq] = await Promise.all([
    page.waitForRequest((r) => r.url().includes("/interviews") && r.method() === "POST"),
    page.getByRole("button", { name: "Start interview" }).click(),
  ]);
  const body = createReq.postDataJSON() as { opportunity_id?: number; configuration?: Record<string, unknown> };
  expect(body.opportunity_id).toBe(1);
  expect(body.configuration?.target_role).toBe("Staff Engineer");
  expect(body.configuration?.industry_or_sector).toBe("fintech");
});
