import { expect, test, type Page } from "@playwright/test";

// W12.4D-C checkout lifecycle UI, mocked at the network layer. Server rules (terms, idempotency, ownership, no entitlement change) are proven by
// tests/test_checkout_w12_4d_c.py. Nothing contacts Stripe: the hosted-checkout host is itself stubbed.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const NONE = { checkout: "none", subscription: "none", payment: "none", confirmation: "not_applicable",
  entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false }, checkout_id: null, created_at: null, expires_at: null };
const FORBIDDEN = /payment (was )?successful|subscription (is )?active|premium (is )?unlocked|thank you for your purchase/i;

async function mock(page: Page, opts: { available: boolean; status?: object; start?: object; startStatus?: number; ret?: object }) {
  const calls: { path: string; body: string | null; key: string | null }[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.includes("/billing/")) calls.push({ path, body: req.postData(), key: req.headers()["idempotency-key"] ?? null });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true,
      providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
      onboarding_completed: true, onboarding_step: 0 });
    if (path.endsWith("/auth/plan")) return json({ plan_code: "basic", plan_version: 1, entitlements: {} });
    if (path.endsWith("/billing/checkout/availability")) return json({ plan: "premium", available: opts.available, reason: opts.available ? null : "not_enabled" });
    if (path.endsWith("/billing/checkout/status")) return json(opts.status ?? NONE);
    if (path.endsWith("/billing/checkout-sessions")) return json(opts.start ?? {}, opts.startStatus ?? 201);
    if (path.endsWith("/billing/checkout-returns")) return json(opts.ret ?? {});
    return json({});
  });
  return calls;
}

test("checkout disabled: truthful message, no purchase button, no success wording", async ({ page }) => {
  await mock(page, { available: false });
  await page.goto("/account");
  await expect(page.getByTestId("checkout-unavailable")).toBeVisible();
  await expect(page.getByTestId("checkout-start")).toHaveCount(0);
  expect(await page.locator("body").innerText()).not.toMatch(FORBIDDEN);
});

test("checkout enabled: sends only the plan code with an idempotency key and redirects to the trusted host", async ({ page }) => {
  const calls = await mock(page, { available: true, start: { checkout_id: "c1", status: "open", redirect_url: "https://checkout.stripe.com/c/pay/cs_test_stub", expires_at: null, browser_returned: false } });
  await page.route("https://checkout.stripe.com/**", (r) => r.fulfill({ status: 200, contentType: "text/html", body: "<title>stub hosted checkout</title>" }));
  await page.goto("/account");
  await page.getByTestId("checkout-start").click();
  await page.waitForURL("https://checkout.stripe.com/**");
  const start = calls.find((c) => c.path.endsWith("/billing/checkout-sessions"))!;
  expect(JSON.parse(start.body!)).toEqual({ plan: "premium" });
  expect(start.key).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
});

test("an untrusted redirect target is refused and the candidate stays on Ask4Mo", async ({ page }) => {
  await mock(page, { available: true, start: { checkout_id: "c1", status: "open", redirect_url: "https://evil.example/pay", expires_at: null, browser_returned: false } });
  await page.goto("/account");
  await page.getByTestId("checkout-start").click();
  await expect(page.getByText("The payment provider could not start checkout.")).toBeVisible();
  expect(new URL(page.url()).hostname).not.toBe("evil.example");
});

test("browser return shows waiting for confirmation, never success", async ({ page }) => {
  await mock(page, { available: false, ret: { checkout_id: "c1", status: "open", redirect_url: null, expires_at: null, browser_returned: true } });
  await page.goto("/billing/return?session=abcdefgh1234&outcome=success");
  await expect(page.getByText("We are waiting for confirmation")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(FORBIDDEN);
});

test("cancel return shows canceled; a missing session is unavailable", async ({ page }) => {
  await mock(page, { available: false, ret: { checkout_id: "c1", status: "canceled", redirect_url: null, expires_at: null, browser_returned: false } });
  await page.goto("/billing/return?session=abcdefgh1234&outcome=cancel");
  await expect(page.getByText("Checkout canceled")).toBeVisible();
  await page.goto("/billing/return");
  await expect(page.getByText("We could not load your checkout status right now.")).toBeVisible();
});

test("account shows the pending state without inventing invoices", async ({ page }) => {
  await mock(page, { available: false, status: { ...NONE, checkout: "open", subscription: "confirmation_pending", payment: "pending", confirmation: "pending" } });
  await page.goto("/account");
  await expect(page.getByText("We are waiting for confirmation")).toBeVisible();
  await expect(page.getByText("No invoices or receipts are shown here")).toBeVisible();
});

const ACTIVE = (granted: boolean) => ({ ...NONE, checkout: "open", subscription: "active", payment: "succeeded", confirmation: "not_applicable",
  entitlement: { plan_code: granted ? "premium" : "basic", source: "entitlement_service", changed_by_billing: granted } });

test("reconciled active subscription: 'confirmed' only when billing actually changed access (W12.4D-D)", async ({ page }) => {
  await mock(page, { available: true, status: ACTIVE(true) });
  await page.goto("/account");
  await expect(page.getByText("Premium subscription confirmed")).toBeVisible();
  await expect(page.getByTestId("checkout-start")).toHaveCount(0);
});

test("reconciled active subscription without an access change makes no access claim", async ({ page }) => {
  await mock(page, { available: true, status: ACTIVE(false) });
  await page.goto("/account");
  await expect(page.getByText("Subscription confirmed by our payment partner")).toBeVisible();
  await expect(page.getByText("Premium subscription confirmed")).toHaveCount(0);
  await expect(page.getByText("Your plan has not changed yet.")).toBeVisible();
});

for (const state of ["past_due", "cancel_scheduled", "canceled"] as const) {
  test(`reconciled ${state} state is shown truthfully`, async ({ page }) => {
    await mock(page, { available: true, status: { ...ACTIVE(true), subscription: state } });
    await page.goto("/account");
    await expect(page.getByTestId("subscription-notice")).toBeVisible();
    expect(await page.locator("body").innerText()).not.toMatch(FORBIDDEN);
  });
}

for (const [name, width, height] of [["desktop", 1280, 900], ["tablet", 768, 1024], ["mobile", 390, 844]] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`responsive ${name} ${scheme}: no horizontal scroll`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: scheme });
      await mock(page, { available: true, status: scheme === "dark" ? ACTIVE(true) : { ...NONE, checkout: "open", subscription: "confirmation_pending", payment: "pending", confirmation: "pending" } });
      await page.goto("/account");
      await expect(page.getByTestId("checkout-panel")).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
      await page.getByTestId("checkout-panel").screenshot({ path: `${process.env.QA_SHOTS || "test-results"}/checkout-${name}-${scheme}.png` });
    });
  }
}
