"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { Panel, PermissionGate, ResourceState, StatusLabel, useAdminResource } from "./ui";

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

function Body() {
  const loaded = useAdminResource(() => api.admin.integrations());
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        These are the external connections Ask4Mo has code for. Configuration, runtime state and health are separate: supported is not
        connected, configured is not healthy, and only an explicit manual test can show a successful connection. Credentials are managed
        outside Ask4Mo and are never shown.
      </p>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Supported connections">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Integrations</caption>
                <thead>
                  <tr className="text-xs text-muted">
                    {["Integration", "Category", "Status", "Credentials", "Health", "Last tested"].map((c) => (
                      <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loaded.data.items.map((i) => (
                    <tr key={i.code} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">
                        <Link href={`/admin/integrations/${i.code}`} className="underline underline-offset-2">{i.name}</Link>
                      </th>
                      <td className="py-1 pr-4">{i.category_label}</td>
                      <td className="py-1 pr-4">{CLASS_LABEL[i.classification] ?? i.classification}</td>
                      <td className="py-1 pr-4">
                        {i.slots.length === 0 ? "None needed" : (
                          <StatusLabel tone={i.configuration_status === "configured" ? "ok" : "neutral"}>
                            {i.configuration_status === "configured" ? "Configured" : i.configuration_status === "partially_configured" ? "Partly configured" : "Not configured"}
                          </StatusLabel>
                        )}
                      </td>
                      <td className="py-1 pr-4">
                        <StatusLabel tone={i.health.status === "healthy" ? "ok" : i.health.status === "unhealthy" ? "warn" : "neutral"}>
                          {HEALTH_LABEL[i.health.status]}
                        </StatusLabel>
                      </td>
                      <td className="py-1 pr-4">{i.health.last_tested_at ?? "never"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}
