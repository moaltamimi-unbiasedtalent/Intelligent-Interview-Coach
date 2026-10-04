import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";

// P10B-W10.11: durable platform pause and feature flags, end to end across TWO browser pages that share ONE stateful network mock standing in for the
// durable backend (the real database, restart and two-process behaviour is proven by tests/test_platform_config_w10_11.py and the manual QA).
// The candidate and the Admin are different pages; neither shares memory with the other except through `server`. The agent "provider" call count stays 0.

const CAPS = (research: boolean) => ({
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true, company_research_enabled: research,
});
const PERMS = ["platform.overview.read", "platform.flags.read", "platform.flags.manage", "platform.config.manage"];

const server = {
  rev: 0, paused: false, providerCalls: 0, flagRev: 0, flagOverride: null as boolean | null,
  reset() { this.rev = 0; this.paused = false; this.providerCalls = 0; this.flagRev = 0; this.flagOverride = null; },
  research() { return this.flagOverride === null ? true : this.flagOverride; },
};

const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
const account = (admin: boolean) => ({ user_id: admin ? 1 : 2, email: admin ? "ops@example.com" : "cand@example.com", display_name: null, platform_role: admin ? "operations_admin" : "user", tier: "basic",
  status: "active", email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: admin ? PERMS : [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 });

const pauseItem = () => ({ capability: "agent", paused: server.paused, source: server.rev ? "override" : "baseline", baseline_paused: false, revision: server.rev, paused_at: null, resumed_at: null, updated_at: null, reason: server.paused ? "provider incident" : "" });
const flagItem = () => ({ flag_id: "external_research", display_name: "External market research", description: "Allows external research.", category: "research", candidate_visible: true, baseline: true,
  baseline_source: "environment variable EXTERNAL_RESEARCH_ENABLED (default on)", override: server.flagOverride, state: server.flagOverride === null ? "inherited" : server.flagOverride ? "enabled_override" : "disabled_override",
  effective: server.research(), revision: server.flagRev, updated_at: null, updated_by_user_id: null, reason: "", notes: "", consumers: [] });

async function mockAdmin(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname; const method = route.request().method();
    const body = () => JSON.parse(route.request().postData() ?? "{}");
    if (path.endsWith("/capabilities")) return json(route, CAPS(server.research()));
    if (path.endsWith("/auth/me")) return json(route, account(true));
    if (path.endsWith("/admin/pause") && method === "GET") return json(route, { environment: "staging", durable: true, items: [pauseItem()], protected_scope: ["agent"], note: "Pausing refuses NEW candidate activity." });
    if (/\/admin\/pause\/agent$/.test(path) && method === "POST") {
      const b = body();
      if (b.expected_revision !== server.rev) return json(route, { error: { code: "http_error", message: "This switch changed since you loaded it. Reload and review the current state before changing it.", request_id: "r" } }, 409);
      server.paused = b.paused; server.rev += 1; return json(route, pauseItem());
    }
    if (path.endsWith("/admin/flags") && method === "GET") return json(route, { environment: "staging", items: [flagItem()], not_mutable: { AGENT_COACH_ENABLED: "read-only environment capability" }, note: "Only the flags listed here exist." });
    if (/\/admin\/flags\/external_research$/.test(path) && method === "PUT") {
      const b = body();
      if (b.expected_revision !== server.flagRev) return json(route, { error: { code: "http_error", message: "stale", request_id: "r" } }, 409);
      server.flagOverride = b.enabled; server.flagRev += 1; return json(route, flagItem());
    }
    if (path.endsWith("/admin/home")) return json(route, { build: { version: "0", git_sha: "abc", build_time: "t", environment: "staging", source: "x" }, migrations: { repository_head: "0023_platform_config", database_revision: "0023_platform_config", state: "match", warning: null },
      health: { database: "reachable", providers_probed: false, note: "" }, rate_limit: { mode: "in_memory_process_local", distributed: false, shared_store_requested: false, note: "" },
      pause: { status: server.paused ? "paused" : "running", environment: "staging", paused: { agent: server.paused }, durable: true, note: "Durable and shared by every process; changed at /admin/configuration." },
      privacy_requests: { status: "restricted", note: "x" }, accounts: { users_total: 1 }, workspaces: { workspaces_total: 0 }, diagnostics_links: [], boundary: "Operational metadata only." });
    return json(route, {});
  });
}

async function mockCandidate(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/capabilities")) return json(route, CAPS(server.research()));
    if (path.endsWith("/auth/me")) return json(route, account(false));
    if (path.endsWith("/agent/run")) {
      if (server.paused) return json(route, { error: { code: "platform_paused", message: "Ask4Mo is temporarily unavailable for this activity.", request_id: "r" } }, 503);
      server.providerCalls += 1;
      return json(route, { run_id: "run1", status: "completed", response: "Grounded guidance.", tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false, memory_count: 0,
        awaiting_human_input: false, pending_action: null, handoff_approved: false, events: [], tool_calls: [], warnings: [], step_count: 1, turn_step_count: 1,
        conversation: [{ role: "user", content: "Prep" }, { role: "assistant", content: "Grounded guidance." }], preparation_context: null, resolved_occupation: null, resolved_geography: null });
    }
    return json(route, {});
  });
}

