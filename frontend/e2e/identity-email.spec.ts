import { expect, test, type Page } from "@playwright/test";

// W12.4C identity email journeys and the Admin email panel, mocked at the network layer. Real token redemption, single use, concurrency,
// trusted link origin, delivery states and leakage are proven by tests/test_email_identity_w12_4c.py with a recording fake provider.
// No provider is contacted and no real address is used.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const BASE = ["platform.overview.read", "platform.integrations.read", "platform.integrations.manage"];
const OWNER = [...BASE, "platform.integrations.secret.rotate", "platform.users.role.assign"];

type St = { verify: "ok" | "token_expired" | "token_used" | "token_invalid"; reset: "ok" | "token_expired" | "token_used" | "token_invalid";
  registered: unknown[]; testSent: number; resendStatus: number };
const st = (): St => ({ verify: "ok", reset: "ok", registered: [], testSent: 0, resendStatus: 200 });

const DELIVERY = {
  status: "provider_accepted", provider_selected: "brevo", adapter_in_process: "brevo", provider_account: { configured: true, source_kind: "managed" },
  sender_configured: true, sender_verification: "verified_by_last_test", restart_required: false, restart_reason: null,
  last_test: { state: "passed", last_tested_at: "2026-10-14T09:00:00", category: "ok" }, delivery_confirmation: "not_collected", live_delivery: "unverified",
  link_origin: { configured: true, https: true }, identity_pipeline: { verification: "ready", recovery: "ready" },
  diagnostics: { retention_days: 30, last_attempt: null, last_accepted: { at: "2026-10-14T09:30:00", message_type: "email_verification", status: "provider_accepted", failure_category: null },
    last_failure: null, last_identity_attempt: null, last_24h: { provider_accepted: 4, failed: 0, delivery_unknown: 0, captured: 0 },
    recent: [{ at: "2026-10-14T09:30:00", message_type: "email_verification", status: "provider_accepted", failure_category: null }] },
  last_failure_category: null, note: "Provider accepted does not mean delivered." };
const BREVO = {
  code: "email_brevo", name: "Brevo (transactional email)", category: "communications", category_label: "Email / communications", adapter: "Brevo email API",
  description: "Sends account emails.", classification: "runtime_active", configuration_status: "configured",
  slots: [{ slot: "api_key", label: "API key", external_name: "BREVO_API_KEY", configured: true, source: "managed", writable: true, source_kind: "managed", managed: true,
    managed_readable: true, revision: 1, last_rotated_at: "2026-10-14T09:00:00", environment_fallback: false, required: true, min_length: 8, max_length: 4096, applies: "restart" }],
  settings: [{ code: "provider", label: "Email provider", selected: "brevo" }], runtime: { enabled: true, managed: "environment", toggle_supported: false, note: "Owned by the environment." },
  store: { name: "managed_with_environment_fallback", writable: true, state: "writable", reason: null },
  health: { status: "healthy", last_tested_at: "2026-10-14T09:00:00", category: "ok", latency_ms: 80 }, test: { supported: true, note: "Sends no email." },
  validation_note: "Live delivery UNVERIFIED.", audit: [] };

async function mock(page: Page, s: St, opts: { role?: string; perms?: string[]; authed?: boolean } = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    const err = (status: number, code: string) => json({ error: { code, message: "server english text", request_id: "r" } }, status);
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      if (!opts.authed) return err(401, "unauthorized");
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: opts.role ?? "user", tier: "basic", status: "active", email_verified: true,
        providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: opts.perms ?? [], response_detail: "brief", interface_locale: "en",
        conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    }
    if (path.endsWith("/auth/register") && method === "POST") { s.registered.push(JSON.parse(route.request().postData() ?? "{}")); return json({ message: "x" }, 201); }
    if (path.endsWith("/auth/verify-email") && method === "POST") return s.verify === "ok" ? json({ message: "Your email is verified." }) : err(400, s.verify);
    if (path.endsWith("/auth/forgot-password") && method === "POST") return json({ message: "x" });
    if (path.endsWith("/auth/reset-password") && method === "POST") return s.reset === "ok" ? json({ message: "ok" }) : err(400, s.reset);
    if (path.endsWith("/auth/verify-email/resend") && method === "POST") return s.resendStatus === 200 ? json({ message: "x" }) : err(s.resendStatus, s.resendStatus === 429 ? "rate_limited" : "email_unavailable");
    if (path.endsWith("/admin/integrations/email_brevo/delivery")) return json(DELIVERY);
    if (path.endsWith("/admin/integrations/email_brevo/test-email") && method === "POST") {
      s.testSent += 1;
      return json({ status: "provider_accepted", failure_category: null, adapter: "brevo", note: "Submitted to the provider. That is not a delivery confirmation: check your inbox." });
    }
    if (/\/admin\/integrations\/email_brevo$/.test(path)) return json(BREVO);
    if (path.endsWith("/admin/integrations")) return json({ items: [BREVO] });
    return json({});
  });
}

