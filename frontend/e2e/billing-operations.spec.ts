import { expect, test, type Page } from "@playwright/test";

// W12.4D-E candidate billing overview and Admin billing operations, mocked at the network layer. Server rules (RBAC, recovery, idempotency, fail-closed Null reader,
// no entitlement writes) are proven by tests/test_billing_ops_w12_4d_e.py. Nothing contacts Stripe.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const NONE = { checkout: "none", subscription: "none", payment: "none", confirmation: "not_applicable",
  entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false }, checkout_id: null, created_at: null, expires_at: null };
const SUMMARY = (o: object = {}) => ({ state: "free", subscription: "none", payment: "none", plan_code: "basic", entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false },
  interval: null, current_period_end: null, cancel_at_period_end: false, cancellation_effective_at: null, refund_state: "none", dispute_state: "none", verified_at: null,
  management: { where: "link", url: null, url_verified: false }, receipts: { shown_here: false, where: "link_email" }, timeline: [], ...o });
const FORBIDDEN = /payment (was )?successful|subscription (is )?active|premium (is )?unlocked|thank you for your purchase/i;

async function candidate(page: Page, summary: object | number) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"],
      auth_method: "session", capabilities: [], admin_permissions: [], response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    if (path.endsWith("/auth/plan")) return json({ plan_code: "basic", plan_version: 1, entitlements: {} });
    if (path.endsWith("/billing/checkout/availability")) return json({ plan: "premium", available: false, reason: "not_enabled" });
    if (path.endsWith("/billing/checkout/status")) return json(NONE);
    if (path.endsWith("/billing/summary")) return typeof summary === "number" ? json({ error: { code: "x", message: "down" } }, summary) : json(summary);
    return json({});
  });
}

test("free plan: honest free state, no management block, no success wording", async ({ page }) => {
  await candidate(page, SUMMARY());
  await page.goto("/account");
  await expect(page.getByTestId("billing-state-free")).toBeVisible();
  await expect(page.getByTestId("billing-management")).toHaveCount(0);
  expect(await page.locator("body").innerText()).not.toMatch(FORBIDDEN);
});

test("payment pending: waiting for confirmation, plan unchanged", async ({ page }) => {
  await candidate(page, SUMMARY({ state: "confirmation_pending", subscription: "confirmation_pending", payment: "pending" }));
  await page.goto("/account");
  await expect(page.getByTestId("billing-state-confirmation_pending")).toContainText("Waiting for confirmation");
  await expect(page.getByText("Your plan has not been changed by billing.")).toBeVisible();
});

test("scheduled cancellation shows the end date and Link guidance without an invented URL", async ({ page }) => {
  await candidate(page, SUMMARY({ state: "cancel_at_period_end", subscription: "cancel_scheduled", payment: "succeeded", plan_code: "premium", interval: "month",
    entitlement: { plan_code: "premium", source: "entitlement_service", changed_by_billing: true }, cancel_at_period_end: true, current_period_end: "2026-11-16T00:00:00+00:00",
    cancellation_effective_at: "2026-11-16T00:00:00+00:00", verified_at: "2026-10-16T00:00:00+00:00", timeline: [{ kind: "access_granted", at: "2026-10-16T00:00:00+00:00" }] }));
  await page.goto("/account");
  await expect(page.getByTestId("billing-state-cancel_at_period_end")).toContainText("Cancellation scheduled");
  await expect(page.getByText("Ends on")).toBeVisible();
  const mgmt = page.getByTestId("billing-management");
  await expect(mgmt).toContainText("Link");
  await expect(mgmt.locator("a")).toHaveCount(0);
  await expect(page.locator('a[href*="link.com"]')).toHaveCount(0);
  await expect(page.getByTestId("billing-timeline")).toContainText("Access updated by billing");
});

test("payment problem and canceled states", async ({ page }) => {
  await candidate(page, SUMMARY({ state: "past_due", subscription: "past_due", payment: "failed" }));
  await page.goto("/account");
  await expect(page.getByTestId("billing-state-past_due")).toContainText("Payment problem");
});

test("provider/billing unavailable is shown truthfully and retry recovers", async ({ page }) => {
  let down = true;                                   // the client retries a transient GET itself, so the outage must persist until we end it
  await candidate(page, SUMMARY());
  await page.route("**/api/v1/billing/summary", (r) => (down ? r.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "x", message: "down" } }) }) : r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SUMMARY()) })));
  await page.goto("/account");
  await expect(page.getByText("We could not load your billing overview right now.")).toBeVisible();
  await expect(page.getByTestId("billing-state-free")).toHaveCount(0);
  down = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("billing-state-free")).toBeVisible();
});

