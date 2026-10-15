import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import en from "@/lib/i18n/messages/w124de/en";

let perms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push() {}, replace() {} }), usePathname: () => "/admin/billing", useSearchParams: () => new URLSearchParams() }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: perms }, status: "authenticated" }),
}));

const summary = vi.fn();
const overview = vi.fn();
const events = vi.fn();
const event = vi.fn();
const recover = vi.fn();
const reconciliation = vi.fn();
const subscriptions = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    billing: { summary: (...a: unknown[]) => summary(...a) },
    admin: { billingOps: {
      overview: (...a: unknown[]) => overview(...a), events: (...a: unknown[]) => events(...a), event: (...a: unknown[]) => event(...a), recover: (...a: unknown[]) => recover(...a),
      reconciliation: (...a: unknown[]) => reconciliation(...a), subscriptions: (...a: unknown[]) => subscriptions(...a), checkouts: vi.fn(), recoveryActions: vi.fn(),
    } },
  },
  ApiError: class ApiError extends Error {},
}));

import { BillingOverview } from "@/components/account/BillingOverview";
import { BillingOperationsView } from "@/components/admin/BillingOperationsView";

const wrap = (ui: React.ReactNode) => render(<I18nProvider>{ui}</I18nProvider>);
const FORBIDDEN = /payment (was )?successful|subscription (is )?active|premium (is )?unlocked|thank you for your purchase|you are now premium/i;
const base = { state: "free", subscription: "none", payment: "none", plan_code: "basic", entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false },
  interval: null, current_period_end: null, cancel_at_period_end: false, cancellation_effective_at: null, refund_state: "none", dispute_state: "none", verified_at: null,
  management: { where: "link", url: null, url_verified: false }, receipts: { shown_here: false, where: "link_email" }, timeline: [] };

beforeEach(() => { vi.clearAllMocks(); perms = []; });

describe("candidate billing overview (verified local state only)", () => {
  const STATES = ["free", "checkout_pending", "confirmation_pending", "trialing", "active", "cancel_at_period_end", "past_due", "canceled", "expired", "refunded", "disputed"] as const;
  it.each(STATES)("renders the %s state with its own title and no success claim", async (state) => {
    summary.mockResolvedValue({ ...base, state, subscription: state === "active" ? "active" : "none", interval: "month" });
    wrap(<BillingOverview />);
    expect(await screen.findByTestId(`billing-state-${state}`)).toBeInTheDocument();
    expect(within(screen.getByTestId(`billing-state-${state}`)).getByText((en.billing as Record<string, string>)[`state_${state}`])).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(FORBIDDEN);
  });

  it("free and checkout-pending users see no management block and no timeline claims", async () => {
    summary.mockResolvedValue({ ...base, state: "checkout_pending" });
    wrap(<BillingOverview />);
    await screen.findByTestId("billing-overview");
    expect(screen.queryByTestId("billing-management")).toBeNull();
  });

  it("a paid user gets Link guidance WITHOUT an invented URL and WITHOUT invoices", async () => {
    summary.mockResolvedValue({ ...base, state: "active", subscription: "active", payment: "succeeded", interval: "month", verified_at: "2026-10-16T00:00:00+00:00",
      current_period_end: "2026-11-16T00:00:00+00:00", entitlement: { plan_code: "premium", source: "entitlement_service", changed_by_billing: true } });
    wrap(<BillingOverview />);
    const box = await screen.findByTestId("billing-management");
    expect(within(box).getByText(en.billing.manageBody)).toBeInTheDocument();
    expect(box.querySelector("a")).toBeNull();
    expect(document.querySelector('a[href*="link.com"]')).toBeNull();
    expect(screen.queryByText(/invoice #|download invoice|invoice history/i)).toBeNull();
    expect(screen.getByText(en.billing.accessByBilling)).toBeInTheDocument();
  });

  it("access is reported as unchanged when billing did not change it (payment, subscription and access stay separate)", async () => {
    summary.mockResolvedValue({ ...base, state: "active", subscription: "active", payment: "succeeded", interval: "year" });
    wrap(<BillingOverview />);
    expect(await screen.findByText(en.billing.accessNotByBilling)).toBeInTheDocument();
    expect(screen.getByText(en.billing.intervalYear)).toBeInTheDocument();
  });

  it("a scheduled cancellation shows the effective date and is not shown as ended", async () => {
    summary.mockResolvedValue({ ...base, state: "cancel_at_period_end", subscription: "cancel_scheduled", cancel_at_period_end: true, interval: "month",
      current_period_end: "2026-11-16T00:00:00+00:00", cancellation_effective_at: "2026-11-16T00:00:00+00:00", entitlement: { plan_code: "premium", source: "x", changed_by_billing: true } });
    wrap(<BillingOverview />);
    expect(await screen.findByText(en.billing.lblEndsOn)).toBeInTheDocument();
    expect(screen.queryByText(en.billing.state_canceled)).toBeNull();
  });

  it("the timeline lists only bounded, verified event kinds", async () => {
    summary.mockResolvedValue({ ...base, state: "active", subscription: "active", timeline: [{ kind: "access_granted", at: "2026-10-16T00:00:00+00:00" }, { kind: "checkout_started", at: "2026-10-15T00:00:00+00:00" }] });
    wrap(<BillingOverview />);
    const tl = await screen.findByTestId("billing-timeline");
    expect(within(tl).getByText(new RegExp(en.billing.tl_access_granted))).toBeInTheDocument();
  });

  it("an unavailable billing service is shown truthfully (never as free or active) and can be retried", async () => {
    summary.mockRejectedValueOnce(new Error("down")).mockResolvedValue({ ...base });
    wrap(<BillingOverview />);
    expect(await screen.findByText(en.billing.loadError)).toBeInTheDocument();
    expect(screen.queryByTestId("billing-state-free")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: en.billing.retry }));
    expect(await screen.findByTestId("billing-state-free")).toBeInTheDocument();
  });

  it("every candidate billing string exists in all eight locales and none claims success or carries the slogan", () => {
    for (const loc of SUPPORTED_LOCALE_CODES) {
      for (const key of Object.keys(en.billing)) {
        const v = translate(loc, `billing.${key}`);
        expect(v, `${loc}.${key}`).toBeTruthy();
        expect(v).not.toBe(`billing.${key}`);
        expect(v).not.toMatch(/Ask More\. Be More\./);
      }
    }
    for (const v of Object.values(en.billing)) expect(v).not.toMatch(FORBIDDEN);
  });
});

