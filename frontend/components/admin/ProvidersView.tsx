"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, useAdminResource, ScrollRegion } from "./ui";

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
            <ScrollRegion label="Provider configuration status (scrollable table)">
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
                        {/* 04D (DEMO-02): the mode of the connection (for the language model: live, offline, not_configured or unknown) so a keyless or offline stack cannot be mistaken for live. Configuration, not health. */}
                        {p.mode ? <span className="ml-2 text-xs text-muted" data-testid={`provider-mode-${p.provider_id}`}>{`Mode: ${p.mode}`}</span> : null}
                      </td>
                      <td className="py-1 pr-4">{p.health}</td>
                      <td className="py-1 pr-4">{p.externally_managed ? "Deployment environment" : "Console"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
            <p className="text-xs text-muted">{loaded.data.note}</p>
            <p className="text-xs text-muted">Credentials, runtime state, health and manual tests for each connection are on <Link href="/admin/integrations" className="underline underline-offset-2">Integrations</Link>. This page is the configuration-only summary and does not show health.</p>
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
