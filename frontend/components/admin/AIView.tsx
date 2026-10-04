"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { AIEnvironment } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KIND_LABEL, SOURCE_LABEL, STATE_LABEL, label, shortHash } from "./aiLabels";
import { Panel, PermissionGate, ResourceState, Stat, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";

// AI and model administration. An AI configuration changes which APPROVED catalogue model each profile uses and a few bounded numbers. It is never
// active without a passed evaluation and a different second approver. There is no provider-name input anywhere on this page. No live model is called.

export function AIView() {
  return (
    <PermissionGate anyOf={[P.ai]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const canManage = hasAnyPermission(granted, [P.aiManage]);
  const canActivate = hasAnyPermission(granted, [P.aiActivate]);
  const overview = useAdminResource(() => api.admin.ai(), []);
  const envs = useAdminResource(() => api.admin.aiEnvironments(), []);
  const configs = useAdminResource(() => api.admin.aiConfigs(), []);
  const approvals = useAdminResource(() => api.admin.aiApprovals(), []);
  const history = useAdminResource(() => api.admin.aiHistory(), []);
  const catalogue = useAdminResource(() => api.admin.aiCatalogue(), []);
  const codeDefined = useAdminResource(() => api.admin.aiCodeDefined(), []);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [base, setBase] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rollbackFor, setRollbackFor] = useState<null | { env: AIEnvironment; toCode: boolean }>(null);
  const reloadAll = () => { overview.reload(); envs.reload(); configs.reload(); approvals.reload(); history.reload(); };

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    try {
      const d = await api.admin.aiCreate(name.trim(), notes.trim(), base || null, null);
      setNotice(`Draft version ${d.version} created.`);
      setName(""); setNotes(""); setBase("");
      reloadAll();
    } catch (err) {
      setFormError(apiMessage(err));
    }
  };

  return (
    <div className="grid gap-4">
      <section aria-labelledby="ai-boundary" className="rounded border-2 border-border p-4">
        <h2 id="ai-boundary" className="text-lg font-semibold">Governed configuration, no live model calls</h2>
        <p className="text-sm">A configuration chooses which approved catalogue model serves Fast, Balanced and Advanced and sets a few bounded numbers. It cannot become active without a passed evaluation of its exact content and a different second approver. Evaluations are deterministic checks of the configuration. They do not measure live answer quality.</p>
      </section>
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}

      <ResourceState loaded={overview}>
        {overview.state === "ready" ? (
          <Panel title="What this server resolves now">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Environment" value={overview.data.runtime.environment} />
              <Stat label="Mode" value={overview.data.runtime.mode === "governed" ? "Governed configuration" : "Code defaults"} />
              <Stat label="Configuration" value={overview.data.runtime.active_version ? `Version ${overview.data.runtime.active_version}` : "None active"} />
              <Stat label="Pending approvals" value={overview.data.stats.pending_approvals} />
            </div>
            {overview.data.runtime.fallback_reason ? <p role="alert" className="text-sm">An active configuration was refused and code defaults are in use (reason: {label(overview.data.runtime.fallback_reason)}).</p> : null}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Resolved model per profile</caption>
                <thead><tr className="text-xs text-muted">{["Profile", "Catalogue entry", "Source"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                <tbody>
                  {Object.entries(overview.data.runtime.profiles).map(([p, r]) => (
                    <tr key={p} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium capitalize">{p}</th>
                      <td className="py-1 pr-4">{r.catalogue_id ?? "Environment-specified model"}</td>
                      <td className="py-1 pr-4">{SOURCE_LABEL[r.source] ?? r.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted">{overview.data.runtime.note}</p>
          </Panel>
        ) : null}
      </ResourceState>

      <ResourceState loaded={envs}>
        {envs.state === "ready" ? (
          <Panel title="Environments">
            <p className="text-sm">This server is <strong>{envs.data.this_environment}</strong>. It activates and rolls back only its own environment; the target cannot be chosen from the browser.</p>
            <div className="grid gap-3 sm:grid-cols-3">
              {envs.data.items.map((env) => (
                <div key={env.environment} className="rounded border border-default p-3">
                  <h3 className="text-sm font-semibold capitalize">{env.environment}</h3>
                  <p className="text-sm">{env.version ? <>Active: <Link href={`/admin/ai/${env.version.public_id}`}>{env.version.name} (version {env.version.version})</Link></> : "Code defaults (no configuration active)"}</p>
                  {env.active ? <p className="text-xs text-muted">Since {env.active.activated_at ?? ""} · {KIND_LABEL[env.active.kind] ?? env.active.kind}</p> : null}
                  {canActivate && env.version && env.environment === envs.data.this_environment ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button type="button" className={btn} onClick={() => setRollbackFor({ env, toCode: false })} aria-label={`Roll back ${env.environment} to the previous configuration`}>Roll back</button>
                      <button type="button" className={btn} onClick={() => setRollbackFor({ env, toCode: true })} aria-label={`Revert ${env.environment} to code defaults`}>Revert to code defaults</button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
            <p className="text-xs text-muted">{envs.data.note}</p>
          </Panel>
        ) : null}
      </ResourceState>

      <ResourceState loaded={configs}>
        {configs.state === "ready" ? (
          <Panel title="Configuration versions">
            {configs.data.items.length === 0 ? <p className="text-sm text-muted">No configuration has been created. The code-defined registry is in use.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">AI configuration versions</caption>
                  <thead><tr className="text-xs text-muted">{["Version", "Name", "State", "Hash", "Active in", "Author"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {configs.data.items.map((v) => (
                      <tr key={v.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">Version {v.version}</th>
                        <td className="py-1 pr-4"><Link href={`/admin/ai/${v.public_id}`}>{v.name}</Link></td>
                        <td className="py-1 pr-4"><StatusLabel tone={v.state === "approved" ? "ok" : v.state === "evaluation_failed" || v.state === "rejected" ? "warn" : "neutral"}>{STATE_LABEL[v.state] ?? v.state}</StatusLabel></td>
                        <td className="py-1 pr-4 font-mono text-xs">{shortHash(v.content_hash)}</td>
                        <td className="py-1 pr-4">{v.active_in.length ? v.active_in.join(", ") : "Not active"}</td>
                        <td className="py-1 pr-4">{v.created_by_email ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        ) : null}
      </ResourceState>

      {canManage ? (
        <Panel title="New draft configuration">
          <form onSubmit={create} className="grid gap-2 sm:max-w-xl">
            <label className="grid gap-1 text-sm">Name
              <input className={field} value={name} maxLength={80} required onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm">Notes (optional)
              <input className={field} value={notes} maxLength={300} onChange={(e) => setNotes(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm">Start from
              <select className={field} value={base} onChange={(e) => setBase(e.target.value)}>
                <option value="">Code defaults</option>
                {configs.state === "ready" ? configs.data.items.map((v) => <option key={v.public_id} value={v.public_id}>Version {v.version}: {v.name}</option>) : null}
              </select>
            </label>
            {formError ? <p role="alert" className="text-sm">{formError}</p> : null}
            <div><button type="submit" className={btn} disabled={!name.trim()}>Create draft</button></div>
          </form>
        </Panel>
      ) : null}

      <ResourceState loaded={approvals}>
        {approvals.state === "ready" ? (
          <Panel title="Approval requests">
            {approvals.data.items.length === 0 ? <p className="text-sm text-muted">No approval requests.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">AI configuration approval requests</caption>
                  <thead><tr className="text-xs text-muted">{["Configuration", "Hash", "Requested by", "Status", "Decided by"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {approvals.data.items.map((a) => (
                      <tr key={a.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">{a.version_ref ? <Link href={`/admin/ai/${a.version_ref}`}>Open configuration</Link> : "Unknown"}</th>
                        <td className="py-1 pr-4 font-mono text-xs">{shortHash(a.content_hash)}</td>
                        <td className="py-1 pr-4">{a.requested_by_email ?? ""}</td>
                        <td className="py-1 pr-4"><StatusLabel tone={a.status === "approved" ? "ok" : a.status === "pending" ? "neutral" : "warn"}>{label(a.status)}</StatusLabel></td>
                        <td className="py-1 pr-4">{a.decided_by_email ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        ) : null}
      </ResourceState>

      <ResourceState loaded={history}>
        {history.state === "ready" ? (
          <Panel title="Activation history">
            {history.data.items.length === 0 ? <p className="text-sm text-muted">Nothing has been activated yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Append-only activation history</caption>
                  <thead><tr className="text-xs text-muted">{["When", "Environment", "Event", "Version", "By", "Reason"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {history.data.items.map((h) => (
                      <tr key={h.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-normal">{h.activated_at ?? ""}</th>
                        <td className="py-1 pr-4 capitalize">{h.environment}</td>
                        <td className="py-1 pr-4">{KIND_LABEL[h.kind] ?? h.kind}{h.open ? " (current)" : ""}</td>
                        <td className="py-1 pr-4">{h.version ? `Version ${h.version}` : "Code defaults"}</td>
                        <td className="py-1 pr-4">{h.activated_by_email ?? ""}</td>
                        <td className="py-1 pr-4">{h.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        ) : null}
      </ResourceState>

      <ResourceState loaded={catalogue}>
        {catalogue.state === "ready" ? (
          <Panel title={`Approved model catalogue (${catalogue.data.version})`}>
            <p className="text-xs text-muted">{catalogue.data.note}</p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Approved model catalogue</caption>
                <thead><tr className="text-xs text-muted">{["Entry", "Provider model (read-only)", "Tier", "May serve", "Tools", "Structured output", "Relative cost"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                <tbody>
                  {catalogue.data.items.map((e) => (
                    <tr key={e.id} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">{e.display_name}</th>
                      <td className="py-1 pr-4 font-mono text-xs">{e.provider_slug}</td>
                      <td className="py-1 pr-4 capitalize">{e.tier}</td>
                      <td className="py-1 pr-4">{e.allowed_profiles.join(", ")}</td>
                      <td className="py-1 pr-4">{e.supports_tools ? "Yes" : "No"}</td>
                      <td className="py-1 pr-4">{e.supports_structured_output ? "Yes" : "No"}</td>
                      <td className="py-1 pr-4">{e.cost_class} of 3</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        ) : null}
      </ResourceState>

      <ResourceState loaded={codeDefined}>
        {codeDefined.state === "ready" ? (
          <Panel title="Code-defined behaviour (not configurable)">
            <p className="text-xs text-muted">{codeDefined.data.note}</p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Operations and what is configurable</caption>
                <thead><tr className="text-xs text-muted">{["Operation", "Capability", "Minimum tier", "Fallback floor", "Configurable"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                <tbody>
                  {codeDefined.data.operations.map((o) => (
                    <tr key={o.operation} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">{label(o.operation)}</th>
                      <td className="py-1 pr-4">{label(o.capability)}</td>
                      <td className="py-1 pr-4 capitalize">{o.deterministic || o.realtime ? "Not applicable" : o.min_capability}</td>
                      <td className="py-1 pr-4 capitalize">{o.deterministic || o.realtime ? "Not applicable" : o.fallback_floor}</td>
                      <td className="py-1 pr-4">{o.tunable ? "Numbers only" : o.deterministic ? "No (deterministic, no model)" : o.realtime ? "No (realtime voice)" : "No (no separate runtime call path)"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        ) : null}
      </ResourceState>

      <ActionDialog open={rollbackFor !== null} title={rollbackFor?.toCode ? "Revert to code defaults?" : "Roll back to the previous configuration?"}
        confirmLabel={rollbackFor?.toCode ? "Revert to code defaults" : "Roll back"} reasonRequired
        onClose={() => setRollbackFor(null)}
        onConfirm={async (reason) => {
          if (!rollbackFor) return;
          await api.admin.aiRollback(rollbackFor.toCode, reason);
          setNotice(rollbackFor.toCode ? `${rollbackFor.env.environment} now uses the code-defined defaults.` : `${rollbackFor.env.environment} rolled back to the previous configuration.`);
          reloadAll();
        }}>
        <p className="text-sm">{rollbackFor?.toCode
          ? "The environment will resolve models from the code-defined registry (environment overrides, then code defaults). The configuration history is kept."
          : "The previously activated configuration is restored after the same integrity checks as any activation."}</p>
      </ActionDialog>
    </div>
  );
}