const OPS = {
  generated_at: "2026-10-16T10:00:00+00:00", data_origin: "Values come from events and subscriptions stored locally. The provider has never been activated.", revenue_reported: false,
  subscriptions: { total: 2, active: 1, trialing: 0, past_due: 1, unpaid: 0, canceled: 0, incomplete: 0, cancellation_scheduled: 1 }, checkouts: { pending: 1, failed: 0, canceled: 0, expired: 0 },
  events: { pending: 1, failed: 1, quarantined: 1, needs_review: 1, processed: 4, ignored: 0, awaiting_operator: 2, oldest_pending_seconds: 120 },
  reconciliation: { stale_links: 1, last_successful: null, last_attempt: null, provider_state_reader: "not_wired_null_reader" }, recovery_actions: 0,
  readiness: { provider_selected: "stripe_managed_payments", environment: "sandbox", provider_configured: true, credential_status: "not_configured", eligibility: "not_confirmed", sandbox_access: "unverified",
    checkout: "not_authorized", webhook: "not_authorized", provider_state_reader: "not_wired_null_reader", reconciliation_scheduler: "disabled", entitlement_policy: "not_approved", live_billing: "disabled",
    kill_switches: { live_billing_enabled: false, external_checkout_authorized: false }, operational: false },
  open_commercial_decisions: ["Premium monthly price", "Legal seller entity"],
};
const EVENT_ROW = { reference: "a".repeat(32), provider_event: "…000001", provider: "stripe_managed_payments", environment: "sandbox", event_type: "customer.subscription.updated", received_at: "2026-10-16T09:00:00",
  status: "quarantined", attempt_count: 1, attempt_limit: 6, last_attempt_at: null, failure_category: "unknown_ownership", processed_at: null };
const DETAIL = { ...EVENT_ROW, operator_retries: 0, correlation_id: "req-1", signature_verified: true, classification: "Quarantined: the event could not be safely associated or verified; no billing state or access was changed.",
  recoverable: true, subscription_reference: null, lifecycle: [{ step: "received_and_signature_verified", at: "2026-10-16T09:00:00" }], reconciliation: null };

