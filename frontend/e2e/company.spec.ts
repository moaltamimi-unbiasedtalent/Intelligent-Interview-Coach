import { expect, test, type Page } from "@playwright/test";

// P10B Wave 5 - Company Intelligence. Mocked at the network layer (no backend, no provider calls).
// Proves: the directable form is reachable and discoverable, a report renders with FACT / AI-suggestion
// separation + provenance, review providers are link-only (not integrated), and the clarification
// state appears when no website is given.

function account(over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: ["current_market_research"], response_detail: "brief", interface_locale: "en",
    conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0, ...over,
  };
}

function report(over: Record<string, unknown> = {}) {
  return {
    status: "ready",
    identity: { company_name: "Acme", confidence: "confirmed", website: "https://acme.example",
                domain: "acme.example", location: "Berlin", country: "DE", note: null },
    snapshot: { description: "Acme builds software.", website: "https://acme.example",
                retrieved_at: "2026-01-15T09:00:00Z", industry: null },
    business_market: [{ kind: "fact", text: "Acme builds software products.", source_ids: ["s1"] }],
    recent_developments: [],
    culture: [{ kind: "fact", text: "Values: integrity.", source_ids: ["s1"] }],
    review_signals: [],
    role_relevance: [{ kind: "model_inference", text: "Connect Acme to your role.", source_ids: ["s1"] }],
    interview_preparation: {
      topics: [{ kind: "model_inference", text: "Understand Acme's products.", source_ids: ["s1"] }],
      questions_to_ask: [{ kind: "model_inference", text: "What are the team priorities?", source_ids: [] }],
      clarify: [],
    },
    sources: [{ id: "s1", title: "Acme - About", url: "https://acme.example/about",
                source_type: "company_official_web", provider: "company_web",
                retrieved_at: "2026-01-15T09:00:00Z", effective_date: null, self_reported: true }],
    provider_statuses: [
      { key: "company_web", label: "Official company website", state: "configured", detail: null, external_url: "https://acme.example" },
      { key: "glassdoor", label: "Glassdoor reviews", state: "not_integrated", detail: null, external_url: "https://www.google.com/search?q=Acme+Glassdoor" },
    ],
    limitations: ["reviews_not_integrated"],
    warnings: [], retrieved_at: "2026-01-15T09:00:00Z", cache_hit: false, jd_linked: false,
    ...over,
  };
}

async function mock(page: Page, reportBody: Record<string, unknown>) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    if (url.includes("/capabilities"))
      return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: true });
    if (url.includes("/research/company") && method === "POST") return json(reportBody);
    if (url.includes("/documents")) return json({ documents: [] });
    if (url.includes("/memory")) return json({ memories: [], items: [] });
    return json({});
  });
}

test("company research: form renders a report with fact/AI separation and provenance", async ({ page }) => {
  await mock(page, report());
  await page.goto("/company");
  await expect(page.getByRole("heading", { name: "Company research", level: 1 })).toBeVisible();

  await page.getByPlaceholder(/Acme GmbH/i).fill("Acme");
  await page.getByRole("textbox", { name: /Official website/i }).fill("acme.example");
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/research/company") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Research company/i }).click(),
  ]);

  await expect(page.getByRole("heading", { name: "Company snapshot" })).toBeVisible();
  await expect(page.getByText("Acme builds software products.")).toBeVisible();
  // Claim kinds are labelled distinctly.
  await expect(page.getByText("Fact").first()).toBeVisible();
  await expect(page.getByText("AI suggestion").first()).toBeVisible();
  // Provenance link.
  await expect(page.getByRole("link", { name: "Acme - About" }).first()).toHaveAttribute("href", "https://acme.example/about");
  // Review provider is link-only (not integrated), never copied content.
  await expect(page.getByRole("link", { name: /Glassdoor reviews/i })).toHaveAttribute("href", /google\.com\/search/);
  await expect(page.getByText(/not an employer rating/i)).toBeVisible();
});

test("company research: clarification state when no website is provided", async ({ page }) => {
  await mock(page, report({
    status: "needs_clarification",
    identity: { company_name: "Acme", confidence: "needs_clarification", website: null,
                domain: null, location: "Berlin", country: null, note: null },
    business_market: [], culture: [], role_relevance: [], sources: [],
    interview_preparation: { topics: [], questions_to_ask: [], clarify: [] },
    provider_statuses: [
      { key: "company_web", label: "Official company website", state: "unavailable", detail: null, external_url: null },
      { key: "glassdoor", label: "Glassdoor reviews", state: "not_integrated", detail: null, external_url: "https://www.google.com/search?q=Acme" },
    ],
    limitations: ["company_website_missing", "reviews_not_integrated"],
  }));
  await page.goto("/company");
  await page.getByPlaceholder(/Acme GmbH/i).fill("Acme");
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/research/company")),
    page.getByRole("button", { name: /Research company/i }).click(),
  ]);
  await expect(page.getByText(/Which company exactly/i)).toBeVisible();
});
