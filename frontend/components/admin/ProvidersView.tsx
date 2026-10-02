"use client";

import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, useAdminResource } from "./ui";

export function ProvidersView() {
  return (
    <PermissionGate anyOf={[P.integrations]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const loaded = useAdminResource(() => api.admin.providers());
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? (
        <div className="grid gap-4">
          <Panel title="Providers">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Provider configuration status</caption>
                <thead>
                  <tr className="text-xs text-muted">
                    {["Provider", "Configuration", "Health", "Managed"].map((c) => (
                      <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loaded.data.providers.map((p) => (
                    <tr key={p.provider_id} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">{p.label}</th>
                      <td className="py-1 pr-4">
                        <StatusLabel tone={p.configured ? "ok" : "neutral"}>{p.configured ? "Configured" : "Not configured"}</StatusLabel>
                      </td>
                      <td className="py-1 pr-4">{p.health}</td>
                      <td className="py-1 pr-4">{p.externally_managed ? "Deployment environment" : "Console"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted">{loaded.data.note}</p>
          </Panel>
          <Panel title="Document OCR">
            <KeyValue
              rows={[
                ["Engine", loaded.data.ocr.engine],
                ["Available", loaded.data.ocr.available ? "Yes" : "No"],
                ["Scanned PDF OCR", loaded.data.ocr.pdf_ocr_available ? "Yes" : "No"],
                ["Live quality", loaded.data.ocr.live_quality],
              ]}
            />
          </Panel>
        </div>
      ) : null}
    </ResourceState>
  );
}
