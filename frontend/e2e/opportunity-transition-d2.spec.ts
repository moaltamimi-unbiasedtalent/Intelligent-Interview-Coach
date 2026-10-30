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


async function createOpportunity(page: Page) {
  await page.getByPlaceholder(/Senior Product Manager/i).fill("Senior PM");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByPlaceholder(/Acme GmbH/i).fill("Acme");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/opportunities" && r.request().method() === "POST" && r.status() === 201),
    page.getByRole("button", { name: /Create opportunity/i }).click(),
  ]);
}

test("creation consumes only its deep link and reload preserves the list", async ({ page }) => {
  await suppressTutorial(page); await mock(page);
  let creates = 0;
  page.on("request", r => { if (new URL(r.url()).pathname === "/api/v1/opportunities" && r.method() === "POST") creates++; });
  await page.goto("/opportunities?create=1&filter=all#content");
  await createOpportunity(page);
  const link = page.getByRole("link", { name: /Senior PM - Acme/ });
  await expect(link).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.has("create")).toBe(false);
  expect(new URL(page.url()).searchParams.get("filter")).toBe("all");
  expect(new URL(page.url()).hash).toBe("#content");
  await page.reload();
  await expect(link).toBeVisible();
  await expect(page.getByPlaceholder(/Senior Product Manager/i)).toHaveCount(0);
  expect(creates).toBe(1);
  await link.click();
  await expect(page).toHaveURL(/\/opportunities\/1$/);
});

for (const stale of ["empty", "error"] as const) {
  test(`older ${stale} list response cannot erase the created opportunity`, async ({ page }) => {
    await suppressTutorial(page); await mock(page);
    let release!: () => void, started!: () => void;
    const barrier = new Promise<void>(r => { release = r; });
    const ready = new Promise<void>(r => { started = r; });
    let held = false, creates = 0;
    page.on("request", r => { if (new URL(r.url()).pathname === "/api/v1/opportunities" && r.method() === "POST") creates++; });
    await page.route("**/api/v1/opportunities*", async route => {
      const request = route.request();
      if (!held && request.method() === "GET" && new URL(request.url()).pathname === "/api/v1/opportunities") {
        held = true; started(); await barrier;
        await route.fulfill({ status: stale === "error" ? 503 : 200, contentType: "application/json", body: JSON.stringify(stale === "error" ? { error: { code: "unavailable", message: "synthetic" } } : { opportunities: [] }) });
        return;
      }
      await route.fallback();
    });
    await page.goto("/opportunities?create=1");
    await ready; await createOpportunity(page);
    const link = page.getByRole("link", { name: /Senior PM - Acme/ });
    await expect(link).toBeVisible();
    const oldResponse = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/opportunities" && r.request().method() === "GET" && r.status() === (stale === "error" ? 503 : 200));
    release(); await (await oldResponse).finished();
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())));
    await expect(link).toBeVisible();
    expect(creates).toBe(1);
    await link.click(); await expect(page).toHaveURL(/\/opportunities\/1$/);
  });
}

test("locale change preserves the opportunity and detail navigation", async ({ page }) => {
  await suppressTutorial(page); await mock(page);
  let creates = 0;
  page.on("request", r => { if (new URL(r.url()).pathname === "/api/v1/opportunities" && r.method() === "POST") creates++; });
  await page.goto("/opportunities?create=1"); await createOpportunity(page);
  const link = page.getByRole("link", { name: /Senior PM - Acme/ }); await expect(link).toBeVisible();
  await page.getByTestId("language-menu-button").click();
  await page.getByRole("menuitemradio", { name: /français/i }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  await expect(link).toBeVisible(); expect(creates).toBe(1);
  await link.click(); await expect(page).toHaveURL(/\/opportunities\/1$/);
});
