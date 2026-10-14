import { expect, test, type Page } from "@playwright/test";

// W12.4D-B Stripe Managed Payments foundation: Admin readiness UI, mocked at the network layer. Server-side authorization, credential separation and
// fail-closed behaviour are proven by tests/test_stripe_foundation_w12_4d_b.py. Nothing contacts Stripe and no payment path exists.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const BASE = ["platform.overview.read", "platform.integrations.read", "platform.integrations.manage"];
const OWNER = [...BASE, "platform.integrations.secret.rotate", "platform.users.role.assign"];
const slot = (s: string, n: string, req: boolean, configured = false) => ({ slot: s, label: n, external_name: n, configured, source: configured ? "managed" : "none", writable: true,
  source_kind: configured ? "managed" : "none", managed: configured, managed_readable: configured ? true : null, revision: configured ? 1 : null, last_rotated_at: null,
  environment_fallback: false, required: req, min_length: 16, max_length: 4096, applies: "restart" });
const DETAIL = { code: "stripe_managed_payments", name: "Stripe Managed Payments (billing provider)", category: "payments", category_label: "Payments / billing",
  adapter: "Stripe Managed Payments (merchant of record)", description: "Owner-selected billing provider foundation.", classification: "code_present_not_validated",
  configuration_status: "partially_configured",
  slots: [slot("sandbox_api_key", "Sandbox secret API key", true, true), slot("sandbox_webhook_secret", "Sandbox webhook signing secret", true),
    slot("live_api_key", "Live secret API key (inert: live billing is disabled)", false), slot("live_webhook_secret", "Live webhook signing secret (inert)", false)],
  settings: [{ code: "provider", label: "Billing provider", selected: "stripe_managed_payments" }],
  runtime: { enabled: false, managed: "environment", toggle_supported: false, note: "Owned by the environment." },
  store: { name: "managed_with_environment_fallback", writable: true, state: "writable", reason: null },
  health: { status: "not_tested", last_tested_at: null, category: null, latency_ms: null }, test: { supported: false, note: "No connection test exists in this wave." },
  validation_note: "FOUNDATION ONLY: sandbox access UNVERIFIED.", audit: [] };
const READINESS = { status: "not_configured", provider_selected: "stripe_managed_payments", environment: "sandbox", checks: [], configuration_problem: null,
  sandbox: { api: { configured: true, source_kind: "managed" }, webhook: { configured: false, source_kind: "none" } }, live_slots_populated: false,
  eligibility: "not_confirmed", merchant_of_record: "not_confirmed", sandbox_access: "unverified", live_billing: "disabled", checkout: "not_implemented",
  refunds: "not_implemented", webhooks: "not_implemented", last_successful_check: null, last_failure_category: null, api_version: "2026-09-30.endive",
  managed_payments_required: true };

async function mock(page: Page, role: string, perms: string[]) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: role, tier: "basic", status: "active", email_verified: true, providers: ["password"],
        auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en",
        onboarding_completed: true, onboarding_step: 0 });
    }
    if (path.endsWith("/admin/integrations/stripe_managed_payments/readiness")) return json(READINESS);
    if (/\/admin\/integrations\/stripe_managed_payments$/.test(path)) return json(DETAIL);
    if (path.endsWith("/admin/integrations")) return json({ items: [DETAIL] });
    return json({});
  });
}

test("platform admin sees the Stripe foundation readiness: unverified, not confirmed, live disabled, no checkout, no secret", async ({ page }) => {
  await mock(page, "platform_admin", OWNER);
  await page.goto("/admin/integrations");
  await page.getByRole("link", { name: "Stripe Managed Payments (billing provider)" }).click();
  await expect(page.getByTestId("billing-readiness-headline")).toContainText("NOT CONFIGURED");
  await expect(page.getByText("Not confirmed").first()).toBeVisible();
  await expect(page.getByText("Disabled", { exact: true })).toBeVisible();
  await expect(page.getByText("Not implemented").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Test connection" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Replace credential" }).first()).toBeVisible();      // owner may rotate (with step-up)
  expect(await page.locator("body").innerText()).not.toMatch(/sk_(test|live)_|whsec_|merchant of record approved|payments are enabled|ready to take payments/i);
});

test("operations admin can inspect the readiness but has no credential control", async ({ page }) => {
  await mock(page, "operations_admin", BASE);
  await page.goto("/admin/integrations/stripe_managed_payments");
  await expect(page.getByTestId("billing-readiness-headline")).toBeVisible();
  await expect(page.getByRole("button", { name: /credential/i })).toHaveCount(0);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
});

test("a candidate cannot reach the billing provider integration", async ({ page }) => {
  await mock(page, "user", []);
  await page.goto("/admin/integrations/stripe_managed_payments");
  await expect(page.getByTestId("billing-readiness-headline")).toHaveCount(0);
});

for (const [width, height] of [[1280, 900], [768, 1024], [390, 844]] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`W12.4D-B responsive: Stripe integration list and detail do not overflow at ${width}px (${scheme})`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: scheme });
      await mock(page, "platform_admin", OWNER);
      for (const path of ["/admin/integrations", "/admin/integrations/stripe_managed_payments"]) {
        await page.goto(path);
        await expect(page.getByRole("heading", { name: /Integrations|Billing provider readiness/ }).first()).toBeVisible();
        const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(o, `${path} overflow at ${width}px`).toBeLessThanOrEqual(1);
        if (process.env.W124DB_SHOTS) await page.screenshot({ path: `${process.env.W124DB_SHOTS}/${path.replace(/\W+/g, "_")}-${width}-${scheme}.png`, fullPage: true });
      }
    });
  }
}
