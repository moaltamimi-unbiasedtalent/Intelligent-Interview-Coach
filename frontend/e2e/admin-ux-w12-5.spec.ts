import { expect, test, type Page } from "@playwright/test";

// W12.5 Admin UX corrections, mocked at the network layer (the real-stack walkthrough with before/after evidence is recorded in the W12.5 report). These
// browser tests keep the corrections from regressing: collapsed mobile navigation, Review inside the Admin shell, responsive Integrations, and a Command Center
// that survives a failing readiness endpoint. No provider is contacted.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const PERMS = ["platform.overview.read", "platform.users.read", "platform.audit.read", "platform.integrations.read", "platform.ai.read", "platform.knowledge.read", "platform.flags.read",
  "platform.billing.read", "platform.jobs.read", "platform.support.read"];
const HOME = {
  build: { version: "0.1.0", git_sha: "abc1234", build_time: "2026-10-02T10:00:00Z", environment: "staging", source: "x" },
  migrations: { repository_head: "0039_speech_governance", database_revision: "0039_speech_governance", state: "match", warning: null },
  health: { database: "reachable", providers_probed: false, note: "" },
  rate_limit: { mode: "in_memory_process_local", distributed: false, shared_store_requested: false, note: "" },
  pause: { status: "running", paused: {}, durable: true, note: "" },
  privacy_requests: { status: "restricted", note: "" },
  accounts: { users_total: 5, platform_admins: 1, premium_accounts: 2 }, workspaces: { workspaces_total: 3 },
  diagnostics_links: [{ label: "Knowledge readiness", path: "/review/rag" }], boundary: "Operational metadata only.",
};
const item = (code: string, name: string) => ({ code, name, category: "ai_model", category_label: "AI / model", adapter: "a", description: "d", classification: "runtime_active",
  configuration_status: "configured", slots: [{ slot: "api_key", source_kind: "environment" }], settings: [], runtime: {}, store: {}, health: { status: "not_tested", last_tested_at: null }, test: {}, validation_note: "" });

async function mock(page: Page, opts: { readiness?: "fail" | "ok" } = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: "platform_admin", tier: "basic", status: "active", email_verified: true, providers: ["password"],
        auth_method: "session", capabilities: [], admin_permissions: PERMS, response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    }
    if (path.endsWith("/admin/home")) return json(HOME);
    if (path.endsWith("/admin/readiness")) return opts.readiness === "fail" ? json({ error: { code: "x", message: "down" } }, 500) : json({ capabilities: [], summary: {}, vocabulary: { statuses: [], qualifiers: [] }, boundary: "" });
    if (path.endsWith("/admin/integrations")) return json({ items: [item("openrouter", "OpenRouter (language models)"), item("clamav", "ClamAV (upload malware scanning)")] });
    return json({});
  });
}

test("at 390px the Admin navigation is one collapsed menu button, operable by keyboard", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mock(page);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  const button = nav.getByRole("button", { name: /Admin menu: Overview/ });
  await expect(button).toBeVisible();
  expect((await nav.boundingBox())!.height).toBeLessThan(120);                       // was about 750 px of stacked links
  await expect(nav.getByRole("link", { name: /Users/ })).toBeHidden();
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(button).toHaveAttribute("aria-expanded", "true");
  await expect(nav.getByRole("link", { name: /Users/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(button).toHaveAttribute("aria-expanded", "false");
  await expect(button).toBeFocused();
});

test("at 1280px the Admin navigation is the full visible list and the menu button is hidden", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mock(page);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(nav.getByRole("button", { name: /Admin menu/ })).toBeHidden();
  await expect(nav.getByRole("link", { name: /Users/ })).toBeVisible();
  await expect(nav.getByRole("link", { name: /Speech/ })).toBeVisible();
});

test("Review and Diagnostics render inside the Admin navigation with a way back", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mock(page);
  await page.goto("/review");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(nav.getByRole("link", { name: /Review \/ Diagnostics/ })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Review & Diagnostics" })).toBeVisible();
  await nav.getByRole("link", { name: /Overview/ }).click();
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
});

for (const width of [390, 768, 1280]) {
  test(`Integrations does not overflow the page at ${width}px and keeps every field`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mock(page);
    await page.goto("/admin/integrations");
    await expect(page.getByRole("link", { name: "OpenRouter (language models)" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBe(0);
    for (const field of ["Credentials", "Health", "Last tested"]) {
      await expect(page.getByText(field, { exact: true }).first()).toBeAttached();
    }
    if (width === 390) await expect(page.locator('td[data-label="Health"]').first()).toBeVisible();   // card layout shows the Health field on a phone
  });
}

test("a failing readiness endpoint leaves the Command Center usable and says readiness is unavailable", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mock(page, { readiness: "fail" });
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByText(/Capability readiness is unavailable right now/)).toBeVisible();
  await expect(page.getByText(/Something went wrong/)).toHaveCount(0);
});
