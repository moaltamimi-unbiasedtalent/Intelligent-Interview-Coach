"use client";

import { useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { FlagState } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, btn, useAdminResource } from "./ui";

// Code-defined feature flags with durable overrides. A flag can only RESTRICT availability: it never grants permission, entitlement, billing or AI
// changes. There is no create control and no generic key/value editor.

const STATE: Record<FlagState["state"], string> = { inherited: "Inherited baseline", enabled_override: "Enabled override", disabled_override: "Disabled override" };

export function FlagsView() {
  return (
    <PermissionGate anyOf={[P.flagsRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const auth = useAuthOptional();
  const canManage = hasAnyPermission(adminPermissions(auth?.account), [P.flagsManage]);
  const data = useAdminResource(() => api.admin.flags(), []);
  const [change, setChange] = useState<null | { flag: FlagState; to: boolean | null }>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const verb = (to: boolean | null) => (to === null ? "Reset to inherited baseline" : to ? "Enable override" : "Disable override");

  return (
    <div className="grid gap-4">
      <ResourceState loaded={data}>
        {data.state === "ready" ? (
          <>
            <p className="text-sm">Environment: <strong>{data.data.environment}</strong> (decided by this server). {data.data.note}</p>
            {notice ? <p role="status" className="text-sm">{notice}</p> : null}
            {data.data.items.map((f) => (
              <Panel key={f.flag_id} title={f.display_name}>
                <p className="text-sm">{f.description}</p>
                <KeyValue rows={[
                  ["Flag", f.flag_id], ["Baseline", `${f.baseline ? "On" : "Off"} (${f.baseline_source})`],
                  ["State", <StatusLabel key="s" tone={f.state === "disabled_override" ? "warn" : f.state === "enabled_override" ? "ok" : "neutral"}>{STATE[f.state]}</StatusLabel>],
                  ["Effective value", f.effective ? "On" : "Off"], ["Revision", String(f.revision)], ["Last change", f.updated_at ?? "Never changed"],
                  ["Candidate visible", f.candidate_visible ? "Yes" : "No"], ["Notes", f.notes],
                ]} />
                {canManage ? (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className={btn} onClick={() => setChange({ flag: f, to: true })} disabled={f.state === "enabled_override"} aria-label={`Enable override for ${f.display_name}`}>Enable override</button>
                    <button type="button" className={btn} onClick={() => setChange({ flag: f, to: false })} disabled={f.state === "disabled_override"} aria-label={`Disable override for ${f.display_name}`}>Disable override</button>
                    <button type="button" className={btn} onClick={() => setChange({ flag: f, to: null })} disabled={f.state === "inherited"} aria-label={`Reset ${f.display_name} to inherited baseline`}>Reset to inherited baseline</button>
                  </div>
                ) : <p className="text-xs text-muted">Your role can view flags but cannot change them.</p>}
              </Panel>
            ))}
            <Panel title="Not configurable here">
              <p className="text-xs text-muted">These deployment settings are deliberately not feature flags: credentials, security, integrations, billing, AI and entitlements are owned elsewhere.</p>
              <ul className="grid gap-1 text-sm">
                {Object.entries(data.data.not_mutable).map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}
              </ul>
            </Panel>
          </>
        ) : null}
      </ResourceState>
      <ActionDialog open={change !== null} title={change ? `${verb(change.to)}: ${change.flag.display_name}?` : ""} confirmLabel={change ? verb(change.to) : ""} reasonRequired
        onClose={() => setChange(null)}
        onConfirm={async (reason) => {
          if (!change) return;
          await api.admin.setFlag(change.flag.flag_id, change.to, change.flag.revision, reason);
          setNotice(`${change.flag.display_name}: ${STATE[change.to === null ? "inherited" : change.to ? "enabled_override" : "disabled_override"].toLowerCase()}.`);
          data.reload();
        }}>
        <p className="text-sm">A flag only restricts availability: it cannot create a permission, an entitlement or a plan. Candidates and the backend both follow the effective value.</p>
      </ActionDialog>
    </div>
  );
}
