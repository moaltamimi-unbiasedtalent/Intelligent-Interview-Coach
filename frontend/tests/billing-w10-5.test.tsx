import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

// P10B-W10.5 Admin MOCK billing UI. MOCK BILLING: NOT LIVE. APIs are mocked; no money, card or provider exists here.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/billing" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { user_id: 7, platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const overview = vi.fn(); const approvals = vi.fn(); const invoices = vi.fn(); const payments = vi.fn(); const refunds = vi.fn(); const customers = vi.fn();
const reqPrice = vi.fn(); const decPrice = vi.fn(); const reqRefund = vi.fn(); const decRefund = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    billing: (...a: unknown[]) => overview(...a), billingApprovals: (...a: unknown[]) => approvals(...a), billingInvoices: (...a: unknown[]) => invoices(...a),
    billingPayments: (...a: unknown[]) => payments(...a), billingRefunds: (...a: unknown[]) => refunds(...a), billingCustomers: (...a: unknown[]) => customers(...a),
    billingRequestPrice: (...a: unknown[]) => reqPrice(...a), billingDecidePrice: (...a: unknown[]) => decPrice(...a),
    billingRequestRefund: (...a: unknown[]) => reqRefund(...a), billingDecideRefund: (...a: unknown[]) => decRefund(...a),
  } },
}));

import { BillingView } from "@/components/admin/BillingView";

const MODE = { provider: "mock", enabled: true, live: false, mode: "mock", label: "MOCK BILLING - NOT LIVE BILLING", configuration_error: null, checkout: false, note: "No live payments are processed." };
const PLAN = { plan_version_id: 3, plan_code: "premium", plan_version: 1, plan_name: "Premium (preview)", plan_status: "active", current: null, configured: false, history: [], pending_approval_id: null };
const CONFIGURED = { ...PLAN, plan_version_id: 2, plan_code: "basic", plan_name: "Basic", configured: true, pending_approval_id: null,
  current: { public_id: "t".repeat(32), version: 2, amount_minor: 1099, currency: "EUR", interval: "month", trial_days: 14, visibility: "public", state: "active", activated_at: null, retired_at: null, approval_id: null },
  history: [{ public_id: "a".repeat(32), version: 2, amount_minor: 1099, currency: "EUR", interval: "month", trial_days: 14, visibility: "public", state: "active", activated_at: null, retired_at: null, approval_id: null },
    { public_id: "b".repeat(32), version: 1, amount_minor: 999, currency: "EUR", interval: "month", trial_days: null, visibility: "internal", state: "retired", activated_at: null, retired_at: null, approval_id: null }] };
const OV = { mode: MODE, stats: { mock: true, label: "x", open_invoices: 1, past_due_invoices: 2, failed_payments: 3, pending_approvals: 1, configured_plan_versions: 1 },
  terms: { items: [CONFIGURED, PLAN], note: "n" } };
const APPROVAL = (o: Record<string, unknown> = {}) => ({ public_id: "p".repeat(32), action_type: "price_change", target_ref: "plan_version:3", proposed: { plan_version_id: 3, amount_minor: 1299, currency: "EUR" },
  reason: "New test terms", status: "pending", requested_by_user_id: 9, requested_by_email: "other@example.com", requested_at: null, decided_by_user_id: null, decided_at: null,
  executed_at: null, execution_ref: null, failure_category: null, ...o });
const PAYMENT = (o: Record<string, unknown> = {}) => ({ public_id: "q".repeat(32), provider: "mock", provider_payment_id: "pay_1", mock: true, invoice_public_id: "i", amount_minor: 2000, currency: "EUR",
  status: "succeeded", failure_category: null, refunded_minor: 500, refundable_minor: 1500, created_at: null, ...o });
const INVOICE = (o: Record<string, unknown> = {}) => ({ public_id: "i".repeat(32), provider: "mock", provider_invoice_id: "inv_1", mock: true, state: "past_due", amount_due_minor: 2000, amount_paid_minor: 0,
  currency: "EUR", subject: { type: "user", id: 5, label: "cand@example.com" }, period_start: null, period_end: null, due_at: null, created_at: null, ...o });
const page = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 25 });

