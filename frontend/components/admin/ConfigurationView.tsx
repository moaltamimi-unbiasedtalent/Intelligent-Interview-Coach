"use client";

import { useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { PauseState } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, btn, useAdminResource } from "./ui";

// Durable platform pause (SEC-W10-05 closed in W10.11). The state lives in the database and is shared by every process. The server decides the
// environment; nothing here can name one. This page is NOT an environment-variable, secret or JSON editor.

const NAMES: Record<string, string> = {
  agent: "Mo (agent) runs", current_market: "External market research", ocr: "Document OCR", realtime_voice: "Realtime voice sessions",
  public_registration: "Open registration",
};

export function ConfigurationView() {
  return (
    <PermissionGate anyOf={[P.flagsRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const auth = useAuthOptional();
  const canManage = hasAnyPermission(adminPermissions(auth?.account), [P.configManage]);
  const data = useAdminResource(() => api.admin.pause(), []);
  const [target, setTarget] = useState<PauseState | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const anyPaused = data.state === "ready" && data.data.items.some((i) => i.paused);

  return (
    <div className="grid gap-4">
      <ResourceState loaded={data}>
        {data.state === "ready" ? (
          <>
            <section aria-labelledby="runtime-status" className="rounded border-2 border-border p-4">
              <h2 id="runtime-status" className="text-lg font-semibold">Platform runtime: {anyPaused ? "Paused (restricted)" : "Running"}</h2>
              <p className="text-sm">Environment: <strong>{data.data.environment}</strong> (decided by this server). State is durable and shared by every process; it survives a restart.</p>
              <p className="text-sm">{data.data.note}</p>
            </section>
            {notice ? <p role="status" className="text-sm">{notice}</p> : null}
            <Panel title="Pause switches">
              <p className="text-xs text-muted">Pausing refuses NEW candidate activity of that kind. Admin, privacy and account controls, legal pages and saved data stay available, and the job worker keeps running.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Pause switches</caption>
                  <thead><tr className="text-xs text-muted">{["Capability", "State", "Source", "Revision", "Last change", "Internal reason", ""].map((c, i) => <th key={i} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {data.data.items.map((i) => (
                      <tr key={i.capability} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">{NAMES[i.capability] ?? i.capability}</th>
                        <td className="py-1 pr-4"><StatusLabel tone={i.paused ? "warn" : "ok"}>{i.paused ? "Paused" : "Running"}</StatusLabel></td>
                        <td className="py-1 pr-4">{i.source === "override" ? "Durable setting" : i.baseline_paused ? "Deployment baseline (paused)" : "Deployment baseline"}</td>
                        <td className="py-1 pr-4">{i.revision}</td>
                        <td className="py-1 pr-4">{(i.paused ? i.paused_at : i.resumed_at) ?? "Never changed"}</td>
                        <td className="py-1 pr-4">{i.reason || "None"}</td>
                        <td className="py-1 pr-4">
                          {canManage ? (
                            <button type="button" className={btn} onClick={() => setTarget(i)} aria-label={`${i.paused ? "Resume" : "Pause"} ${NAMES[i.capability] ?? i.capability}`}>{i.paused ? "Resume" : "Pause"}</button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!canManage ? <p className="text-xs text-muted">Your role can view the pause state but cannot change it.</p> : null}
            </Panel>
            <Panel title="What this page does not do">
              <KeyValue rows={[["Settings editor", "None: there is no environment-variable, secret, database or JSON editor"], ["Workers", "Not stopped by a pause"], ["Candidates see", "A fixed message only (never your reason)"]]} />
            </Panel>
          </>
        ) : null}
      </ResourceState>
      <ActionDialog open={target !== null} title={target ? `${target.paused ? "Resume" : "Pause"} ${NAMES[target.capability] ?? target.capability}?` : ""}
        confirmLabel={target?.paused ? "Resume" : "Pause"} reasonRequired
        onClose={() => setTarget(null)}
        onConfirm={async (reason) => {
          if (!target) return;
          await api.admin.setPause(target.capability, !target.paused, target.revision, reason);
          setNotice(target.paused ? `${NAMES[target.capability] ?? target.capability} resumed.` : `${NAMES[target.capability] ?? target.capability} paused.`);
          data.reload();
        }}>
        <p className="text-sm">{target?.paused
          ? "New candidate activity of this kind will be accepted again under the existing authorization and entitlement rules."
          : "New candidate activity of this kind will be refused with a fixed message. Saved data, privacy and account controls and Admin recovery stay available."}</p>
      </ActionDialog>
    </div>
  );
}
