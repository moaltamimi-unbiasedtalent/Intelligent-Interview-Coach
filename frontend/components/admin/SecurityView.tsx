"use client";

import { useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { AdminAlert, IncidentDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { useStepUp } from "./StepUp";
import { Pager, Panel, PermissionGate, ResourceState, StatusLabel, Table, apiMessage, btn, field, useAdminResource } from "./ui";

// Security administration. Operational metadata only: no candidate content, no email, IP or user agent.
// Step-up is password re-authentication, not MFA. Alerts are in-app only.

type Tab = "events" | "audit" | "incidents" | "alerts" | "roles";
const TABS: { id: Tab; label: string; perm: string }[] = [
  { id: "events", label: "Security events", perm: P.securityRead },
  { id: "audit", label: "Audit", perm: P.audit },
  { id: "incidents", label: "Incidents", perm: P.securityRead },
  { id: "alerts", label: "Alerts", perm: P.securityRead },
  { id: "roles", label: "Role approvals", perm: P.roleAssign },
];
const SEVERITY_TEXT: Record<string, string> = { low: "Severity: low", medium: "Severity: medium", high: "Severity: high", critical: "Severity: critical" };

export function SecurityView() {
  return (
    <PermissionGate anyOf={[P.securityRead, P.audit, P.roleAssign]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const tabs = TABS.filter((t) => hasAnyPermission(granted, [t.perm]));
  const [tab, setTab] = useState<Tab>(tabs[0]?.id ?? "events");
  return (
    <div className="grid gap-4">
      <p className="text-sm">Operational metadata only. Security administration never shows candidate content, email addresses, IP addresses or session tokens. Alerts are shown here in the app; nothing is sent to an external pager.</p>
      <div role="tablist" aria-label="Security sections" className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={btn} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      {tab === "events" ? <Events /> : null}
      {tab === "audit" ? <Audit /> : null}
      {tab === "incidents" ? <Incidents /> : null}
      {tab === "alerts" ? <Alerts /> : null}
      {tab === "roles" ? <RoleApprovals /> : null}
    </div>
  );
}

// ------------------------------------------------------------------ events
function Events() {
  const [category, setCategory] = useState("");
  const [severity, setSeverity] = useState("");
  const [period, setPeriod] = useState("7d");
  const [page, setPage] = useState(1);
  const loaded = useAdminResource(() => api.admin.securityEvents({ category, severity, period, page, page_size: 25 }), [category, severity, period, page]);
  return (
    <Panel title="Security events">
      <div className="flex flex-wrap gap-3">
        <label className="grid gap-1 text-sm">Category
          <select className={field} value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
            <option value="">All</option>
            {["authentication", "authorization", "role_change", "session_revocation", "password_reset", "account_status", "step_up", "audit_export"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm">Severity
          <select className={field} value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
            <option value="">All</option>
            {["low", "medium", "high", "critical"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm">Period
          <select className={field} value={period} onChange={(e) => { setPeriod(e.target.value); setPage(1); }}>
            {["24h", "7d", "30d", "90d"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <>
            {loaded.data.anomalies.length ? (
              <ul className="grid gap-1 text-sm" aria-label="Detected patterns">
                {loaded.data.anomalies.map((a) => (
                  <li key={`${a.rule}-${a.actor_user_id}`} className="rounded border border-border px-3 py-2">
                    <strong>{a.rule.replace(/_/g, " ")}</strong>: account {a.actor_user_id}, {a.count} in {a.window_minutes} minutes (threshold {a.threshold}).
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">No repeated-failure pattern in the last 15 minutes. Advanced anomaly detection is not implemented.</p>}
            <Table caption="Security events" cols={["created_at", "severity", "category", "event_type", "result", "actor_user_id", "target_type", "target_id", "request_id"]}
              rows={loaded.data.items.map((e) => ({ ...e, severity: SEVERITY_TEXT[e.severity] ?? e.severity }))} />
            <Pager page={page} pageSize={25} total={loaded.data.total} onPage={setPage} />
          </>
        ) : null}
      </ResourceState>
    </Panel>
  );
}

// ------------------------------------------------------------------ audit
function Audit() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const [area, setArea] = useState("");
  const [result, setResult] = useState("");
  const [requestId, setRequestId] = useState("");
  const [period, setPeriod] = useState("30d");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const loaded = useAdminResource(() => api.admin.auditPage({ area, result, request_id: requestId, period, page, page_size: 50 }), [area, result, requestId, period, page]);
  return (
    <Panel title="Audit history">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm">Area
          <select className={field} value={area} onChange={(e) => { setArea(e.target.value); setPage(1); }}>
            <option value="">All</option>
            {["account", "admin", "security", "platform"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm">Result
          <input className={field} value={result} maxLength={32} onChange={(e) => { setResult(e.target.value); setPage(1); }} />
        </label>
        <label className="grid gap-1 text-sm">Request ID
          <input className={field} value={requestId} maxLength={64} onChange={(e) => { setRequestId(e.target.value); setPage(1); }} />
        </label>
        <label className="grid gap-1 text-sm">Period
          <select className={field} value={period} onChange={(e) => { setPeriod(e.target.value); setPage(1); }}>
            {["24h", "7d", "30d", "90d", "all"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        {hasAnyPermission(granted, [P.auditExport]) ? <button type="button" className={btn} onClick={() => setExporting(true)}>Export audit events</button> : null}
      </div>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <>
            <Table caption="Audit events" cols={["created_at", "event_type", "result", "actor_user_id", "target_type", "target_id", "request_id"]} rows={loaded.data.items.map((e) => ({ ...e }))} />
            <Pager page={page} pageSize={50} total={loaded.data.total} onPage={setPage} />
          </>
        ) : null}
      </ResourceState>
      <ExportDialog open={exporting} onClose={() => setExporting(false)} onDone={(m) => setNotice(m)} defaults={{ area, result, request_id: requestId }} />
    </Panel>
  );
}

function ExportDialog({ open, onClose, onDone, defaults }: { open: boolean; onClose: () => void; onDone: (m: string) => void; defaults: Record<string, string> }) {
  const [format, setFormat] = useState("csv");
  const [period, setPeriod] = useState("7d");
  return (
    <ActionDialog open={open} title="Export audit events?" confirmLabel="Export" reasonRequired onClose={onClose}
      onConfirm={async (reason) => {
        const filters = Object.fromEntries(Object.entries(defaults).filter(([, v]) => v));
        const out = await api.admin.exportAudit({ format, period, reason, ...filters });
        const url = URL.createObjectURL(new Blob([out.content], { type: format === "json" ? "application/json" : "text/csv" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = out.filename;
        a.click();
        URL.revokeObjectURL(url);
        onDone(`Exported ${out.count} audit events. The export itself was recorded in the audit log.`);
      }}>
      <p>The export is limited to a bounded period and a maximum number of rows. It contains event metadata only (never event context or candidate content), and the export is audited.</p>
      <label className="grid gap-1 text-xs text-muted">Format
        <select className={field} value={format} onChange={(e) => setFormat(e.target.value)}><option value="csv">CSV</option><option value="json">JSON</option></select>
      </label>
      <label className="grid gap-1 text-xs text-muted">Period
        <select className={field} value={period} onChange={(e) => setPeriod(e.target.value)}>{["24h", "7d", "30d", "90d"].map((c) => <option key={c} value={c}>{c}</option>)}</select>
      </label>
    </ActionDialog>
  );
}

// ------------------------------------------------------------------ alerts
function Alerts() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.securityManage]);
  const [state, setState] = useState("");
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState<{ alert: AdminAlert; action: "acknowledge" | "resolve" } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const loaded = useAdminResource(() => api.admin.alerts({ state, page, page_size: 25 }), [state, page]);
  return (
    <Panel title="Alerts (in-app only)">
      <label className="grid gap-1 text-sm">State
        <select className={field} value={state} onChange={(e) => { setState(e.target.value); setPage(1); }}>
          <option value="">All</option>{["active", "acknowledged", "resolved"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <>
            {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No alerts.</p> : (
              <ul className="grid gap-2">
                {loaded.data.items.map((a) => (
                  <li key={a.public_id} className="rounded border border-border p-3 text-sm">
                    <p className="font-medium">{a.title}</p>
                    <p className="text-xs text-muted">{SEVERITY_TEXT[a.severity] ?? a.severity} · State: {a.state} · Seen {a.occurrence_count} time(s) · Last seen {a.last_seen_at}</p>
                    {canManage && a.state !== "resolved" ? (
                      <span className="mt-2 flex gap-2">
                        {a.state === "active" ? <button type="button" className={btn} onClick={() => setPending({ alert: a, action: "acknowledge" })}>Acknowledge</button> : null}
                        <button type="button" className={btn} onClick={() => setPending({ alert: a, action: "resolve" })}>Resolve</button>
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-muted">Alert categories not implemented: {loaded.data.not_implemented.join(", ").replace(/_/g, " ")}. Delivery is in-app only.</p>
            <Pager page={page} pageSize={25} total={loaded.data.total} onPage={setPage} />
          </>
        ) : null}
      </ResourceState>
      <ActionDialog open={pending !== null} title={pending?.action === "resolve" ? "Resolve this alert?" : "Acknowledge this alert?"} askReason={false}
        confirmLabel={pending?.action === "resolve" ? "Resolve" : "Acknowledge"} onClose={() => setPending(null)}
        onConfirm={async () => {
          if (!pending) return;
          if (pending.action === "resolve") await api.admin.resolveAlert(pending.alert.public_id, pending.alert.revision);
          else await api.admin.acknowledgeAlert(pending.alert.public_id, pending.alert.revision);
          setNotice(`Alert ${pending.action === "resolve" ? "resolved" : "acknowledged"}.`);
          loaded.reload();
        }}>
        <p>{pending?.alert.title}</p>
      </ActionDialog>
    </Panel>
  );
}

// ------------------------------------------------------------------ incidents
function Incidents() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.incidentsManage]);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const loaded = useAdminResource(() => api.admin.incidents({ page, page_size: 25 }), [page]);
  return (
    <div className="grid gap-4">
      <Panel title="Incidents">
        <p className="text-xs text-muted">Operational metadata only. Do not paste candidate content, credentials or secrets. Incidents are closed, never deleted.</p>
        {canManage ? <button type="button" className={btn} onClick={() => setCreating(true)}>Create incident</button> : null}
        <ResourceState loaded={loaded}>
          {loaded.state === "ready" ? (
            <>
              {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No incidents.</p> : (
                <ul className="grid gap-2">
                  {loaded.data.items.map((i) => (
                    <li key={i.public_id} className="flex items-center justify-between gap-3 rounded border border-border p-3 text-sm">
                      <span><strong>{i.title}</strong><br /><span className="text-xs text-muted">{SEVERITY_TEXT[i.severity] ?? i.severity} · Status: {i.status} · Service: {i.affected_service}</span></span>
                      <button type="button" className={btn} onClick={() => setSelected(i.public_id)}>Open</button>
                    </li>
                  ))}
                </ul>
              )}
              <Pager page={page} pageSize={25} total={loaded.data.total} onPage={setPage} />
              <CreateIncident open={creating} onClose={() => setCreating(false)} onCreated={loaded.reload} services={loaded.data.services} severities={loaded.data.severities} />
            </>
          ) : null}
        </ResourceState>
      </Panel>
      {selected ? <IncidentPanel id={selected} canManage={canManage} onChanged={loaded.reload} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

function CreateIncident({ open, onClose, onCreated, services, severities }: { open: boolean; onClose: () => void; onCreated: () => void; services: string[]; severities: string[] }) {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [service, setService] = useState(services[0] ?? "platform");
  return (
    <ActionDialog open={open} title="Create incident" confirmLabel="Create" askReason={false} onClose={onClose}
      onConfirm={async () => {
        await api.admin.createIncident({ title, severity, affected_service: service });
        setTitle("");
        onCreated();
      }}>
      <p className="text-xs">Operational metadata only. Do not paste candidate content, credentials or secrets.</p>
      <label className="grid gap-1 text-xs text-muted">Title
        <input className={field} value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="grid gap-1 text-xs text-muted">Severity
        <select className={field} value={severity} onChange={(e) => setSeverity(e.target.value)}>{severities.map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </label>
      <label className="grid gap-1 text-xs text-muted">Affected service
        <select className={field} value={service} onChange={(e) => setService(e.target.value)}>{services.map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </label>
    </ActionDialog>
  );
}

function IncidentPanel({ id, canManage, onChanged, onClose }: { id: string; canManage: boolean; onChanged: () => void; onClose: () => void }) {
  const loaded = useAdminResource(() => api.admin.incident(id), [id]);
  return (
    <Panel title="Incident detail">
      <button type="button" className={btn} onClick={onClose}>Close detail</button>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? <IncidentBody d={loaded.data} canManage={canManage} reload={() => { loaded.reload(); onChanged(); }} /> : null}
      </ResourceState>
    </Panel>
  );
}

function IncidentBody({ d, canManage, reload }: { d: IncidentDetail; canManage: boolean; reload: () => void }) {
  const [rootCause, setRootCause] = useState(d.root_cause ?? "");
  const [remediation, setRemediation] = useState(d.remediation ?? "");
  const [ticket, setTicket] = useState("");
  const [error, setError] = useState<string | null>(null);
  const guard = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); reload(); } catch (e) { setError(apiMessage(e)); }
  };
  return (
    <div className="grid gap-3 text-sm">
      <h3 className="text-base font-semibold">{d.title}</h3>
      <p>{SEVERITY_TEXT[d.severity] ?? d.severity} · Status: {d.status} · Service: {d.affected_service} · Revision {d.revision}</p>
      {error ? <p role="alert" className="rounded border border-border px-3 py-2">{error}</p> : null}
      {canManage ? (
        <>
          <p className="text-xs text-muted">Operational metadata only. Do not paste candidate content, credentials or secrets.</p>
          <label className="grid gap-1">Root cause
            <textarea className={field} rows={3} maxLength={1000} value={rootCause} onChange={(e) => setRootCause(e.target.value)} />
          </label>
          <label className="grid gap-1">Remediation
            <textarea className={field} rows={3} maxLength={1000} value={remediation} onChange={(e) => setRemediation(e.target.value)} />
          </label>
          <button type="button" className={btn} onClick={() => guard(() => api.admin.updateIncident(d.public_id, { expected_revision: d.revision, root_cause: rootCause, remediation }))}>Save notes</button>
          <div className="flex flex-wrap gap-2" aria-label="Status transitions">
            {d.allowed_transitions.map((s) => (
              <button key={s} type="button" className={btn} onClick={() => guard(() => api.admin.incidentStatus(d.public_id, s, d.revision))}>Move to {s}</button>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="grid gap-1">Link a support ticket (identifier only)
              <input className={field} value={ticket} maxLength={32} onChange={(e) => setTicket(e.target.value)} />
            </label>
            <button type="button" className={btn} disabled={!ticket.trim()} onClick={() => guard(async () => { await api.admin.linkIncidentTicket(d.public_id, ticket.trim(), d.revision); setTicket(""); })}>Link ticket</button>
          </div>
        </>
      ) : null}
      <Table caption="Linked tickets (identifiers only)" cols={["public_id", "status", "category"]} rows={d.tickets} />
      <Table caption="Incident history" cols={["created_at", "action", "prior_status", "new_status", "actor_user_id", "request_id"]} rows={d.history} />
    </div>
  );
}

// ------------------------------------------------------------------ role approvals
function RoleApprovals() {
  const stepUp = useStepUp();
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loaded = useAdminResource(() => api.admin.roleChanges(), []);
  const act = async (fn: () => Promise<unknown>, done: string) => {
    setError(null);
    try { await stepUp.run(fn); setNotice(done); loaded.reload(); } catch (e) { setError(apiMessage(e)); }
  };
  return (
    <Panel title="Role approvals">
      <p className="text-sm">A role change takes effect only when a different Admin approves it. Approving needs a recent password confirmation (password re-authentication, not MFA).</p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      {error ? <p role="alert" className="rounded border border-border px-3 py-2 text-sm">{error}</p> : null}
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          loaded.data.items.length === 0 ? <p className="text-sm text-muted">No role-change requests.</p> : (
            <ul className="grid gap-2">
              {loaded.data.items.map((r) => {
                const mine = r.requester_user_id === loaded.data.viewer_user_id;
                const involved = mine || r.target_user_id === loaded.data.viewer_user_id;
                return (
                  <li key={r.public_id} className="rounded border border-border p-3 text-sm">
                    <p>Account {r.target_user_id}: {r.before_role} to {r.requested_role} <StatusLabel tone={r.status === "applied" ? "ok" : r.status === "pending" ? "neutral" : "warn"}>{r.status}</StatusLabel></p>
                    <p className="text-xs text-muted">Reason: {r.reason} · Requested {r.requested_at}</p>
                    {r.status === "pending" ? (
                      <span className="mt-2 flex flex-wrap items-center gap-2">
                        {involved ? <span className="text-xs">{mine ? "You requested this; a different Admin must approve." : "This request is about your account; you cannot decide it."}</span> : (
                          <>
                            <button type="button" className={btn} onClick={() => act(() => api.admin.approveRoleChange(r.public_id), "Role change approved and applied.")}>Approve</button>
                            <button type="button" className={btn} onClick={() => act(() => api.admin.rejectRoleChange(r.public_id), "Role change rejected.")}>Reject</button>
                          </>
                        )}
                        {mine ? <button type="button" className={btn} onClick={() => act(() => api.admin.cancelRoleChange(r.public_id), "Request cancelled.")}>Cancel request</button> : null}
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )
        ) : null}
      </ResourceState>
      {stepUp.dialog}
    </Panel>
  );
}