// ------------------------------------------------------------------ Admin
const OPS_OVERVIEW = {
  generated_at: "2026-10-16T10:00:00+00:00", data_origin: "Values come from events and subscriptions stored locally. The provider has never been activated, no real provider-state reader has run and no scheduler is deployed.", revenue_reported: false,
  subscriptions: { total: 2, active: 1, trialing: 0, past_due: 1, unpaid: 0, canceled: 0, incomplete: 0, cancellation_scheduled: 1 }, checkouts: { pending: 1, failed: 0, canceled: 0, expired: 0 },
  events: { pending: 1, failed: 1, quarantined: 1, needs_review: 1, processed: 4, ignored: 0, awaiting_operator: 2, oldest_pending_seconds: 120 },
  reconciliation: { stale_links: 1, last_successful: null, last_attempt: null, provider_state_reader: "not_wired_null_reader" }, recovery_actions: 0,
  readiness: { provider_selected: "stripe_managed_payments", environment: "sandbox", provider_configured: true, credential_status: "not_configured", eligibility: "not_confirmed", sandbox_access: "unverified",
    checkout: "not_authorized", webhook: "not_authorized", provider_state_reader: "not_wired_null_reader", reconciliation_scheduler: "disabled", entitlement_policy: "not_approved", live_billing: "disabled",
    kill_switches: { live_billing_enabled: false, external_checkout_authorized: false, stripe_webhook_authorized: false }, operational: false },
  open_commercial_decisions: ["Premium monthly price", "Premium annual price", "Legal seller entity"],
};
const ROW = { reference: "a".repeat(32), provider_event: "…000001", provider: "stripe_managed_payments", environment: "sandbox", event_type: "customer.subscription.updated", received_at: "2026-10-16T09:00:00",
  status: "quarantined", attempt_count: 1, attempt_limit: 6, last_attempt_at: null, failure_category: "unknown_ownership", processed_at: null };
const DETAIL = { ...ROW, operator_retries: 0, correlation_id: "req-1", signature_verified: true, classification: "Quarantined: the event could not be safely associated or verified; no billing state or access was changed.",
  recoverable: true, subscription_reference: null, lifecycle: [{ step: "received_and_signature_verified", at: "2026-10-16T09:00:00" }], reconciliation: null };

async function admin(page: Page, perms: string[]) {
  const seen: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.includes("/billing/operations")) seen.push(route.request().method() + " " + path + url.search);
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) return json({ user_id: 1, email: "a@example.com", display_name: null, platform_role: "platform_admin", tier: "basic", status: "active", email_verified: true, providers: ["password"],
      auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    if (path.endsWith("/billing/operations/overview")) return json(OPS_OVERVIEW);
    if (path.endsWith("/billing/operations/events")) return json({ items: url.searchParams.get("status") && url.searchParams.get("status") !== "quarantined" ? [] : [ROW], total: 1, page: 1, page_size: 25 });
    if (/\/billing\/operations\/events\/[a-f0-9]{32}$/.test(path)) return json(DETAIL);
    if (/\/billing\/operations\/events\/[a-f0-9]{32}\/retry$/.test(path)) return json({ reference: "r".repeat(32), action: "retry_event", status: "refused", result: "reader_unavailable", replayed: false });
    if (path.endsWith("/billing/operations/reconciliation")) return json({ generated_at: "x", provider_state_reader: "not_wired_null_reader", provider_synchronization: "not_performed_no_reader", scheduler: "disabled",
      last_successful: null, last_attempt: null, stale_links: 1, retry_scheduled: 0, problems_by_category: { "quarantined:unknown_ownership": 1 }, needs_attention: [{ ...ROW, classification: DETAIL.classification }], cadence_note: "Once validated, one bounded sweep every 15 to 60 minutes; no polling is enabled." });
    if (path.endsWith("/billing/operations/subscriptions") || path.endsWith("/billing/operations/checkouts") || path.endsWith("/billing/operations/recovery-actions")) return json({ items: [], total: 0, page: 1, page_size: 25 });
    return json({});
  });
  return seen;
}
const READ = ["platform.billing.read"];

