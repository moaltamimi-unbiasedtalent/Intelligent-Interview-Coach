"use client";

import { useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { IntegrationDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { useStepUp } from "./StepUp";
import { EmailDeliveryPanel } from "./EmailDeliveryPanel";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, Table, apiMessage, btn, field, useAdminResource } from "./ui";

const SOURCE_LABEL = { managed: "Managed secure store", environment: "Environment", none: "Not configured" } as const;
const REASON_COPY: Record<string, string> = {
  key_missing: "its encryption key is not configured in the deployment",
  key_malformed: "its encryption key is not valid",
  store_error: "the store cannot be reached",
  not_bound: "the store cannot be reached",
};

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
  const [removing, setRemoving] = useState<string | null>(null);
  const valueRef = useRef<HTMLInputElement>(null);
  const stepUp = useStepUp();
  const chosen = d.slots.find((c) => c.slot === slot) ?? null;
  const chosenRemoval = d.slots.find((c) => c.slot === removing) ?? null;

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
    // A fresh password step-up is part of the gate: on step_up_required the dialog collects it and the SAME write is retried.
    // The value is held in this closure only for that retry and is cleared when the attempt ends (success, failure or cancel).
    let pending: string | null = value;
    try {
      const saved = await stepUp.run(() => api.admin.replaceCredential(d.code, slot, pending ?? "", chosen?.revision ?? null));
      setNotice(`Credential ${saved.action === "created" ? "configured" : "replaced"}. It is saved but not tested, and its value cannot be viewed from Ask4Mo.`);
      setSlot(null);
      reload();
    } finally {
      pending = null;
    }
  };

  const removeManaged = async () => {
    if (!removing) return;
    await stepUp.run(() => api.admin.removeCredential(d.code, removing, chosenRemoval?.revision ?? null));
    setNotice(chosenRemoval?.environment_fallback
      ? "Managed credential removed. The deployment environment credential is used again."
      : "Managed credential removed. This credential is now not configured.");
    setRemoving(null);
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
        <p className="text-sm" data-testid="store-state">
          {d.store.state === "writable" ? "Secure credential store: writable. Managed credentials are encrypted before they are saved."
            : d.store.state === "unavailable" ? `Secure writable credential store unavailable: ${REASON_COPY[d.store.reason ?? ""] ?? "it cannot be used right now"}.`
            : "Credentials are managed in the deployment environment (read-only). The secure credential store is not enabled for this deployment."}
        </p>
        {d.slots.length === 0 ? <p className="text-sm text-muted">This integration needs no credentials.</p> : (
          <ul className="grid gap-3" aria-label="Credential slots">
            {d.slots.map((c) => (
              <li key={c.slot} className="rounded border border-border px-3 py-2">
                <p className="flex flex-wrap items-center gap-3 text-sm font-medium">
                  {c.label}
                  <StatusLabel tone={c.configured ? "ok" : "neutral"}>{c.configured ? "Configured" : "Not configured"}</StatusLabel>
                </p>
                <p className="text-xs text-muted" data-testid={`source-${c.slot}`}>
                  Source: {SOURCE_LABEL[c.source_kind]}
                  {c.managed && c.last_rotated_at ? `. Last changed ${c.last_rotated_at}` : ""}
                  {c.managed && c.managed_readable === false ? ". The managed credential cannot be read with the current encryption key; the environment value (if any) is used" : ""}
                  {c.source_kind === "environment" && d.store.state !== "writable" ? `. Managed outside Ask4Mo (set ${c.external_name} in the deployment environment); it cannot be viewed or changed here.` : ""}
                  {c.source_kind === "environment" && d.store.state === "writable" ? `. Configuring a managed credential overrides the environment value (${c.external_name}), which is not changed.` : ""}
                </p>
                <p className="text-xs text-muted">{c.applies === "next_use" ? "A new value is used on the next request that needs it." : "A new value is used after the API and worker restart."}</p>
                {c.writable && canRotate ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button type="button" className={btn} onClick={() => setSlot(c.slot)}>{c.managed ? "Replace credential" : "Configure credential"}</button>
                    {c.managed ? <button type="button" className={btn} onClick={() => setRemoving(c.slot)}>Remove managed credential</button> : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted">Ask4Mo never displays a credential, part of one, or a masked form of one. Configured only means a value exists, not that it is valid or healthy. Saving a credential does not contact the provider.</p>
      </Panel>

      <Panel title="Settings and runtime">
        <KeyValue rows={[
          ...d.settings.map((s): [string, string] => [s.label, s.selected ?? "not set"]),
          ["Runtime state", d.runtime.enabled === null ? "Not applicable" : d.runtime.enabled ? "On" : "Off"],
          ["Runtime state managed by", "Deployment environment (read-only)"],
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

      {d.code === "email_brevo" ? <EmailDeliveryPanel canTest={canTest} onChanged={reload} /> : null}

      <Panel title="Recent management events">
        <Table caption="Integration audit" rows={d.audit.map((e) => ({ ...e, detail: e.context ? Object.entries(e.context).map(([k, v]) => `${k}: ${String(v)}`).join(", ") : "" }))}
          cols={["created_at", "event_type", "result", "actor_user_id", "detail", "request_id"]} />
      </Panel>

      <ActionDialog open={slot !== null} title={chosen?.managed ? "Replace this credential?" : "Configure this credential?"} confirmLabel="Save credential" askReason={false}
        onClose={() => setSlot(null)}
        onConfirm={async () => {
          try {
            await submitCredential();
          } finally {
            if (valueRef.current) valueRef.current.value = "";
          }
        }}>
        <p>{chosen?.managed ? "The previous value cannot be viewed from Ask4Mo and is discarded." : "This managed value will override any deployment environment value."} The new value is write-only: it is saved once, encrypted, and never shown again.</p>
        <label className="grid gap-1 text-xs text-muted">
          {chosen?.managed ? "New credential" : "Credential"}
          <input ref={valueRef} type="password" autoComplete="off" spellCheck={false} minLength={chosen?.min_length} maxLength={chosen?.max_length} className={field} />
        </label>
      </ActionDialog>

      <ActionDialog open={removing !== null} title="Remove the managed credential?" confirmLabel="Remove" askReason={false}
        onClose={() => setRemoving(null)} onConfirm={removeManaged}>
        <p>
          This deletes the Admin-managed credential only.{" "}
          {chosenRemoval?.environment_fallback ? "The deployment environment credential will be used again." : "No environment credential exists, so this credential will be not configured."}
        </p>
      </ActionDialog>
      {stepUp.dialog}
    </div>
  );
}
