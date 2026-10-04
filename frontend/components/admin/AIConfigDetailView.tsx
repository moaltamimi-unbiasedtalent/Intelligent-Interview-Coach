"use client";

import { useEffect, useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { AICatalogue, AIVersionDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KIND_LABEL, STATE_LABEL, TUNABLE_LABEL, label, shortHash } from "./aiLabels";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";

export function AIConfigDetailView({ id }: { id: string }) {
  return (
    <PermissionGate anyOf={[P.ai]}>
      <Body id={id} />
    </PermissionGate>
  );
}

type Action = "validate" | "evaluate" | "request" | "approve" | "reject" | "activate" | "retire";
const COPY: Record<Action, { title: string; button: string; body: string; reason: boolean }> = {
  validate: { title: "Validate this draft?", button: "Validate", body: "Deterministic checks run now. A draft that passes is frozen: its content can no longer be edited.", reason: false },
  evaluate: { title: "Queue an evaluation?", button: "Queue evaluation", body: "A background worker evaluates this exact configuration against the real resolution code. No live model is called. Refresh the page to see the result.", reason: false },
  request: { title: "Submit for approval?", button: "Submit for approval", body: "A different administrator, who is not the author and not you, must approve before it can be activated.", reason: true },
  approve: { title: "Approve this configuration?", button: "Approve", body: "You confirm you reviewed the changes and the passed evaluation. Approval does not activate it.", reason: true },
  reject: { title: "Reject this configuration?", button: "Reject", body: "A rejected configuration cannot be activated. Create a new draft to try again.", reason: true },
  activate: { title: "Activate on this server's environment?", button: "Activate", body: "This server's environment resolves models from this configuration within seconds (other servers of the same environment converge within a few seconds). You can roll back at any time.", reason: true },
  retire: { title: "Retire this version?", button: "Retire", body: "A retired version can never be activated again. Its history is kept.", reason: true },
};

function Body({ id }: { id: string }) {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const me = auth?.account?.user_id ?? null;
  const email = auth?.account?.email ?? null;
  const canManage = hasAnyPermission(granted, [P.aiManage]);
  const canActivate = hasAnyPermission(granted, [P.aiActivate]);
  const cfg = useAdminResource(() => api.admin.aiConfig(id), [id]);
  const catalogue = useAdminResource(() => api.admin.aiCatalogue(), []);
  const envs = useAdminResource(() => api.admin.aiEnvironments(), []);
  const thisEnv = envs.state === "ready" ? envs.data.this_environment : "";
  const [action, setAction] = useState<Action | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const run = async (v: AIVersionDetail, reason: string) => {
    if (!action) return;
    const pending = v.approvals.find((a) => a.status === "pending");
    switch (action) {
      case "validate": await api.admin.aiValidate(id); setNotice("Validation finished."); break;
      case "evaluate": await api.admin.aiEvaluate(id); setNotice("Evaluation queued. Refresh to see the result."); break;
      case "request": await api.admin.aiRequestApproval(id, reason); setNotice("Submitted. A different administrator must approve."); break;
      case "approve": if (pending) await api.admin.aiDecide(pending.public_id, true, reason); setNotice("Approved. It is not active until someone activates it."); break;
      case "reject": if (pending) await api.admin.aiDecide(pending.public_id, false, reason); setNotice("Rejected."); break;
      case "activate": await api.admin.aiActivate(id, reason); setNotice(`Active in ${thisEnv}.`); break;
      case "retire": await api.admin.aiRetire(id, reason); setNotice("Retired."); break;
    }
    cfg.reload();
  };

  return (
    <ResourceState loaded={cfg}>
      {cfg.state === "ready" ? (
        <div className="grid gap-4">
          {notice ? <p role="status" className="text-sm">{notice}</p> : null}
          <Panel title="Configuration">
            <KeyValue rows={[
              ["Name", cfg.data.name], ["Version", String(cfg.data.version)],
              ["State", <StatusLabel key="s" tone={cfg.data.state === "approved" ? "ok" : cfg.data.state === "evaluation_failed" || cfg.data.state === "rejected" ? "warn" : "neutral"}>{STATE_LABEL[cfg.data.state] ?? cfg.data.state}</StatusLabel>],
              ["Content hash", <span key="h" className="font-mono text-xs">{cfg.data.content_hash}</span>], ["Catalogue", cfg.data.catalogue_version],
              ["Author", cfg.data.created_by_email ?? ""], ["Active in", cfg.data.active_in.length ? cfg.data.active_in.join(", ") : "Not active"],
              ["Notes", cfg.data.notes || "None"],
            ]} />
            <div className="flex flex-wrap gap-2">
              <button type="button" className={btn} onClick={() => cfg.reload()}>Refresh</button>
              {canManage && cfg.data.state === "draft" ? <button type="button" className={btn} onClick={() => setAction("validate")}>Validate</button> : null}
              {canManage && ["validated", "evaluation_failed", "evaluated"].includes(cfg.data.state) ? <button type="button" className={btn} onClick={() => setAction("evaluate")}>Evaluate</button> : null}
              {canManage && cfg.data.state === "evaluated" && cfg.data.latest_evaluation_passed && !cfg.data.approvals.some((a) => a.status === "pending") ? (
                <button type="button" className={btn} onClick={() => setAction("request")}>Submit for approval</button>
              ) : null}
              {canManage && cfg.data.state !== "retired" && cfg.data.active_in.length === 0 ? <button type="button" className={btn} onClick={() => setAction("retire")}>Retire</button> : null}
            </div>
          </Panel>

          {cfg.data.state === "draft" && canManage && catalogue.state === "ready" ? (
            <Editor v={cfg.data} catalogue={catalogue.data} onSaved={() => { setNotice("Draft saved."); cfg.reload(); }} />
          ) : (
            <Panel title="Settings (frozen)">
              <Settings v={cfg.data} />
            </Panel>
          )}

          <Panel title="Changes from the code defaults">
            {cfg.data.changed_from_baseline.length === 0 ? <p className="text-sm text-muted">This configuration matches the code defaults exactly.</p> : (
              <ul className="grid gap-1 text-sm">
                {cfg.data.changed_from_baseline.map((c) => <li key={c.field}><strong>{label(c.field.replace(/\./g, " "))}</strong>: {String(c.baseline)} to {String(c.value)}</li>)}
              </ul>
            )}
          </Panel>

          <Panel title="Validation checks">
            {cfg.data.validation.length === 0 ? <p className="text-sm text-muted">Not validated yet.</p> : <Checks checks={cfg.data.validation} />}
          </Panel>

          <Panel title="Evaluations">
            <p className="text-xs text-muted">A deterministic check of this exact content against the real resolution code. It evidences that the configuration is safe and consistent. It is not a measure of live answer quality, and no live model is called.</p>
            {cfg.data.evaluations.length === 0 ? <p className="text-sm text-muted">Not evaluated yet.</p> : cfg.data.evaluations.map((e) => (
              <div key={e.public_id} className="rounded border border-default p-3">
                <p className="text-sm"><StatusLabel tone={e.status === "passed" ? "ok" : e.status === "failed" || e.status === "error" ? "warn" : "neutral"}>{label(e.status)}</StatusLabel>{" "}
                  Hash <span className="font-mono text-xs">{shortHash(e.content_hash)}</span>{e.content_hash === cfg.data.content_hash ? " (matches this content)" : " (does not match this content)"} · {e.evaluator_version} · live calls: {e.live_calls}</p>
                {e.failure_category ? <p className="text-sm">Failure category: {label(e.failure_category)}</p> : null}
                {e.checks.length ? <Checks checks={e.checks} /> : null}
              </div>
            ))}
          </Panel>

          <Panel title="Approval">
            {cfg.data.approvals.length === 0 ? <p className="text-sm text-muted">No approval requested.</p> : cfg.data.approvals.map((a) => {
              const own = (email !== null && (a.requested_by_email === email || cfg.data.created_by_email === email)) || (me !== null && cfg.data.created_by_user_id === me);
              return (
                <div key={a.public_id} className="flex flex-wrap items-center gap-3 text-sm">
                  <StatusLabel tone={a.status === "approved" ? "ok" : a.status === "pending" ? "neutral" : "warn"}>{label(a.status)}</StatusLabel>
                  <span>Requested by {a.requested_by_email ?? "unknown"}{a.decided_by_email ? `, decided by ${a.decided_by_email}` : ""}</span>
                  {a.status === "pending" && canActivate ? (own ? <span className="text-muted">A different administrator must decide this request (you requested or authored it).</span> : (
                    <>
                      <button type="button" className={btn} onClick={() => setAction("approve")}>Approve</button>
                      <button type="button" className={btn} onClick={() => setAction("reject")}>Reject</button>
                    </>
                  )) : null}
                </div>
              );
            })}
          </Panel>

          <Panel title="Activation">
            {cfg.data.state !== "approved" ? <p className="text-sm text-muted">Only an approved configuration can be activated. It needs a passed evaluation and a different second approver first.</p> : canActivate ? (
              <div className="flex flex-wrap items-center gap-2">
                {(() => {
                  const supported = ["development", "staging", "production"].includes(thisEnv);
                  const needsStaging = thisEnv === "production" && !cfg.data.activations.some((a) => a.environment === "staging");
                  return (
                    <>
                      <button type="button" className={btn} onClick={() => setAction("activate")} disabled={!supported || needsStaging || cfg.data.active_in.includes(thisEnv)}>
                        {supported ? `Activate in ${thisEnv}` : "Activation unavailable"}
                      </button>
                      {!supported && thisEnv ? <span className="text-sm text-muted">This deployment&apos;s environment is not recognised, so governed activation is disabled.</span> : null}
                      {needsStaging ? <span className="text-sm text-muted">Production needs a prior staging activation of this exact content. A development activation does not count.</span> : null}
                    </>
                  );
                })()}
              </div>
            ) : <p className="text-sm text-muted">You can view this configuration but your role cannot activate it.</p>}
            {cfg.data.activations.length ? (
              <ul className="grid gap-1 text-sm">
                {cfg.data.activations.map((a) => <li key={a.public_id}>{a.activated_at ?? ""} · {a.environment} · {KIND_LABEL[a.kind] ?? a.kind}{a.open ? " (current)" : ""} · {a.activated_by_email ?? ""}</li>)}
              </ul>
            ) : null}
          </Panel>

          <ActionDialog open={action !== null} title={action ? COPY[action].title : ""} confirmLabel={action ? COPY[action].button : ""}
            askReason={action ? COPY[action].reason : false} reasonRequired={action ? COPY[action].reason : false}
            onClose={() => setAction(null)} onConfirm={(reason) => run(cfg.data, reason)}>
            <p className="text-sm">{action ? COPY[action].body : ""}</p>
          </ActionDialog>
        </div>
      ) : null}
    </ResourceState>
  );
}

function Checks({ checks }: { checks: { code: string; label: string; passed: boolean; detail: string }[] }) {
  return (
    <ul className="grid gap-1 text-sm">
      {checks.map((c) => (
        <li key={c.code}><StatusLabel tone={c.passed ? "ok" : "warn"}>{c.passed ? "Passed" : "Failed"}</StatusLabel> {c.label}{c.passed ? "" : `: ${c.detail}`}</li>
      ))}
    </ul>
  );
}

function Settings({ v }: { v: AIVersionDetail }) {
  return (
    <div className="grid gap-3">
      <KeyValue rows={Object.entries(v.settings.profiles).map(([p, c]) => [`${p[0].toUpperCase()}${p.slice(1)} profile`, c] as [string, string])} />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Operation settings</caption>
          <thead><tr className="text-xs text-muted">{["Operation", ...Object.values(TUNABLE_LABEL)].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
          <tbody>
            {Object.entries(v.settings.operations).map(([op, t]) => (
              <tr key={op} className="border-t border-default">
                <th scope="row" className="py-1 pr-4 text-left font-medium">{label(op)}</th>
                {Object.keys(TUNABLE_LABEL).map((k) => <td key={k} className="py-1 pr-4">{t[k]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Editor({ v, catalogue, onSaved }: { v: AIVersionDetail; catalogue: AICatalogue; onSaved: () => void }) {
  const [profiles, setProfiles] = useState<Record<string, string>>(v.settings.profiles);
  const [ops, setOps] = useState<Record<string, Record<string, string>>>({});
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setProfiles(v.settings.profiles);
    setOps(Object.fromEntries(Object.entries(v.settings.operations).map(([op, t]) => [op, Object.fromEntries(Object.entries(t).map(([k, n]) => [k, String(n)]))])));
  }, [v.content_hash, v.settings.profiles, v.settings.operations]);
  const save = async () => {
    setErr(null);
    try {
      const operations = Object.fromEntries(Object.entries(ops).map(([op, t]) => [op, Object.fromEntries(Object.entries(t).map(([k, s]) => [k, Number(s)]))]));
      await api.admin.aiUpdate(v.public_id, { settings: { profiles, operations } });
      onSaved();
    } catch (e) {
      setErr(apiMessage(e));
    }
  };
  return (
    <Panel title="Edit draft">
      <p className="text-xs text-muted">Pick an approved catalogue entry for each profile and set bounded numbers. Provider model names cannot be typed here.</p>
      <div className="grid gap-2 sm:grid-cols-3">
        {["fast", "balanced", "advanced"].map((p) => (
          <label key={p} className="grid gap-1 text-sm capitalize">{p} profile
            <select className={field} value={profiles[p] ?? ""} onChange={(e) => setProfiles({ ...profiles, [p]: e.target.value })}>
              {catalogue.items.map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
            </select>
          </label>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Operation settings</caption>
          <thead><tr className="text-xs text-muted"><th scope="col" className="py-1 pr-4 font-medium">Operation</th>{Object.values(TUNABLE_LABEL).map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
          <tbody>
            {Object.entries(ops).map(([op, t]) => (
              <tr key={op} className="border-t border-default">
                <th scope="row" className="py-1 pr-4 text-left font-medium">{label(op)}</th>
                {Object.keys(TUNABLE_LABEL).map((k) => (
                  <td key={k} className="py-1 pr-4">
                    <input className={`${field} w-24`} inputMode="decimal" aria-label={`${label(op)} ${TUNABLE_LABEL[k]}`} value={t[k] ?? ""}
                      onChange={(e) => setOps({ ...ops, [op]: { ...t, [k]: e.target.value } })} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {err ? <p role="alert" className="text-sm">{err}</p> : null}
      <div><button type="button" className={btn} onClick={save}>Save draft</button></div>
    </Panel>
  );
}
