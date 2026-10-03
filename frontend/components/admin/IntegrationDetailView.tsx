"use client";

import { useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { IntegrationDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, Table, apiMessage, btn, field, useAdminResource } from "./ui";

export function IntegrationDetailView({ code }: { code: string }) {
  return (
    <PermissionGate anyOf={[P.integrations]}>
      <Body code={code} />
    </PermissionGate>
  );
}

function Body({ code }: { code: string }) {
  const loaded = useAdminResource(() => api.admin.integration(code), [code]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

function Detail({ d, reload }: { d: IntegrationDetail; reload: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canTest = hasAnyPermission(granted, [P.integrationsManage]);
  const canRotate = hasAnyPermission(granted, [P.secretRotate]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slot, setSlot] = useState<string | null>(null);
  const valueRef = useRef<HTMLInputElement>(null);

  const runTest = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.admin.testIntegration(d.code);
      setNotice(r.outcome === "success" ? "Connection test succeeded." : `Connection test failed (${r.category.replace(/_/g, " ")}).`);
      reload();
    } catch (e) {
      setError(apiMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // Write-only: the value lives in an uncontrolled input, is sent once and cleared immediately. It is never held in
  // React state, never shown back, and the response contains no value.
  const submitCredential = async () => {
    if (!slot || !valueRef.current) return;
    const value = valueRef.current.value;
    valueRef.current.value = "";
    await api.admin.replaceCredential(d.code, slot, value);
    setNotice("Credential saved. The value cannot be viewed from Ask4Mo.");
    setSlot(null);
    reload();
  };

  const h = d.health;
  return (
    <div className="grid gap-4">
      <p><Link href="/admin/integrations" className="text-sm underline underline-offset-2">Back to integrations</Link></p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      {error ? <p role="alert" className="text-sm">{error}</p> : null}

      <Panel title="Overview">
        <KeyValue rows={[["Name", d.name], ["Code", d.code], ["Category", d.category_label], ["Adapter", d.adapter],
          ["Support state", d.classification.replace(/_/g, " ")], ["Description", d.description]]} />
        <p className="text-xs text-muted">{d.validation_note}</p>
      </Panel>

      <Panel title="Credentials">
        {d.slots.length === 0 ? <p className="text-sm text-muted">This integration needs no credentials.</p> : (
          <ul className="grid gap-3" aria-label="Credential slots">
            {d.slots.map((c) => (
              <li key={c.slot} className="rounded border border-border px-3 py-2">
                <p className="flex flex-wrap items-center gap-3 text-sm font-medium">
                  {c.label}
                  <StatusLabel tone={c.configured ? "ok" : "neutral"}>{c.configured ? "Configured" : "Not configured"}</StatusLabel>
                </p>
                <p className="text-xs text-muted">
                  Source: {c.source === "none" ? "none" : c.source.replace(/_/g, " ")}
                  {c.writable ? "" : `. Managed outside Ask4Mo (set ${c.external_name} in the deployment environment); it cannot be viewed or changed here.`}
                </p>
                {c.writable && canRotate ? (
                  <button type="button" className={`${btn} mt-2`} onClick={() => setSlot(c.slot)}>{c.configured ? "Replace credential" : "Set credential"}</button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted">Ask4Mo never displays a credential, part of one, or a masked form of one. Configured only means a value exists, not that it is valid.</p>
      </Panel>

      <Panel title="Settings and runtime">
        <KeyValue rows={[
          ...d.settings.map((s): [string, string] => [s.label, s.selected ?? "not set"]),
          ["Runtime state", d.runtime.enabled === null ? "Not applicable" : d.runtime.enabled ? "On" : "Off"],
          ["Managed by", "Deployment environment (read-only)"],
        ]} />
        <p className="text-xs text-muted">{d.runtime.note}</p>
      </Panel>

      <Panel title="Connection test">
        <KeyValue rows={[
          ["Health", h.status === "not_tested" ? "Not tested" : h.status === "healthy" ? "Last test succeeded" : "Last test failed"],
          ["Last tested", h.last_tested_at ?? "never"], ["Result", h.category ? h.category.replace(/_/g, " ") : "none"],
          ["Latency", h.latency_ms === null ? "not recorded" : `${h.latency_ms} ms`],
        ]} />
        <p className="text-xs text-muted">{d.test.note} Tests run only when you start one; nothing is checked automatically.</p>
        {d.test.supported && canTest ? (
          <div><button type="button" className={btn} disabled={busy} onClick={runTest}>{busy ? "Testing..." : "Test connection"}</button></div>
        ) : null}
        {!d.test.supported ? <p className="text-sm text-muted">A manual test is not available for this integration.</p> : null}
      </Panel>

      <Panel title="Recent management events">
        <Table caption="Integration audit" rows={d.audit.map((e) => ({ ...e, detail: e.context ? Object.entries(e.context).map(([k, v]) => `${k}: ${String(v)}`).join(", ") : "" }))}
          cols={["created_at", "event_type", "result", "actor_user_id", "detail", "request_id"]} />
      </Panel>

      <ActionDialog open={slot !== null} title="Replace this credential?" confirmLabel="Save credential" askReason={false}
        onClose={() => setSlot(null)}
        onConfirm={async () => {
          try {
            await submitCredential();
          } finally {
            if (valueRef.current) valueRef.current.value = "";
          }
        }}>
        <p>The previous value cannot be viewed from Ask4Mo. The new value is write-only: it is saved once and never shown again.</p>
        <label className="grid gap-1 text-xs text-muted">
          New credential
          <input ref={valueRef} type="password" autoComplete="off" spellCheck={false} className={field} />
        </label>
      </ActionDialog>
    </div>
  );
}