describe("Admin billing operations", () => {
  const open = async (tab: string) => { overview.mockResolvedValue(OPS); wrap(<BillingOperationsView />); await userEvent.click(await screen.findByTestId(`ops-tab-${tab}`)); };

  it("is gated by the billing-read permission, not by a role name", () => {
    perms = ["platform.jobs.manage"];
    wrap(<BillingOperationsView />);
    expect(screen.getByText(/does not include access/i)).toBeInTheDocument();
    expect(screen.queryByTestId("billing-operations")).toBeNull();
  });

  it("states the operational limitations up front and reports no revenue", async () => {
    perms = ["platform.billing.read"];
    overview.mockResolvedValue(OPS);
    wrap(<BillingOperationsView />);
    expect(await screen.findByText(/offline-qualified, not operationally active/i)).toBeInTheDocument();
    expect(await screen.findByTestId("data-origin")).toHaveTextContent("never been activated");
    expect(screen.getByText("Premium monthly price")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/revenue:|MRR|\$\d/i);
  });

  it("readiness reports the null reader, disabled scheduler and unapproved policy as warnings, never as healthy", async () => {
    perms = ["platform.billing.read"];
    await open("readiness");
    const table = await screen.findByTestId("readiness-table");
    expect(within(table).getByText("not wired null reader")).toBeInTheDocument();
    expect(within(table).getAllByText("disabled").length).toBeGreaterThanOrEqual(2);              // the scheduler and live billing
    expect(within(table).getByText("not approved")).toBeInTheDocument();
    expect(table.textContent).not.toMatch(/healthy|validated|ready to take payments/i);
  });

  it("filters events by status through the API and opens a safe detail view", async () => {
    perms = ["platform.billing.read"];
    events.mockResolvedValue({ items: [EVENT_ROW], total: 1, page: 1, page_size: 25 });
    event.mockResolvedValue(DETAIL);
    await open("events");
    await userEvent.selectOptions(await screen.findByTestId("event-status-filter"), "quarantined");
    await waitFor(() => expect(events).toHaveBeenLastCalledWith(1, "quarantined"));
    await userEvent.click(await screen.findByRole("button", { name: /Open event …000001/ }));
    const d = await screen.findByTestId("event-detail");
    expect(within(d).getByText(/only verified events are stored/)).toBeInTheDocument();
    expect(d.textContent).not.toMatch(/whsec|sk_test|payload|@/);
    expect(within(d).getByText(/Recovery needs the job-management permission/)).toBeInTheDocument();
  });

  it("recovery needs the job-management permission, a reason, and shows a refusal truthfully", async () => {
    perms = ["platform.billing.read", "platform.jobs.manage"];
    events.mockResolvedValue({ items: [EVENT_ROW], total: 1, page: 1, page_size: 25 });
    event.mockResolvedValue(DETAIL);
    recover.mockResolvedValue({ reference: "r".repeat(32), action: "retry_event", status: "refused", result: "reader_unavailable", replayed: false });
    await open("events");
    await userEvent.click(await screen.findByRole("button", { name: /Open event …000001/ }));
    await userEvent.click(await screen.findByRole("button", { name: /Retry through the verified pipeline/ }));
    const dialog = await screen.findByTestId("recovery-dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
    expect(await within(dialog).findByText("A reason is required.")).toBeInTheDocument();
    expect(recover).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByRole("textbox"), "ownership evidence arrived");
    await userEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(recover).toHaveBeenCalledTimes(1));
    expect(recover.mock.calls[0][0]).toBe("retry");
    expect(recover.mock.calls[0][3]).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(await screen.findByTestId("recovery-outcome")).toHaveTextContent("Refused: reader unavailable. Nothing was changed.");
    expect(screen.getByTestId("recovery-outcome").textContent).not.toMatch(/completed|success/i);
  });

  it("reconciliation says no provider synchronization was performed while no reader is wired", async () => {
    perms = ["platform.billing.read"];
    reconciliation.mockResolvedValue({ generated_at: "x", provider_state_reader: "not_wired_null_reader", provider_synchronization: "not_performed_no_reader", scheduler: "disabled", last_successful: null, last_attempt: null,
      stale_links: 1, retry_scheduled: 0, problems_by_category: { "quarantined:unknown_ownership": 1 }, needs_attention: [{ ...EVENT_ROW, classification: DETAIL.classification }], cadence_note: "Once validated, one bounded sweep every 15 to 60 minutes; no polling is enabled." });
    await open("reconciliation");
    expect(await screen.findByTestId("sync-status")).toHaveTextContent("not performed: no provider-state reader is wired");
    expect(screen.getByText(/quarantined:unknown ownership|quarantined unknown_ownership|quarantined:unknown_ownership/i)).toBeTruthy();
  });

  it("the subscriptions list requests the selected lifecycle state", async () => {
    perms = ["platform.billing.read"];
    subscriptions.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    await open("subscriptions");
    await userEvent.selectOptions(await screen.findByRole("combobox"), "past_due");
    await waitFor(() => expect(subscriptions).toHaveBeenLastCalledWith(1, "past_due"));
  });
});