test("candidate registration shows a localised neutral outcome and sends the interface language", async ({ page }) => {
  const s = st();
  await mock(page, s);
  await page.goto("/register");
  await page.getByLabel(/^email/i).fill("new@example.test");
  await page.getByLabel(/^password/i).fill("a-long-enough-pass");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByText(/we've sent a verification link/)).toBeVisible();
  expect(s.registered).toHaveLength(1);
  expect((s.registered[0] as { locale: string }).locale).toBe("en");
});

for (const [state, re] of [["ok", /Your email is verified/], ["token_expired", /has expired/], ["token_used", /already used/], ["token_invalid", /invalid or has expired/]] as const) {
  test(`verification link: ${state}`, async ({ page }) => {
    const s = st();
    s.verify = state;
    await mock(page, s);
    await page.goto("/verify-email?token=tok_demo");
    await expect(page.getByText(re).first()).toBeVisible();
    await expect(page.locator("body")).not.toContainText("server english text");
    await expect(page.locator("body")).not.toContainText("tok_demo");
  });
}

test("forgot password then reset: neutral request, success, and distinct expired / used link states", async ({ page }) => {
  const s = st();
  await mock(page, s);
  await page.goto("/forgot-password");
  await page.getByLabel(/email/i).fill("someone@example.test");
  await page.getByRole("button", { name: /send reset link/i }).click();
  await expect(page.getByText(/If an account exists for that email/)).toBeVisible();

  await page.goto("/reset-password?token=tok_demo");
  await page.getByLabel(/new password/i).fill("a-long-enough-pass");
  await page.getByRole("button", { name: /update password/i }).click();
  await expect(page.getByText(/You can now sign in/)).toBeVisible();

  for (const [code, re] of [["token_expired", /expired/], ["token_used", /already used/]] as const) {
    s.reset = code;
    await page.goto("/reset-password?token=tok_demo");
    await page.getByLabel(/new password/i).fill("a-long-enough-pass");
    await page.getByRole("button", { name: /update password/i }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText(re);
  }
});

test("platform admin: Brevo integration shows accepted-not-delivered, then sends one explicit test email to their own address", async ({ page }) => {
  const s = st();
  await mock(page, s, { authed: true, role: "platform_admin", perms: OWNER });
  await page.goto("/admin/integrations/email_brevo");
  await expect(page.getByTestId("email-headline")).toContainText("PROVIDER ACCEPTED A SUBMISSION");
  await expect(page.getByText("Not collected (no delivery events)")).toBeVisible();
  await expect(page.getByText("Unverified", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Send test email to my address" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("your own account address only");
  expect(s.testSent).toBe(0);
  await page.getByRole("alertdialog").getByRole("button", { name: "Send test email" }).click();
  await expect(page.getByTestId("test-email-result")).toContainText("not a delivery confirmation");
  expect(s.testSent).toBe(1);
  expect(await page.locator("body").innerText()).not.toMatch(/token=|@example/);
});

test("operations admin: diagnostics and the test action, but no credential control", async ({ page }) => {
  await mock(page, st(), { authed: true, role: "operations_admin", perms: BASE });
  await page.goto("/admin/integrations/email_brevo");
  await expect(page.getByTestId("email-headline")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send test email to my address" })).toBeVisible();
  await expect(page.getByRole("button", { name: /credential/i })).toHaveCount(0);
});

test("a candidate cannot reach the Brevo integration", async ({ page }) => {
  await mock(page, st(), { authed: true, role: "user", perms: [] });
  await page.goto("/admin/integrations/email_brevo");
  await expect(page.getByTestId("email-headline")).toHaveCount(0);
});

for (const [width, height] of [[1280, 900], [768, 1024], [390, 844]] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`W12.4C responsive: identity pages and the Admin Brevo detail do not overflow at ${width}px (${scheme})`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: scheme });
      const s = st();
      await mock(page, s);
      for (const path of ["/register", "/sign-in", "/forgot-password", "/reset-password?token=tok_demo", "/verify-email?token=tok_demo"]) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(o, `${path} overflow at ${width}px`).toBeLessThanOrEqual(1);
        if (process.env.W124C_SHOTS) await page.screenshot({ path: `${process.env.W124C_SHOTS}/${path.replace(/\W+/g, "_")}-${width}-${scheme}.png`, fullPage: true });
      }
      await page.unroute("**/api/v1/**");
      await mock(page, s, { authed: true, role: "platform_admin", perms: OWNER });
      await page.goto("/admin/integrations/email_brevo");
      await expect(page.getByTestId("email-headline")).toBeVisible();
      const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(o, `brevo detail overflow at ${width}px`).toBeLessThanOrEqual(1);
      if (process.env.W124C_SHOTS) await page.screenshot({ path: `${process.env.W124C_SHOTS}/admin_brevo-${width}-${scheme}.png`, fullPage: true });
    });
  }
}
