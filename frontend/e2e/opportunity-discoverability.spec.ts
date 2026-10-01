import { expect, test, type Page } from "@playwright/test";

// P10B-W9.4 - Opportunity discoverability (Pilot PF-10). Reproduces the exact task two of four
// Pilot participants could not complete: "Create an Opportunity for the role." The whole core path
// goes through normal UI (no direct API creation), from authenticated Home to Prepare-with-context.

function account() {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
    coaching_style: "balanced", career_geography: "", target_role: "", onboarding_completed: true,
    onboarding_step: 0,
  };
}

// Stateful opportunities mock (create via UI then read back), modelled on opportunities.spec.ts.
async function mock(page: Page) {
  const state: { items: Record<string, unknown>[] } = { items: [] };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(account());
    // Agent Coach enabled so Prepare mounts the workspace that pre-populates governed Opportunity
    // context (role + JD) and shows the "Preparing for this opportunity" note.
    if (url.includes("/capabilities")) return json({ agent_coach_enabled: true, realtime_voice_enabled: false, company_research_enabled: false });
    // ReturnJourney / Home reads (empty -> first-use).
    if (url.includes("/interviews") && method === "GET") return json({ sessions: [] });
    if (url.includes("/history")) return json({ interviews: [] });
    if (url.includes("/progress")) return json({ interviews_completed: 0, answers_evaluated: 0, recent_interviews: [] });
    if (url.includes("/memory")) return json({ memories: [] });
    if (url.match(/\/opportunities\/\d+$/) && method === "GET") {
      const id = Number(url.split("/opportunities/")[1]);
      const o = state.items.find((it) => it.id === id);
      return o ? json({ ...o, jd_available: false, interview_ids: [], interview_count: 0 }) : json({ error: { code: "not_found", message: "x" } }, 404);
    }
    if (url.includes("/opportunities") && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const item = {
        id: state.items.length + 1,
        title: [body.target_role, body.company_name].filter(Boolean).join(" - "),
        target_role: body.target_role, company_name: body.company_name ?? null,
        company_location: null, company_country: null, company_domain: null,
        job_description_document_id: null, status: "active", notes: null,
      };
      state.items.push(item);
      return json(item, 201);
    }
    if (url.includes("/opportunities") && method === "GET") return json({ opportunities: state.items });
    if (url.includes("/documents")) return json({ documents: [] });
    return json({});
  });
}

// The first-run Tutorial invitation (a separate W9.5 surface) auto-fires on /app and would overlap
// the create wizard; suppress it deterministically so this test isolates W9.4 discoverability.
async function suppressTutorial(page: Page) {
  // W9.5: tutorial state is account-scoped (key `ask4mo.tutorial:<user_id>`). The mocked account is
  // user_id 1, so suppress that account's invitation (version 2).
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "ask4mo.tutorial:1",
        JSON.stringify({ version: 2, completed: true, dismissed: true, lastStep: 0 }),
      );
    } catch { /* storage blocked — ignore */ }
  });
}

test("Pilot task: a fresh candidate finds and creates an Opportunity from Home, then prepares from it", async ({ page }) => {
  await suppressTutorial(page);
  await mock(page);
  await page.goto("/app");

  // 1-2) Without moderator instruction, the job-context action is visibly Opportunity-related, and it
  //      appears BEFORE the general Prepare composer.
  await expect(page.getByRole("heading", { name: /prepare for a specific job/i })).toBeVisible();
  const createCta = page.getByRole("link", { name: /create an opportunity/i });
  await expect(createCta).toBeVisible();
  const askMo = page.getByRole("button", { name: "Ask Mo" }); // the Prepare composer remains available
  await expect(askMo).toBeVisible();
  const oppBox = await createCta.boundingBox();
  const askBox = await askMo.boundingBox();
  expect(oppBox!.y).toBeLessThan(askBox!.y); // Opportunity entry is above the Prepare composer

  // 3-4) Follow it into the EXISTING creation flow (deep-link opens the inline create form).
  await createCta.click();
  await expect(page).toHaveURL(/\/opportunities\?create=1$/);
  await expect(page.getByRole("heading", { name: "Create an opportunity" })).toBeVisible();

  // 5) Create via normal UI.
  await page.getByPlaceholder(/Senior Product Manager/i).fill("Senior PM");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByPlaceholder(/Acme GmbH/i).fill("Acme");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click(); // skip JD -> review
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/opportunities") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Create opportunity/i }).click(),
  ]);

  // 6) The created Opportunity is visibly confirmed in the list.
  await expect(page.getByText("Senior PM - Acme")).toBeVisible();

  // 7) Continue from the Opportunity toward Prepare.
  await page.getByText("Senior PM - Acme").click();
  await expect(page).toHaveURL(/\/opportunities\/1$/);
  await page.getByRole("link", { name: /Open Prepare/i }).click();

  // 8) Prepare opens with the governed Opportunity context (owner-scoped) reaching it.
  await expect(page).toHaveURL(/\/prepare\?opportunity=1$/);
  await expect(page.getByText(/Preparing for this opportunity/i)).toBeVisible();
});

test("mobile: Opportunity is discoverable on Home and in the bottom navigation (390px)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await suppressTutorial(page);
  await mock(page);
  await page.goto("/app");

  // Home Opportunity entry is present and actionable at phone width.
  await expect(page.getByRole("heading", { name: /prepare for a specific job/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /create an opportunity/i })).toBeVisible();

  // The mobile bottom nav exposes Opportunities with its full accessible name (no ambiguous clip).
  const bottomNav = page.getByRole("navigation", { name: "Primary" });
  const oppNav = bottomNav.getByRole("link", { name: "Opportunities" });
  await expect(oppNav).toBeVisible();
  await expect(oppNav).toHaveAttribute("href", "/opportunities");
});
