"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { Panel, PermissionGate, ResourceState, ScrollRegion, StatusLabel, formatCell, useAdminResource } from "./ui";

export function IntegrationsView() {
  return (
    <PermissionGate anyOf={[P.integrations]}>
      <Body />
    </PermissionGate>
  );
}

const CLASS_LABEL: Record<string, string> = {
  runtime_active: "In use",
  configured_inactive: "Configured, not in use",
  supported_unconfigured: "Supported, not configured",
  code_present_not_validated: "Code present, not validated",
  development_only: "Development only",
};
const HEALTH_LABEL = { not_tested: "Not tested", healthy: "Last test succeeded", unhealthy: "Last test failed" } as const;

function sourceSummary(sources: string[]): string {
  const kinds = new Set(sources.filter((s) => s !== "none"));
  if (kinds.size === 0) return "Not configured";
  if (kinds.size > 1) return "Managed and environment";
  return kinds.has("managed") ? "Managed secure store" : "Environment";
}

function Body() {
  const loaded = useAdminResource(() => api.admin.integrations());
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        These are the external connections Ask4Mo has code for. Configuration, runtime state and health are separate: supported is not
        connected, configured is not healthy, and only an explicit manual test can show a successful connection. Credentials are either
        managed here in the encrypted store or set in the deployment environment, and are never shown.
      </p>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Supported connections">
            <p className="text-xs text-muted">Related: <Link href="/admin/providers" className="underline underline-offset-2">Provider status</Link> shows the same providers as a configuration-only summary with document OCR.</p>
            {/* W12.5 (F-04): below md each row is a labelled card (no column is dropped or clipped); from md up it is a normal table inside a keyboard-scrollable region. Explicit
                roles keep the table semantics when the rows are displayed as blocks. */}
            <ScrollRegion label="Integrations (scrollable table)">
              <table role="table" className="w-full text-left text-sm max-md:block">
                <caption className="sr-only">Integrations</caption>
                <thead role="rowgroup" className="max-md:sr-only">
                  <tr role="row" className="text-xs text-muted">
                    {["Integration", "Category", "Status", "Credentials", "Source", "Health", "Last tested"].map((c) => (
                      <th key={c} role="columnheader" scope="col" className="py-1 pr-4 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody role="rowgroup" className="max-md:grid max-md:gap-3">
                  {loaded.data.items.map((i) => {
                    const cell = "py-1 pr-4 max-md:flex max-md:justify-between max-md:gap-3 max-md:py-1.5 max-md:pr-0 max-md:before:shrink-0 max-md:before:text-xs max-md:before:text-muted max-md:before:content-[attr(data-label)]";
                    return (
                      <tr key={i.code} role="row" className="border-t border-default max-md:block max-md:rounded-lg max-md:border max-md:border-border max-md:px-3 max-md:py-2">
                        <th role="rowheader" scope="row" className="py-1 pr-4 text-left font-medium max-md:block max-md:pr-0">
                          <Link href={`/admin/integrations/${i.code}`} className="inline-flex min-h-[44px] items-center underline underline-offset-2">{i.name}</Link>
                        </th>
                        <td role="cell" data-label="Category" className={cell}><span className="max-md:text-right">{i.category_label}</span></td>
                        <td role="cell" data-label="Status" className={cell}><span className="max-md:text-right">{CLASS_LABEL[i.classification] ?? i.classification}</span></td>
                        <td role="cell" data-label="Credentials" className={cell}>
                          {i.slots.length === 0 ? "None needed" : (
                            <StatusLabel tone={i.configuration_status === "configured" ? "ok" : "neutral"}>
                              {i.configuration_status === "configured" ? "Configured" : i.configuration_status === "partially_configured" ? "Partly configured" : "Not configured"}
                            </StatusLabel>
                          )}
                        </td>
                        <td role="cell" data-label="Source" className={cell}><span className="max-md:text-right">{i.slots.length === 0 ? "n/a" : sourceSummary(i.slots.map((s) => s.source_kind))}</span></td>
                        <td role="cell" data-label="Health" className={cell}>
                          <StatusLabel tone={i.health.status === "healthy" ? "ok" : i.health.status === "unhealthy" ? "warn" : "neutral"}>
                            {HEALTH_LABEL[i.health.status]}
                          </StatusLabel>
                        </td>
                        <td role="cell" data-label="Last tested" className={cell}><span className="max-md:text-right">{i.health.last_tested_at ? formatCell(i.health.last_tested_at) : "never"}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </ScrollRegion>
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}