test("W10.11: pause is observed by an independent candidate page, blocks before the provider, leaves privacy/Admin available, resumes; flags restrict and reset", async ({ browser }) => {
  server.reset();
  const admin = await (await browser.newContext()).newPage();
  const cand = await (await browser.newContext()).newPage();
  await mockAdmin(admin); await mockCandidate(cand);

  await admin.goto("/admin/configuration");
  await expect(admin.getByRole("heading", { name: "Platform runtime: Running" })).toBeVisible();
  await admin.getByRole("button", { name: "Pause Mo (agent) runs" }).click();
  await expect(admin.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await admin.getByRole("alertdialog").getByLabel(/Reason/).fill("provider incident");
  await admin.getByRole("alertdialog").getByRole("button", { name: "Pause" }).click();
  await expect(admin.getByRole("heading", { name: "Platform runtime: Paused (restricted)" })).toBeVisible();

  await cand.goto("/account/data");                                                                   // privacy/account surface still opens
  await expect(cand.getByRole("heading", { level: 1 })).toBeVisible();
  await cand.goto("/prepare");
  await cand.getByLabel("What interview are you preparing for?").fill("Prep");
  await cand.getByRole("button", { name: "Start preparing" }).click();
  await expect(cand.getByRole("alert").filter({ hasText: translate("en", "states.platformPaused") })).toBeVisible();
  await expect(cand.getByText("provider incident")).toHaveCount(0);                                   // the internal reason never reaches the candidate
  expect(server.providerCalls).toBe(0);                                                               // blocked BEFORE the provider

  await admin.goto("/admin");                                                                         // Admin remains usable and shows the pause prominently
  await expect(admin.getByText(/Candidate activity is restricted: agent paused/)).toBeVisible();
  await admin.goto("/admin/configuration");
  await admin.getByRole("button", { name: "Resume Mo (agent) runs" }).click();
  await admin.getByRole("alertdialog").getByLabel(/Reason/).fill("recovered");
  await admin.getByRole("alertdialog").getByRole("button", { name: "Resume" }).click();
  await expect(admin.getByRole("heading", { name: "Platform runtime: Running" })).toBeVisible();

  await cand.reload();
  await cand.getByLabel("What interview are you preparing for?").fill("Prep");
  await cand.getByRole("button", { name: "Start preparing" }).click();
  await expect(cand.getByText("Grounded guidance.")).toBeVisible();
  expect(server.providerCalls).toBe(1);                                                               // admitted again under the existing rules

  await admin.goto("/admin/flags");
  await expect(admin.locator("dd", { hasText: "Inherited baseline" })).toBeVisible();
  await admin.getByRole("button", { name: "Disable override for External market research" }).click();
  await admin.getByRole("alertdialog").getByLabel(/Reason/).fill("cost");
  await admin.getByRole("alertdialog").getByRole("button", { name: "Disable override" }).click();
  await expect(admin.locator("dd", { hasText: "Disabled override" })).toBeVisible();
  expect(server.research()).toBe(false);
  const caps = await cand.evaluate(async () => (await fetch("/api/v1/capabilities")).json());
  expect(caps.company_research_enabled).toBe(false);                                                  // the candidate-visible projection follows the flag
  await admin.getByRole("button", { name: "Reset External market research to inherited baseline" }).click();
  await admin.getByRole("alertdialog").getByLabel(/Reason/).fill("back");
  await admin.getByRole("alertdialog").getByRole("button", { name: "Reset to inherited baseline" }).click();
  await expect(admin.locator("dd", { hasText: "Inherited baseline" })).toBeVisible();
  expect(server.research()).toBe(true);
});

test("W10.11: a stale pause revision is rejected and shown without a retry", async ({ browser }) => {
  server.reset();
  const a = await (await browser.newContext()).newPage();
  await mockAdmin(a);
  await a.goto("/admin/configuration");
  await expect(a.getByRole("heading", { name: "Platform runtime: Running" })).toBeVisible();
  server.rev = 5;                                                                                       // another administrator changed it after this page loaded
  await a.getByRole("button", { name: "Pause Mo (agent) runs" }).click();
  await a.getByRole("alertdialog").getByLabel(/Reason/).fill("x");
  await a.getByRole("alertdialog").getByRole("button", { name: "Pause" }).click();
  await expect(a.getByRole("alertdialog").getByText(/changed since you loaded it/)).toBeVisible();
  expect(server.paused).toBe(false);
});