beforeEach(() => {
  mockPerms = ["platform.billing.read", "platform.billing.refund", "platform.plans.price.change"];
  overview.mockResolvedValue(OV);
  approvals.mockResolvedValue(page([APPROVAL(), APPROVAL({ public_id: "r".repeat(32), action_type: "refund", status: "pending", requested_by_user_id: 7, proposed: { amount_minor: 500, currency: "EUR" } })]));
  invoices.mockResolvedValue(page([INVOICE()]));
  payments.mockResolvedValue(page([PAYMENT(), PAYMENT({ public_id: "z".repeat(32), provider_payment_id: "pay_f", status: "failed", failure_category: "declined", refunded_minor: 0, refundable_minor: 0 })]));
  refunds.mockResolvedValue(page([{ public_id: "x", provider: "mock", provider_refund_id: "mock_re_1", mock: true, payment_public_id: "q".repeat(32), amount_minor: 500, currency: "EUR", state: "succeeded", created_at: null, executed_at: null }]));
  customers.mockResolvedValue(page([{ public_id: "c", provider: "mock", provider_customer_id: "cus_1", mock: true, subject: { type: "user", id: 5, label: "cand@example.com" }, state: "active",
    provider_subscriptions: [{ public_id: "s", provider_subscription_id: "sub_1", provider_state: "past_due", plan_version_id: 2, current_period_end: null, grace_until: "2026-12-01" }] }]));
  reqPrice.mockResolvedValue(APPROVAL()); decPrice.mockResolvedValue(APPROVAL({ status: "executed" })); reqRefund.mockResolvedValue(APPROVAL()); decRefund.mockResolvedValue(APPROVAL({ status: "approved" }));
});
afterEach(() => vi.clearAllMocks());

