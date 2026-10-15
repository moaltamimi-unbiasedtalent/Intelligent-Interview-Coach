"use client";

import { useRef, useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { BillingOpsPage, BillingOpsReadiness } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { Pager, Panel, PermissionGate, ResourceState, Stat, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";

// Billing OPERATIONS (W12.4D-E): every value comes from the verified local billing domain. Provider ids are masked, nothing here shows a raw payload, a signature,
// a secret or a card detail, and nothing reports revenue. Recovery actions only re-drive the existing verified pipeline for one of OUR records; with the runtime
// provider-state reader not wired they are refused, and this screen says so. Controls are permission-driven, never role-name-driven.

const label = (v: unknown) => String(v ?? "-").replace(/_/g, " ");
const when = (v: unknown) => (v ? String(v).replace("T", " ").slice(0, 19) + " UTC" : "Never");
const SECTIONS = [["overview", "Overview"], ["subscriptions", "Subscriptions"], ["checkouts", "Checkout sessions"], ["events", "Webhook events"], ["reconciliation", "Reconciliation"],
  ["recovery", "Audit history"], ["readiness", "Readiness"]] as const;
type Section = (typeof SECTIONS)[number][0];
const EVENT_STATUSES = ["received", "processing", "processed", "failed", "quarantined", "needs_review", "ignored"];
const SUB_STATES = ["incomplete", "trialing", "active", "past_due", "unpaid", "paused", "canceled", "incomplete_expired"];
const CHECKOUT_STATUSES = ["pending_creation", "open", "canceled", "expired", "failed"];

export function BillingOperationsView() {
  return (
    <PermissionGate anyOf={[P.billingRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const [section, setSection] = useState<Section>("overview");
  return (
    <div className="grid gap-4" data-testid="billing-operations">
      <section aria-labelledby="ops-banner" className="rounded border-2 border-border p-4">
        <h2 id="ops-banner" className="text-lg font-semibold">Provider billing operations: offline-qualified, not operationally active</h2>
        <p className="text-sm">Values below come from events and subscriptions stored locally. The provider has never been activated, the real provider-state reader is not wired, no scheduler is deployed and no paid entitlement policy is approved. No revenue is reported.</p>
      </section>
      <nav aria-label="Billing operations sections" className="flex flex-wrap gap-2">
        {SECTIONS.map(([id, text]) => (
          <button key={id} type="button" className={btn} aria-pressed={section === id} onClick={() => setSection(id)} data-testid={`ops-tab-${id}`}>{text}</button>
        ))}
      </nav>
      {section === "overview" ? <Overview /> : null}
      {section === "subscriptions" ? <Subscriptions /> : null}
      {section === "checkouts" ? <Checkouts /> : null}
      {section === "events" ? <Events /> : null}
      {section === "reconciliation" ? <Reconciliation /> : null}
      {section === "recovery" ? <History /> : null}
      {section === "readiness" ? <Readiness /> : null}
    </div>
  );
}

const UNUSABLE = <p className="text-sm text-muted" role="alert">That request could not be processed.</p>;

function Overview() {
  const o = useAdminResource(() => api.admin.billingOps.overview(), []);
  return (
    <ResourceState loaded={o}>
      {o.state === "ready" && !(o.data?.subscriptions && o.data.events && o.data.reconciliation) ? UNUSABLE : null}
      {o.state === "ready" && o.data?.subscriptions && o.data.events && o.data.reconciliation ? (
        <>
          <Panel title="Provider-managed subscriptions">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total" value={o.data.subscriptions.total} /><Stat label="Active" value={o.data.subscriptions.active} />
              <Stat label="Past due" value={o.data.subscriptions.past_due} /><Stat label="Canceled" value={o.data.subscriptions.canceled} />
              <Stat label="Cancellation scheduled" value={o.data.subscriptions.cancellation_scheduled} /><Stat label="Pending checkouts" value={o.data.checkouts.pending} />
            </div>
          </Panel>
          <Panel title="Webhook processing">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Pending" value={o.data.events.pending} /><Stat label="Failed (retrying)" value={o.data.events.failed} />
              <Stat label="Quarantined" value={o.data.events.quarantined} /><Stat label="Needs review" value={o.data.events.needs_review} />
              <Stat label="Awaiting operator" value={o.data.events.awaiting_operator} /><Stat label="Stale subscriptions" value={o.data.reconciliation.stale_links} />
            </div>
            <p className="text-xs text-muted">Last successful reconciliation: {when(o.data.reconciliation.last_successful)} · last attempt: {when(o.data.reconciliation.last_attempt)} · data generated {when(o.data.generated_at)}</p>
            <p className="text-xs text-muted" data-testid="data-origin">{o.data.data_origin}</p>
          </Panel>
          <Panel title="Open owner decisions (not decided, not invented)">
            <ul className="grid gap-1 text-sm sm:grid-cols-2">{o.data.open_commercial_decisions.map((d) => <li key={d}>{d}</li>)}</ul>
          </Panel>
        </>
      ) : null}
    </ResourceState>
  );
}

function List({ page, cols, caption }: { page: BillingOpsPage; cols: [string, string][]; caption: string }) {
  if (!page?.items || page.items.length === 0) return <p className="text-sm text-muted">Nothing to show.</p>;
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead><tr className="text-xs text-muted">{cols.map(([, h]) => <th key={h} scope="col" className="py-1 pr-4 font-medium">{h}</th>)}</tr></thead>
        <tbody>
          {page.items.map((r, i) => (
            <tr key={i} className="border-t border-default">
              {cols.map(([k], ci) => {
                const v = r[k];
                const text = typeof v === "boolean" ? (v ? "Yes" : "No") : k.endsWith("_at") || k.endsWith("_end") ? when(v) : label(v);
                return ci === 0 ? <th key={k} scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">{text}</th> : <td key={k} className="py-1 pr-4 [overflow-wrap:anywhere]">{text}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Subscriptions() {
  const [page, setPage] = useState(1);
  const [state, setState] = useState("");
  const r = useAdminResource(() => api.admin.billingOps.subscriptions(page, state), [page, state]);
  return (
    <Panel title="Provider-managed subscriptions">
      <label className="grid max-w-xs gap-1 text-xs text-muted">Lifecycle state
        <select className={field} value={state} onChange={(e) => { setState(e.target.value); setPage(1); }}><option value="">All</option>{SUB_STATES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
      </label>
      <ResourceState loaded={r}>
        {r.state === "ready" ? (<>
          <List page={r.data} caption="Provider-managed subscriptions" cols={[["reference", "Reference"], ["state", "State"], ["environment", "Environment"], ["interval", "Interval"], ["terms_version", "Terms"], ["invoice_state", "Invoice"],
            ["cancel_at_period_end", "Cancels at period end"], ["current_period_end", "Period end"], ["last_verified_at", "Last verified"], ["entitlement_decision", "Access decision"], ["review_category", "Review"]]} />
          <Pager page={page} pageSize={25} total={r.data.total} onPage={setPage} />
        </>) : null}
      </ResourceState>
    </Panel>
  );
}

function Checkouts() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const r = useAdminResource(() => api.admin.billingOps.checkouts(page, status), [page, status]);
  return (
    <Panel title="Checkout sessions (no URL, no provider session id)">
      <label className="grid max-w-xs gap-1 text-xs text-muted">Status
        <select className={field} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All</option>{CHECKOUT_STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
      </label>
      <ResourceState loaded={r}>
        {r.state === "ready" ? (<>
          <List page={r.data} caption="Checkout sessions" cols={[["reference", "Reference"], ["status", "Status"], ["environment", "Environment"], ["terms_version", "Terms"], ["created_at", "Created"], ["expires_at", "Expires"],
            ["browser_returned", "Browser returned"], ["subscription_linked", "Subscription linked"], ["failure_category", "Failure"]]} />
          <Pager page={page} pageSize={25} total={r.data.total} onPage={setPage} />
        </>) : null}
      </ResourceState>
    </Panel>
  );
}

function Events() {
  const auth = useAuthOptional();
  const canRecover = hasAnyPermission(adminPermissions(auth?.account), [P.jobsManage]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const r = useAdminResource(() => api.admin.billingOps.events(page, status), [page, status]);
  return (
    <Panel title="Verified webhook events (no body, no signature)">
      <label className="grid max-w-xs gap-1 text-xs text-muted">Processing status
        <select className={field} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} data-testid="event-status-filter"><option value="">All</option>{EVENT_STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
      </label>
      <ResourceState loaded={r}>
        {r.state === "ready" ? (<>
          {!r.data?.items || r.data.items.length === 0 ? <p className="text-sm text-muted">Nothing to show.</p> : (
            <div className="relative overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Webhook events</caption>
                <thead><tr className="text-xs text-muted">{["Event", "Received", "Status", "Attempts", "Failure", ""].map((h, i) => <th key={i} scope="col" className="py-1 pr-3 font-medium">{h}</th>)}</tr></thead>
                <tbody>
                  {r.data.items.map((e) => (
                    <tr key={String(e.reference)} className="border-t border-default align-top">
                      <th scope="row" className="py-1 pr-3 text-left font-medium">
                        <span className="block [overflow-wrap:anywhere]">{String(e.provider_event)}</span>
                        <span className="block text-xs font-normal text-muted [overflow-wrap:anywhere]">{label(e.event_type)} · {String(e.environment)}</span>
                      </th>
                      <td className="py-1 pr-3">{when(e.received_at)}</td>
                      <td className="py-1 pr-3"><StatusLabel tone={e.status === "processed" || e.status === "ignored" ? "ok" : e.status === "quarantined" || e.status === "needs_review" || e.status === "failed" ? "warn" : "neutral"}>{label(e.status)}</StatusLabel></td>
                      <td className="py-1 pr-3 whitespace-nowrap">{String(e.attempt_count)} / {String(e.attempt_limit)}</td><td className="py-1 pr-3">{label(e.failure_category)}</td>
                      <td className="py-1"><button type="button" className={btn} onClick={() => setOpen(String(e.reference))} aria-label={`Open event ${String(e.provider_event)}`}>Details</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager page={page} pageSize={25} total={r.data.total} onPage={setPage} />
        </>) : null}
      </ResourceState>
      {open ? <EventDetail reference={open} canRecover={canRecover} onClose={() => { setOpen(null); r.reload(); }} /> : null}
    </Panel>
  );
}

function EventDetail({ reference, canRecover, onClose }: { reference: string; canRecover: boolean; onClose: () => void }) {
  const d = useAdminResource(() => api.admin.billingOps.event(reference), [reference]);
  const [action, setAction] = useState<null | "retry" | "requeue">(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const key = useRef<string>("");
  const begin = (a: "retry" | "requeue") => { key.current = `ui-${a}-${Math.random().toString(36).slice(2, 12)}${Date.now().toString(36)}`; setAction(a); };
  const run = async (reason: string) => {
    const res = await api.admin.billingOps.recover(action as "retry" | "requeue", reference, reason, key.current);
    setOutcome(res.status === "completed" ? `Recovery completed (${label(res.result)}).` : res.status === "refused"
      ? `Refused: ${label(res.result)}. Nothing was changed.` : `Recovery failed: ${label(res.result)}. Nothing was guessed.`);
    d.reload();
  };
  return (
    <section aria-label="Event detail" className="mt-3 rounded border border-border p-3" data-testid="event-detail">
      <div className="flex items-center justify-between"><h3 className="text-base font-semibold">Event detail</h3><button type="button" className={btn} onClick={onClose}>Close</button></div>
      <ResourceState loaded={d}>
        {d.state === "ready" ? (
          <div className="grid gap-2 text-sm">
            <p><strong>{label(d.data.event_type)}</strong> · {d.data.environment} · <StatusLabel tone="neutral">{label(d.data.status)}</StatusLabel></p>
            <p>{d.data.classification}</p>
            <p>Signature verified: <strong>{d.data.signature_verified ? "yes (only verified events are stored)" : "no"}</strong> · attempts {d.data.attempt_count} of {d.data.attempt_limit} · operator retries {d.data.operator_retries} · failure: {label(d.data.failure_category)}</p>
            <p>Subscription reference: {d.data.subscription_reference ?? "none (not associated)"} · audit correlation: {d.data.correlation_id ?? "none"}</p>
            <ol className="list-decimal pl-5">{d.data.lifecycle.map((s, i) => <li key={i}>{label(s.step)}: {when(s.at)}</li>)}</ol>
            {d.data.reconciliation ? <p>Reconciliation: {label(d.data.reconciliation.disposition)} · observed {label(d.data.reconciliation.observed_state)} · access decision {label(d.data.reconciliation.entitlement_decision)}{d.data.reconciliation.conflict ? ` · conflict: ${label(d.data.reconciliation.conflict)}` : ""}</p> : <p className="text-muted">Not reconciled.</p>}
            {outcome ? <p role="status" data-testid="recovery-outcome">{outcome}</p> : null}
            {canRecover && d.data.recoverable ? (
              <p className="flex flex-wrap gap-2">
                <button type="button" className={btn} onClick={() => begin("retry")}>Retry through the verified pipeline</button>
                {d.data.status === "processing" ? <button type="button" className={btn} onClick={() => begin("requeue")}>Release abandoned lease</button> : null}
              </p>
            ) : <p className="text-xs text-muted">{d.data.recoverable ? "Recovery needs the job-management permission." : "This event cannot be retried."}</p>}
          </div>
        ) : null}
      </ResourceState>
      <ActionDialog open={action !== null} title={action === "retry" ? "Retry this event?" : "Release the abandoned lease?"} confirmLabel="Confirm" askReason reasonRequired
        onConfirm={run} onClose={() => setAction(null)} testId="recovery-dialog">
        <p className="text-sm">This re-drives the existing verified pipeline for this stored event. It cannot create, edit or delete a financial fact, grant access, or run a refund or payment. Without a wired provider-state reader it is refused.</p>
      </ActionDialog>
    </section>
  );
}

function Reconciliation() {
  const r = useAdminResource(() => api.admin.billingOps.reconciliation(), []);
  return (
    <ResourceState loaded={r}>
      {r.state === "ready" && !(r.data?.problems_by_category && r.data.needs_attention) ? UNUSABLE : null}
      {r.state === "ready" && r.data?.problems_by_category && r.data.needs_attention ? (
        <>
          <Panel title="Reconciliation status">
            <p className="text-sm" data-testid="sync-status">Provider synchronization: <strong>{r.data.provider_synchronization === "not_performed_no_reader" ? "not performed: no provider-state reader is wired" : "available"}</strong> · scheduler: <strong>{r.data.scheduler}</strong></p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Stale subscriptions" value={r.data.stale_links} /><Stat label="Retry scheduled" value={r.data.retry_scheduled} />
              <Stat label="Last successful" value={when(r.data.last_successful)} /><Stat label="Last attempt" value={when(r.data.last_attempt)} />
            </div>
            <p className="text-xs text-muted">{r.data.cadence_note}</p>
            {Object.keys(r.data.problems_by_category).length ? <ul className="text-sm">{Object.entries(r.data.problems_by_category).map(([k, n]) => <li key={k}>{label(k)}: {n}</li>)}</ul> : <p className="text-sm text-muted">No failed, quarantined or review-needed events.</p>}
          </Panel>
          <Panel title="Failures and quarantine">
            <List page={{ items: r.data.needs_attention, total: r.data.needs_attention.length, page: 1, page_size: 25 }} caption="Events needing attention"
              cols={[["provider_event", "Event"], ["event_type", "Type"], ["status", "Status"], ["failure_category", "Category"], ["attempt_count", "Attempts"], ["classification", "What it means"]]} />
          </Panel>
        </>
      ) : null}
    </ResourceState>
  );
}

function History() {
  const [page, setPage] = useState(1);
  const r = useAdminResource(() => api.admin.billingOps.recoveryActions(page), [page]);
  return (
    <Panel title="Operator recovery history (who, what, why, result)">
      <ResourceState loaded={r}>
        {r.state === "ready" ? (<>
          <List page={r.data} caption="Recovery history" cols={[["created_at", "When"], ["action", "Action"], ["status", "Status"], ["result", "Result"], ["actor_id", "Operator"], ["reason", "Reason"]]} />
          <Pager page={page} pageSize={25} total={r.data.total} onPage={setPage} />
        </>) : null}
      </ResourceState>
      <p className="text-xs text-muted">Every action is also written to the audit log in the same transaction. Financial evidence is never deleted to clear a warning.</p>
    </Panel>
  );
}

const YES = new Set(["approved", "authorized", "enabled", "wired"]);
const ROWS: [keyof BillingOpsReadiness, string][] = [["provider_selected", "Provider selected"], ["environment", "Environment"], ["credential_status", "Credential status"], ["eligibility", "Managed Payments eligibility"],
  ["sandbox_access", "Sandbox access"], ["checkout", "External checkout"], ["webhook", "Webhook endpoint"], ["provider_state_reader", "Provider-state reader"], ["reconciliation_scheduler", "Reconciliation scheduler"],
  ["entitlement_policy", "Paid entitlement policy"], ["live_billing", "Live billing"]];

function Readiness() {
  const r = useAdminResource(() => api.admin.billingOps.overview(), []);
  return (
    <ResourceState loaded={r}>
      {r.state === "ready" && !r.data?.readiness?.kill_switches ? UNUSABLE : null}
      {r.state === "ready" && r.data?.readiness?.kill_switches ? (
        <Panel title="Operational readiness (truth only: nothing here is validated)">
          <table className="w-full text-left text-sm" data-testid="readiness-table">
            <caption className="sr-only">Billing readiness</caption>
            <tbody>
              {ROWS.map(([k, text]) => (
                <tr key={k} className="border-t border-default">
                  <th scope="row" className="py-1 pr-4 text-left font-medium">{text}</th>
                  <td className="py-1"><StatusLabel tone={YES.has(String(r.data.readiness[k])) ? "ok" : "warn"}>{label(r.data.readiness[k])}</StatusLabel></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-muted">Kill switches (code constants, not settings): {Object.entries(r.data.readiness.kill_switches).map(([k, v]) => `${label(k)}: ${v ? "on" : "off"}`).join(" · ")}. Secret values are never shown here.</p>
        </Panel>
      ) : null}
    </ResourceState>
  );
}
