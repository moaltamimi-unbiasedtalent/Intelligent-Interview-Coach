import { expect, test, type Page } from "@playwright/test";

// W12.4B secure provider and secret administration, mocked at the network layer. Server-side authorization, step-up, encryption, precedence,
// transactional audit and leakage are proven by tests/test_secret_admin_w12_4b.py; these browser tests prove the governed UI flow and the
// role boundary. No provider is contacted and the value below is a dummy that must never come back in any response or render.

const DUMMY = "dummy-credential-for-e2e-0001";
const BASE = ["platform.overview.read", "platform.integrations.read", "platform.integrations.manage"];
const OWNER = [...BASE, "platform.integrations.secret.rotate", "platform.users.role.assign"];
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };

type Sec = { managed: boolean; revision: number; elevated: boolean; sent: string[] };

function slot(s: Sec) {
  return { slot: "api_key", label: "API key", external_name: "OPENROUTER_API_KEY", configured: true, source: s.managed ? "managed" : "environment", writable: true,
    source_kind: s.managed ? "managed" : "environment", managed: s.managed, managed_readable: s.managed ? true : null, revision: s.managed ? s.revision : null,
    last_rotated_at: s.managed ? "2026-10-14T09:00:00" : null, environment_fallback: true, required: true, min_length: 8, max_length: 4096, applies: "restart" };
}
function detail(s: Sec) {
  return { code: "openrouter", name: "OpenRouter (language models)", category: "ai_model", category_label: "AI / model", adapter: "OpenRouter chat API",
    description: "Chat model provider.", classification: "runtime_active", configuration_status: "configured", slots: [slot(s)], settings: [],
    runtime: { enabled: true, managed: "environment", toggle_supported: false, note: "Runtime state is owned by the deployment environment." },
    store: { name: "managed_with_environment_fallback", writable: true, state: "writable", reason: null },
    health: { status: "not_tested", last_tested_at: null, category: null, latency_ms: null }, test: { supported: true, note: "One key check." },
    validation_note: "Healthy only after a successful manual test.", audit: [] };
}

async function mock(page: Page, role: string, perms: string[], s: Sec) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: role, tier: "basic", status: "active", email_verified: true,
        providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en",
        conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    }
    if (path.endsWith("/admin/step-up") && method === "POST") { s.elevated = true; return json({ elevated: true, window_seconds: 300, method: "password_reauthentication" }); }
    if (/\/credentials\/api_key\/remove$/.test(path) && method === "POST") {
      if (!s.elevated) return json({ error: { code: "step_up_required", message: "Confirm your password to continue." } }, 403);
      s.managed = false;
      return json({ integration: "openrouter", slot: "api_key", removed: true });
    }
    if (/\/credentials\/api_key$/.test(path) && method === "POST") {
      if (!s.elevated) return json({ error: { code: "step_up_required", message: "Confirm your password to continue." } }, 403);
      s.sent.push(route.request().postData() ?? "");
      const action = s.managed ? "rotated" : "created";
      s.managed = true;
      s.revision += 1;
      return json({ integration: "openrouter", slot: "api_key", configured: true, action, revision: s.revision });
    }
    if (/\/admin\/integrations\/[^/]+$/.test(path)) return json(detail(s));
    if (path.endsWith("/admin/integrations")) return json({ items: [detail(s)] });
    return json({});
  });
}

test("platform admin: integration detail, configure with a password step-up, metadata updates, the field clears, no secret rendered", async ({ page }) => {
  const s: Sec = { managed: false, revision: 0, elevated: false, sent: [] };
  await mock(page, "platform_admin", OWNER, s);
  await page.goto("/admin/integrations");
  await page.getByRole("link", { name: "OpenRouter (language models)" }).click();
  await expect(page.getByTestId("source-api_key")).toContainText("Environment");
  await expect(page.getByTestId("store-state")).toContainText("writable");

  await page.getByRole("button", { name: "Configure credential" }).click();
  const dialog = page.getByRole("alertdialog");
  const input = dialog.getByLabel("Credential");
  await expect(input).toHaveValue("");
  await expect(input).toHaveAttribute("type", "password");
  await input.fill(DUMMY);
  await dialog.getByRole("button", { name: "Save credential" }).click();

  const step = page.getByTestId("step-up-dialog");
  await expect(step).toBeVisible();
  await step.getByLabel("Current password").fill("a-correct-password");
  await step.getByRole("button", { name: "Confirm" }).click();

  await expect(page.getByText(/It is saved but not tested/)).toBeVisible();
  await expect(page.getByTestId("source-api_key")).toContainText("Managed secure store");
  await expect(page.getByText("Not tested").first()).toBeVisible();      // saving does not claim health
  expect(s.sent).toHaveLength(1);
  await expect(page.locator("body")).not.toContainText(DUMMY);
  expect(await page.content()).not.toContain(DUMMY);
  expect(page.url()).not.toContain(DUMMY);
  const storage = await page.evaluate(() => JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]));
  expect(storage).not.toContain(DUMMY);

  // rotate (step-up still fresh), then remove with confirmation: the environment value is used again
  await page.getByRole("button", { name: "Replace credential" }).click();
  await expect(page.getByRole("alertdialog").getByLabel("New credential")).toHaveValue("");
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();
  await page.getByRole("button", { name: "Remove managed credential" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("deployment environment credential will be used again");
  await page.getByRole("alertdialog").getByRole("button", { name: "Remove" }).click();
  await expect(page.getByTestId("source-api_key")).toContainText("Environment");
  await expect(page.getByText(/environment credential is used again/)).toBeVisible();
});

test("operations admin can inspect and test but has no credential control", async ({ page }) => {
  const s: Sec = { managed: true, revision: 2, elevated: false, sent: [] };
  await mock(page, "operations_admin", BASE, s);
  await page.goto("/admin/integrations/openrouter");
  await expect(page.getByRole("heading", { name: "Credentials" })).toBeVisible();
  await expect(page.getByTestId("source-api_key")).toContainText("Managed secure store");
  await expect(page.getByRole("button", { name: "Test connection" })).toBeVisible();
  await expect(page.getByRole("button", { name: /credential/i })).toHaveCount(0);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
});

test("a candidate cannot reach Admin integrations", async ({ page }) => {
  const s: Sec = { managed: false, revision: 0, elevated: false, sent: [] };
  await mock(page, "user", [], s);
  await page.goto("/admin/integrations");
  await expect(page.getByRole("heading", { name: "Credentials" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "OpenRouter (language models)" })).toHaveCount(0);
});

for (const [width, height] of [[1280, 900], [768, 1024], [390, 844]] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`W12.4B responsive: integrations list and detail do not overflow horizontally at ${width}px (${scheme})`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: scheme });
      const s: Sec = { managed: true, revision: 2, elevated: false, sent: [] };
      await mock(page, "platform_admin", OWNER, s);
      for (const path of ["/admin/integrations", "/admin/integrations/openrouter"]) {
        await page.goto(path);
        await expect(page.getByRole("heading", { name: /Integrations|Credentials/ }).first()).toBeVisible();
        if (path.endsWith("openrouter")) await expect(page.getByRole("button", { name: "Replace credential" })).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        // F-04 (walkthrough): the list table is allowed to scroll inside its own overflow-x wrapper, never the page.
        expect(overflow, `${path} page-level horizontal overflow at ${width}px`).toBeLessThanOrEqual(1);
        if (process.env.W124B_SHOTS) await page.screenshot({ path: `${process.env.W124B_SHOTS}/${path.replace(/\W+/g, "_")}-${width}-${scheme}.png`, fullPage: true });
      }
    });
  }
}