describe("Admin Billing (MOCK)", () => {
  it("states MOCK BILLING / NOT LIVE prominently, provider live=false, no checkout", async () => {
    render(<BillingView />);
    expect(await screen.findByRole("heading", { name: "MOCK BILLING — NOT LIVE BILLING" })).toBeInTheDocument();
    expect(screen.getByText(/No live payments are processed/)).toBeInTheDocument();
    expect(screen.getByText(/live:/).parentElement).toHaveTextContent("live: no");
    expect(screen.getByText(/MockBillingAdapter/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy|subscribe|checkout|upgrade/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/card|cvv|expiry|payment method/i)).not.toBeInTheDocument();
  });

  it("shows a configuration error for a rejected live/production configuration and never says live", async () => {
    overview.mockResolvedValue({ ...OV, mode: { ...MODE, enabled: false, provider: "none", mode: "disabled", label: "BILLING DISABLED", configuration_error: "The mock billing adapter cannot be enabled in a production or live environment." } });
    render(<BillingView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot be enabled in a production or live environment/);
    expect(screen.getByText(/status:/).parentElement).toHaveTextContent("disabled");
  });

  it("commercial terms: unconfigured is never free; configured shows money from minor units, trial as metadata and version history", async () => {
    render(<BillingView />);
    const basic = (await screen.findByRole("rowheader", { name: /Basic \(version 1\)/ })).closest("tr") as HTMLElement;
    expect(within(basic).getByText("10.99 EUR per month")).toBeInTheDocument();
    expect(within(basic).getByText(/14 days \(metadata only\)/)).toBeInTheDocument();
    expect(within(basic).getByText("2")).toBeInTheDocument();
    const premium = screen.getByRole("rowheader", { name: /Premium \(preview\)/ }).closest("tr") as HTMLElement;
    expect(within(premium).getByText(/Not configured \(this is not free\)/)).toBeInTheDocument();
    expect(screen.getByText(/does not charge users and does not change entitlements/)).toBeInTheDocument();
    expect(screen.getByText(/nothing is purchasable/)).toBeInTheDocument();
  });

  it("proposing terms validates minor units, sends integers and states a different admin must approve", async () => {
    const user = userEvent.setup();
    render(<BillingView />);
    await user.click(await screen.findByRole("button", { name: /Propose mock terms for Premium/ }));
    await user.type(screen.getByLabelText(/Amount in minor units/), "10.99");
    await user.type(screen.getByLabelText("Reason"), "Initial test terms");
    await user.click(screen.getByRole("button", { name: "Request approval" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/whole number of minor units/);
    expect(reqPrice).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText(/Amount in minor units/));
    await user.type(screen.getByLabelText(/Amount in minor units/), "1099");
    await user.click(screen.getByRole("button", { name: "Request approval" }));
    await waitFor(() => expect(reqPrice).toHaveBeenCalledWith({ plan_version_id: 3, amount_minor: 1099, currency: "EUR", interval: "month", trial_days: null, visibility: "internal", reason: "Initial test terms" }));
    expect(await screen.findByText(/A different administrator must approve it/)).toBeInTheDocument();
  });

  it("second approval: another admin sees Approve/Reject; the requester sees only 'a second approver is required'", async () => {
    const user = userEvent.setup();
    render(<BillingView />);
    const price = (await screen.findByText("p".repeat(32))).closest("tr") as HTMLElement;
    const own = screen.getByText("r".repeat(32)).closest("tr") as HTMLElement;
    expect(within(own).getByText(/A second approver is required/)).toBeInTheDocument();
    expect(within(own).queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    await user.click(within(price).getByRole("button", { name: "Approve" }));
    const dlg = screen.getByRole("alertdialog");
    expect(within(dlg).getByText(/does not charge users and does not change entitlements/)).toBeInTheDocument();
    expect(within(dlg).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(decPrice).not.toHaveBeenCalled();
    await user.click(within(dlg).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(decPrice).toHaveBeenCalledWith("p".repeat(32), true));
  });

  it("invoices and payments show MOCK labels, states as text, failure category and refundable amounts", async () => {
    render(<BillingView />);
    const inv = (await screen.findByRole("rowheader", { name: "MOCK inv_1" })).closest("tr") as HTMLElement;
    expect(within(inv).getByText("Past due")).toBeInTheDocument();
    expect(within(inv).getByText("cand@example.com")).toBeInTheDocument();
    const failed = screen.getByRole("rowheader", { name: "MOCK pay_f" }).closest("tr") as HTMLElement;
    expect(within(failed).getByText("declined")).toBeInTheDocument();
    expect(within(failed).queryByRole("button", { name: /refund/i })).not.toBeInTheDocument();
    expect(screen.getByText(/A provider subscription state never grants or removes product access/)).toBeInTheDocument();
    expect(screen.getByText(/past due \(grace until 2026-12-01\)/)).toBeInTheDocument();
  });

  it("requesting a mock refund validates against the refundable amount and says no real money moves", async () => {
    const user = userEvent.setup();
    render(<BillingView />);
    await user.click(await screen.findByRole("button", { name: /Request a mock refund for pay_1/ }));
    expect(screen.getAllByText(/Mock refund — no real money moves\./).length).toBeGreaterThan(0);
    await user.type(screen.getByLabelText(/Refund amount in minor units/), "9999");
    await user.type(screen.getByLabelText("Reason"), "Duplicate");
    await user.click(screen.getByRole("button", { name: "Request approval" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot exceed the refundable amount \(15.00 EUR\)/);
    expect(reqRefund).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText(/Refund amount in minor units/));
    await user.type(screen.getByLabelText(/Refund amount in minor units/), "700");
    await user.click(screen.getByRole("button", { name: "Request approval" }));
    await waitFor(() => expect(reqRefund).toHaveBeenCalledWith("q".repeat(32), 700, "Duplicate"));
  });

  it("controls follow permissions only: read-only sees no propose/refund/approve", async () => {
    mockPerms = ["platform.billing.read"];
    render(<BillingView />);
    await screen.findByRole("heading", { name: "MOCK BILLING — NOT LIVE BILLING" });
    for (const n of [/Propose mock terms/, /Request a mock refund/, "Approve", "Reject"]) expect(screen.queryByRole("button", { name: n })).not.toBeInTheDocument();
  });

  it("is hidden without billing.read, and contains no role-name authority, card fields or purchase affordance in code", () => {
    mockPerms = ["platform.users.read"];
    render(<BillingView />);
    expect(overview).not.toHaveBeenCalled();
    const src = readFileSync("components/admin/BillingView.tsx", "utf8");
    expect(src).not.toMatch(/billing_admin|platform_admin|platform_role ===|dangerouslySetInnerHTML/);
    expect(src).not.toMatch(/card_number|cvv|cvc|card_expiry|bank_account|routing_number|payment_method_secret/i);
  });
});

describe("Candidate surfaces stay free of any purchase affordance", () => {
  const walk = (dir: string): string[] => readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? (f === "node_modules" || f === ".next" ? [] : walk(p)) : [p];
  });

  it("no candidate route or component offers checkout, a billing portal, a payment-method form or a buy/subscribe control", () => {
    const routes = walk("app").filter((p) => /page\.tsx$/.test(p) && !p.startsWith(join("app", "admin")));
    expect(routes.filter((p) => /checkout|billing|payment|portal|invoice/i.test(p))).toEqual([]);
    const candidate = walk("components").filter((p) => /\.tsx$/.test(p) && !p.includes(join("components", "admin")));
    for (const f of candidate) {
      const src = readFileSync(f, "utf8");
      expect(src, f).not.toMatch(/\/checkout|billing-portal|payment-method|cardNumber|card_number|type="password"[^>]*cvv/i);
      expect(src, f).not.toMatch(/>\s*(Buy now|Subscribe|Upgrade now|Add payment method)\s*</i);
    }
  });

  it("the candidate plan and export copy states no live payments and offers no checkout, in all 8 locales", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      const a = translate(locale, "plan.noPayments");
      const b = translate(locale, "dataPrivacy.incBillingMock");
      expect(a && !a.startsWith("plan.")).toBeTruthy();
      expect(b && !b.startsWith("dataPrivacy.")).toBeTruthy();
      expect(`${a} ${b}`).not.toMatch(/guarante|garant|GDPR/i);
      if (locale !== "en") { expect(a).not.toBe(translate("en", "plan.noPayments")); expect(b).not.toBe(translate("en", "dataPrivacy.incBillingMock")); }
    }
  });
});
