"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { BillingApproval, BillingPayment, BillingPlanTerms } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { Pager, Panel, PermissionGate, ResourceState, Stat, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";

// MOCK BILLING: NOT LIVE BILLING. Operational metadata only: no card, payment-method, bank, tax or provider-payload data, and nothing here
// changes anyone's access (entitlements stay with the plans and subscriptions). Controls are permission-driven, never role-name-driven.

export function BillingView() {
  return (
    <PermissionGate anyOf={[P.billingRead]}>
      <Body />
    </PermissionGate>
  );
}

/** Amounts are integer minor units; shown assuming two decimal places. */
export const money = (minor: number, currency: string) => `${(minor / 100).toFixed(2)} ${currency}`;
const label = (v: string) => v.replace(/_/g, " ");
const INTERVAL = { month: "per month", year: "per year" } as Record<string, string>;
const STATE: Record<string, string> = {
  pending: "Awaiting second approver", approved: "Approved (queued)", rejected: "Rejected", executed: "Executed", failed: "Failed", cancelled: "Cancelled",
  open: "Open", paid: "Paid", past_due: "Past due", void: "Void", succeeded: "Succeeded",
};

function Body() {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const me = (auth?.account as { user_id?: number } | null | undefined)?.user_id ?? null;
  const canPrice = hasAnyPermission(granted, [P.priceChange]);
  const canRefund = hasAnyPermission(granted, [P.billingRefund]);
  const overview = useAdminResource(() => api.admin.billing(), []);
  const approvals = useAdminResource(() => api.admin.billingApprovals(), []);
  const [invPage, setInvPage] = useState(1);
  const [payPage, setPayPage] = useState(1);
  const invoices = useAdminResource(() => api.admin.billingInvoices(invPage), [invPage]);
  const payments = useAdminResource(() => api.admin.billingPayments(payPage), [payPage]);
  const refunds = useAdminResource(() => api.admin.billingRefunds(), []);
  const customers = useAdminResource(() => api.admin.billingCustomers(), []);
  const [priceFor, setPriceFor] = useState<BillingPlanTerms | null>(null);
  const [refundFor, setRefundFor] = useState<BillingPayment | null>(null);
  const [decision, setDecision] = useState<null | { a: BillingApproval; approve: boolean }>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const reloadAll = () => { overview.reload(); approvals.reload(); payments.reload(); refunds.reload(); invoices.reload(); };

  const decide = async () => {
    if (!decision) return;
    const { a, approve } = decision;
    if (a.action_type === "price_change") await api.admin.billingDecidePrice(a.public_id, approve);
    else await api.admin.billingDecideRefund(a.public_id, approve);
    setNotice(approve ? (a.action_type === "refund" ? "Mock refund approved and queued. No real money moves." : "Approved. New mock commercial terms are active.") : "Request rejected.");
    reloadAll();
  };

  return (
    <div className="grid gap-4">
      <ResourceState loaded={overview}>
        {overview.state === "ready" ? (
          <section aria-labelledby="mock-banner" className="rounded border-2 border-border p-4">
            <h2 id="mock-banner" className="text-lg font-semibold">MOCK BILLING — NOT LIVE BILLING</h2>
            <p className="text-sm">No live payments are processed. There is no checkout, no payment-method collection, no card data and no tax engine. Billing records here are simulated metadata and never change anyone&apos;s access.</p>
            <p className="text-sm">
              Provider: <strong>{overview.data.mode.provider === "none" ? "none" : "MockBillingAdapter"}</strong> · live: <strong>{overview.data.mode.live ? "yes" : "no"}</strong> ·
              status: <strong>{overview.data.mode.enabled ? "mock enabled (development or test only)" : "disabled"}</strong>
            </p>
            {overview.data.mode.configuration_error ? <p role="alert" className="text-sm">{overview.data.mode.configuration_error}</p> : null}
          </section>
        ) : null}
      </ResourceState>
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}
      <ResourceState loaded={overview}>
        {overview.state === "ready" ? (
          <>
            <Panel title="Overview (mock)">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Open mock invoices" value={overview.data.stats.open_invoices} />
                <Stat label="Past-due mock invoices" value={overview.data.stats.past_due_invoices} />
                <Stat label="Failed mock payments" value={overview.data.stats.failed_payments} />
                <Stat label="Pending approvals" value={overview.data.stats.pending_approvals} />
              </div>
            </Panel>
            <Panel title="Commercial terms (mock)">
              <p className="text-xs text-muted">Changing mock commercial terms does not charge users and does not change entitlements. A plan version with no terms is unconfigured, which is not the same as free. &quot;Public&quot; means catalogue visibility only; nothing is purchasable.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Commercial terms per plan version</caption>
                  <thead><tr className="text-xs text-muted">{["Plan version", "Status", "Current terms", "Trial", "Visibility", "Versions", ""].map((c, i) => <th key={i} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {overview.data.terms.items.map((t) => (
                      <tr key={t.plan_version_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">{t.plan_name} (version {t.plan_version})</th>
                        <td className="py-1 pr-4">{t.plan_status}</td>
                        <td className="py-1 pr-4">{t.current ? `${money(t.current.amount_minor, t.current.currency)} ${INTERVAL[t.current.interval] ?? t.current.interval}` : "Not configured (this is not free)"}</td>
                        <td className="py-1 pr-4">{t.current?.trial_days ? `${t.current.trial_days} days (metadata only)` : "None"}</td>
                        <td className="py-1 pr-4">{t.current?.visibility ?? "None"}</td>
                        <td className="py-1 pr-4">{t.history.length}{t.pending_approval_id ? " (change pending)" : ""}</td>
                        <td className="py-1 pr-4">
                          {canPrice && t.plan_status !== "retired" && !t.pending_approval_id ? (
                            <button type="button" className={btn} onClick={() => setPriceFor(t)} aria-label={`Propose mock terms for ${t.plan_name} version ${t.plan_version}`}>Propose terms</button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </>
        ) : null}
      </ResourceState>
      <ResourceState loaded={approvals}>
        {approvals.state === "ready" ? (
          <Panel title="Approval requests">
            {approvals.data.items.length === 0 ? <p className="text-sm text-muted">No approval requests.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Billing approval requests</caption>
                  <thead><tr className="text-xs text-muted">{["Request", "Action", "Proposal", "Requested by", "Status", ""].map((c, i) => <th key={i} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {approvals.data.items.map((a) => {
                      const own = a.requested_by_user_id !== null && a.requested_by_user_id === me;
                      const may = a.action_type === "price_change" ? canPrice : canRefund;
                      return (
                        <tr key={a.public_id} className="border-t border-default">
                          <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">{a.public_id}</th>
                          <td className="py-1 pr-4">{a.action_type === "refund" ? "Mock refund" : "Commercial terms"}</td>
                          <td className="py-1 pr-4">{money(Number(a.proposed.amount_minor ?? 0), String(a.proposed.currency ?? ""))}{a.reason ? `: ${a.reason}` : ""}</td>
                          <td className="py-1 pr-4">{a.requested_by_email ?? `Account ${a.requested_by_user_id ?? "removed"}`}</td>
                          <td className="py-1 pr-4"><StatusLabel tone={a.status === "executed" ? "ok" : a.status === "failed" || a.status === "rejected" ? "warn" : "neutral"}>{STATE[a.status] ?? a.status}</StatusLabel></td>
                          <td className="py-1 pr-4">
                            {a.status === "pending" && may ? (own ? <span className="text-xs text-muted">A second approver is required</span> : (
                              <span className="flex gap-2">
                                <button type="button" className={btn} onClick={() => setDecision({ a, approve: true })}>Approve</button>
                                <button type="button" className={btn} onClick={() => setDecision({ a, approve: false })}>Reject</button>
                              </span>
                            )) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        ) : null}
      </ResourceState>
      <ResourceState loaded={invoices}>
        {invoices.state === "ready" ? (
          <Panel title="Mock invoices">
            {invoices.data.items.length === 0 ? <p className="text-sm text-muted">No mock invoices.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Mock invoices</caption>
                  <thead><tr className="text-xs text-muted">{["Invoice", "Account", "State", "Due", "Paid", "Created"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {invoices.data.items.map((i) => (
                      <tr key={i.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">MOCK {i.provider_invoice_id}</th>
                        <td className="py-1 pr-4">{i.subject.label ?? `${i.subject.type} ${i.subject.id}`}</td>
                        <td className="py-1 pr-4"><StatusLabel tone={i.state === "paid" ? "ok" : i.state === "past_due" ? "warn" : "neutral"}>{STATE[i.state] ?? i.state}</StatusLabel></td>
                        <td className="py-1 pr-4">{money(i.amount_due_minor, i.currency)}</td>
                        <td className="py-1 pr-4">{money(i.amount_paid_minor, i.currency)}</td>
                        <td className="py-1 pr-4">{i.created_at ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pager page={invoices.data.page} pageSize={invoices.data.page_size} total={invoices.data.total} onPage={setInvPage} />
          </Panel>
        ) : null}
      </ResourceState>
      <ResourceState loaded={payments}>
        {payments.state === "ready" ? (
          <Panel title="Mock payments">
            {payments.data.items.length === 0 ? <p className="text-sm text-muted">No mock payments.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Mock payments</caption>
                  <thead><tr className="text-xs text-muted">{["Payment", "Status", "Amount", "Refunded", "Refundable", "Problem", ""].map((c, i) => <th key={i} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {payments.data.items.map((p) => (
                      <tr key={p.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">MOCK {p.provider_payment_id}</th>
                        <td className="py-1 pr-4"><StatusLabel tone={p.status === "succeeded" ? "ok" : p.status === "failed" ? "warn" : "neutral"}>{STATE[p.status] ?? p.status}</StatusLabel></td>
                        <td className="py-1 pr-4">{money(p.amount_minor, p.currency)}</td>
                        <td className="py-1 pr-4">{money(p.refunded_minor, p.currency)}</td>
                        <td className="py-1 pr-4">{money(p.refundable_minor, p.currency)}</td>
                        <td className="py-1 pr-4">{p.failure_category ? label(p.failure_category) : "None"}</td>
                        <td className="py-1 pr-4">
                          {canRefund && p.status === "succeeded" && p.refundable_minor > 0 ? (
                            <button type="button" className={btn} onClick={() => setRefundFor(p)} aria-label={`Request a mock refund for ${p.provider_payment_id}`}>Request mock refund</button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pager page={payments.data.page} pageSize={payments.data.page_size} total={payments.data.total} onPage={setPayPage} />
          </Panel>
        ) : null}
      </ResourceState>
      <ResourceState loaded={refunds}>
        {refunds.state === "ready" ? (
          <Panel title="Mock refunds">
            <p className="text-xs text-muted">Mock refund — no real money moves.</p>
            {refunds.data.items.length === 0 ? <p className="text-sm text-muted">No mock refunds.</p> : (
              <ul className="grid gap-1 text-sm">
                {refunds.data.items.map((r) => (
                  <li key={r.public_id}>MOCK refund of {money(r.amount_minor, r.currency)} on {r.payment_public_id}: <StatusLabel tone={r.state === "succeeded" ? "ok" : r.state === "failed" ? "warn" : "neutral"}>{r.state === "succeeded" ? "Executed" : r.state === "failed" ? "Failed" : "Pending"}</StatusLabel></li>
                ))}
              </ul>
            )}
          </Panel>
        ) : null}
      </ResourceState>
      <ResourceState loaded={customers}>
        {customers.state === "ready" ? (
          <Panel title="Provider customers and subscriptions (mock, informational)">
            <p className="text-xs text-muted">A provider subscription state never grants or removes product access.</p>
            {customers.data.items.length === 0 ? <p className="text-sm text-muted">No mock customers.</p> : (
              <ul className="grid gap-1 text-sm">
                {customers.data.items.map((c) => (
                  <li key={c.public_id}>{c.subject.label ?? `${c.subject.type} ${c.subject.id}`}: {c.provider_subscriptions.length === 0 ? "no provider subscription" : c.provider_subscriptions.map((s) => `${label(s.provider_state)}${s.grace_until ? ` (grace until ${s.grace_until})` : ""}`).join(", ")}</li>
                ))}
              </ul>
            )}
          </Panel>
        ) : null}
      </ResourceState>
      {priceFor ? <PriceDialog plan={priceFor} onClose={() => setPriceFor(null)} onDone={() => { setNotice("Request recorded. A different administrator must approve it."); reloadAll(); }} /> : null}
      {refundFor ? <RefundDialog payment={refundFor} onClose={() => setRefundFor(null)} onDone={() => { setNotice("Request recorded. A different administrator must approve it."); reloadAll(); }} /> : null}
      <ActionDialog open={decision !== null} title={decision ? `${decision.approve ? "Approve" : "Reject"} this ${decision.a.action_type === "refund" ? "mock refund" : "terms change"}?` : ""}
        confirmLabel={decision?.approve ? "Approve" : "Reject"} askReason={false} onConfirm={decide} onClose={() => setDecision(null)}>
        <p className="text-sm">{decision?.a.action_type === "refund" ? "Mock refund — no real money moves, and nobody's access changes." : "This creates a new immutable version of the mock terms. It does not charge users and does not change entitlements."}</p>
      </ActionDialog>
    </div>
  );
}

function PriceDialog({ plan, onClose, onDone }: { plan: BillingPlanTerms; onClose: () => void; onDone: () => void }) {
  const [v, setV] = useState({ amount: "", currency: "EUR", interval: "month", trial: "", visibility: "internal", reason: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!/^\d{1,9}$/.test(v.amount)) return setError("Enter the amount as a whole number of minor units (for example 1099 for 10.99).");
    if (v.trial && !/^\d{1,3}$/.test(v.trial)) return setError("Trial days must be a whole number.");
    setBusy(true);
    try {
      await api.admin.billingRequestPrice({ plan_version_id: plan.plan_version_id, amount_minor: Number(v.amount), currency: v.currency.trim().toUpperCase(),
        interval: v.interval, trial_days: v.trial ? Number(v.trial) : null, visibility: v.visibility, reason: v.reason.trim() });
      onDone();
      onClose();
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel title={`Propose mock terms: ${plan.plan_name} (version ${plan.plan_version})`}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" aria-label="Propose mock commercial terms">
        <label className="grid gap-1 text-xs text-muted">Amount in minor units
          <input className={field} inputMode="numeric" value={v.amount} onChange={set("amount")} required />
        </label>
        <label className="grid gap-1 text-xs text-muted">Currency (three letters, metadata only)
          <input className={field} value={v.currency} onChange={set("currency")} maxLength={3} required />
        </label>
        <label className="grid gap-1 text-xs text-muted">Billing interval
          <select className={field} value={v.interval} onChange={set("interval")}><option value="month">Month</option><option value="year">Year</option></select>
        </label>
        <label className="grid gap-1 text-xs text-muted">Trial days (optional, metadata only)
          <input className={field} inputMode="numeric" value={v.trial} onChange={set("trial")} />
        </label>
        <label className="grid gap-1 text-xs text-muted">Visibility (catalogue only; nothing is purchasable)
          <select className={field} value={v.visibility} onChange={set("visibility")}><option value="public">Public</option><option value="private">Private</option><option value="internal">Internal</option></select>
        </label>
        <label className="grid gap-1 text-xs text-muted">Reason
          <input className={field} value={v.reason} onChange={set("reason")} maxLength={300} required />
        </label>
        <div className="sm:col-span-2 grid gap-2">
          <p className="text-xs text-muted">Changing mock commercial terms does not charge users and does not change entitlements. A different administrator must approve.</p>
          {error ? <p role="alert" className="text-sm">{error}</p> : null}
          <div className="flex gap-3"><button type="submit" className={btn} disabled={busy}>Request approval</button><button type="button" className={btn} onClick={onClose}>Cancel</button></div>
        </div>
      </form>
    </Panel>
  );
}

function RefundDialog({ payment, onClose, onDone }: { payment: BillingPayment; onClose: () => void; onDone: () => void }) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!/^\d{1,9}$/.test(amount) || Number(amount) < 1) return setError("Enter the refund as a whole number of minor units, at least 1.");
    if (Number(amount) > payment.refundable_minor) return setError(`The refund cannot exceed the refundable amount (${money(payment.refundable_minor, payment.currency)}).`);
    setBusy(true);
    try {
      await api.admin.billingRequestRefund(payment.public_id, Number(amount), reason.trim());
      onDone();
      onClose();
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel title={`Request a mock refund for ${payment.provider_payment_id}`}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" aria-label="Request a mock refund">
        <p className="sm:col-span-2 text-sm">Original amount {money(payment.amount_minor, payment.currency)}; refundable {money(payment.refundable_minor, payment.currency)}. Mock refund — no real money moves.</p>
        <label className="grid gap-1 text-xs text-muted">Refund amount in minor units ({payment.currency})
          <input className={field} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </label>
        <label className="grid gap-1 text-xs text-muted">Reason
          <input className={field} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} required />
        </label>
        <div className="sm:col-span-2 grid gap-2">
          {error ? <p role="alert" className="text-sm">{error}</p> : null}
          <div className="flex gap-3"><button type="submit" className={btn} disabled={busy}>Request approval</button><button type="button" className={btn} onClick={onClose}>Cancel</button></div>
        </div>
      </form>
    </Panel>
  );
}