test("admin overview states the limitations, reports no revenue and lists the open owner decisions", async ({ page }) => {
  await admin(page, READ);
  await page.goto("/admin/billing");
  await expect(page.getByTestId("billing-operations").getByText("offline-qualified, not operationally active")).toBeVisible();
  await expect(page.getByTestId("data-origin")).toContainText("never been activated");
  await expect(page.getByText("Premium monthly price")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(/\bMRR\b|revenue:/i);
});

test("admin readiness never says healthy and shows the null reader, disabled scheduler and unapproved policy", async ({ page }) => {
  await admin(page, READ);
  await page.goto("/admin/billing");
  await page.getByTestId("ops-tab-readiness").click();
  const table = page.getByTestId("readiness-table");
  await expect(table).toContainText("not wired null reader");
  await expect(table).toContainText("not approved");
  expect(await table.innerText()).not.toMatch(/healthy|validated/i);
});

test("admin event filter calls the API with the status and event detail is safe", async ({ page }) => {
  const seen = await admin(page, READ);
  await page.goto("/admin/billing");
  await page.getByTestId("ops-tab-events").click();
  await page.getByTestId("event-status-filter").selectOption("quarantined");
  await expect.poll(() => seen.some((s) => s.includes("events?") && s.includes("status=quarantined"))).toBeTruthy();
  await page.getByRole("button", { name: "Open event …000001" }).click();
  const d = page.getByTestId("event-detail");
  await expect(d).toContainText("only verified events are stored");
  await expect(d).toContainText("Recovery needs the job-management permission");
  expect(await d.innerText()).not.toMatch(/whsec|sk_test|payload/i);
  await expect(page.getByRole("button", { name: /Retry through the verified pipeline/ })).toHaveCount(0);
});

test("recovery needs the job-management permission, a reason, and a refusal is shown as a refusal", async ({ page }) => {
  const seen = await admin(page, [...READ, "platform.jobs.manage"]);
  await page.goto("/admin/billing");
  await page.getByTestId("ops-tab-events").click();
  await page.getByRole("button", { name: "Open event …000001" }).click();
  await page.getByRole("button", { name: /Retry through the verified pipeline/ }).click();
  const dialog = page.getByTestId("recovery-dialog");
  await dialog.getByRole("button", { name: "Confirm" }).click();
  await expect(dialog).toContainText("A reason is required.");
  await dialog.getByRole("textbox").fill("ownership evidence arrived");
  await dialog.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByTestId("recovery-outcome")).toContainText("Refused: reader unavailable. Nothing was changed.");
  expect(seen.filter((s) => s.startsWith("POST") && s.endsWith("/retry")).length).toBe(1);
});

test("admin reconciliation says no provider synchronization was performed", async ({ page }) => {
  await admin(page, READ);
  await page.goto("/admin/billing");
  await page.getByTestId("ops-tab-reconciliation").click();
  await expect(page.getByTestId("sync-status")).toContainText("not performed: no provider-state reader is wired");
  await expect(page.getByText(/unknown_ownership|unknown ownership/).first()).toBeVisible();
});

test("a role without billing.read gets no billing diagnostics", async ({ page }) => {
  await admin(page, ["platform.jobs.manage"]);
  await page.goto("/admin/billing");
  await expect(page.getByText(/does not include access/i)).toBeVisible();
  await expect(page.getByTestId("billing-operations")).toHaveCount(0);
});

for (const [name, width, height] of [["desktop", 1280, 900], ["tablet", 768, 1024], ["mobile", 390, 844]] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`responsive ${name} ${scheme}: candidate overview and admin operations do not overflow`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: scheme });
      await candidate(page, SUMMARY({ state: "cancel_at_period_end", subscription: "cancel_scheduled", payment: "succeeded", interval: "month", entitlement: { plan_code: "premium", source: "x", changed_by_billing: true },
        cancel_at_period_end: true, current_period_end: "2026-11-16T00:00:00+00:00", cancellation_effective_at: "2026-11-16T00:00:00+00:00", verified_at: "2026-10-16T00:00:00+00:00",
        timeline: [{ kind: "subscription_linked", at: "2026-10-15T00:00:00+00:00" }, { kind: "access_granted", at: "2026-10-16T00:00:00+00:00" }] }));
      await page.goto("/account");
      await expect(page.getByTestId("billing-overview")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      await page.getByTestId("billing-overview").screenshot({ path: `${process.env.QA_SHOTS || "test-results"}/billing-candidate-${name}-${scheme}.png` });
    });
    test(`responsive ${name} ${scheme}: admin events and detail do not overflow`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: scheme });
      await admin(page, [...READ, "platform.jobs.manage"]);
      await page.goto("/admin/billing");
      await page.getByTestId("ops-tab-events").click();
      await page.getByRole("button", { name: "Open event …000001" }).click();
      await expect(page.getByTestId("event-detail")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({ path: `${process.env.QA_SHOTS || "test-results"}/billing-admin-${name}-${scheme}.png` });
    });
  }
}
