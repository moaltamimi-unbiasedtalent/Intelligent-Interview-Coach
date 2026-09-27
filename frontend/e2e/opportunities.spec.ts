import { expect, test, type Page } from "@playwright/test";

// P10B Wave 6 - Opportunities. Mocked at the network layer (no backend). Proves the list empty
// state, the create wizard, and the opportunity home; plus discoverability from the primary nav.

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: ["current_market_research"], response_detail: "brief", interface_locale: "en",
    conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0, ...over,
  };
}

async function mock(page: Page) {
  const state: { items: Record<string, unknown>[] } = { items: [] };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: true });
    if (url.match(/\/opportunities\/\d+$/) && method === "GET") {
      const id = Number(url.split("/opportunities/")[1]);
      const o = state.items.find((it) => it.id === id);
      return o ? json({ ...o, jd_available: false, interview_ids: [], interview_count: 0 }) : json({ error: { code: "not_found", message: "x" } }, 404);
    }
    if (url.includes("/opportunities") && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const item = {
        id: state.items.length + 1,
        title: [body.target_role, body.company_name, body.company_location].filter(Boolean).join(" - "),
        target_role: body.target_role, company_name: body.company_name ?? null,
        company_location: body.company_location ?? null, company_country: body.company_country ?? null,
        company_domain: body.company_domain ?? null, job_description_document_id: null,
        status: "active", notes: null,
      };
      state.items.push(item);
      return json(item, 201);
    }
    if (url.includes("/opportunities") && method === "GET") return json({ opportunities: state.items });
    if (url.includes("/documents")) return json({ documents: [] });
    return json({});
  });
}

test("opportunities: empty state, create wizard, then home", async ({ page }) => {
  await mock(page);
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { name: "Your opportunities" })).toBeVisible();
  await expect(page.getByText(/Start with an opportunity/i)).toBeVisible();

  // Open the create wizard (use the header action).
  await page.getByRole("button", { name: "New opportunity" }).first().click();
  await expect(page.getByRole("heading", { name: "Create an opportunity" })).toBeVisible();

  // Step 1: role required.
  await page.getByPlaceholder(/Senior Product Manager/i).fill("Senior PM");
  await page.getByRole("button", { name: "Continue" }).click();
  // Step 2: company.
  await page.getByPlaceholder(/Acme GmbH/i).fill("Acme");
  await page.getByRole("button", { name: "Continue" }).click();
  // Step 3: JD (skip) -> review.
  await page.getByRole("button", { name: "Continue" }).click();
  // Step 4: create.
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/opportunities") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Create opportunity/i }).click(),
  ]);

  // Back on the list with the new opportunity.
  await expect(page.getByText("Senior PM - Acme")).toBeVisible();

  // Open its home.
  await page.getByText("Senior PM - Acme").click();
  await expect(page).toHaveURL(/\/opportunities\/1$/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Company intelligence" })).toBeVisible();
});

test("opportunities: reachable from the primary navigation", async ({ page }) => {
  await mock(page);
  await page.goto("/prepare");
  await expect(page.getByRole("link", { name: "Opportunities" }).first()).toBeVisible();
});
