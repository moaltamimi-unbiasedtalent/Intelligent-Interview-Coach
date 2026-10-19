"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { Panel, StatusLabel, useAdminResource } from "./ui";

// Derived capability readiness (W12.4F). Read-only: every row is computed by the server from existing sources. A status here never means "production ready".

const LABEL: Record<string, string> = {
  OPERATIONAL: "Operational", CONFIGURED_BUT_UNAVAILABLE: "Configured but unavailable", ENVIRONMENT_MANAGED: "Environment-managed", MOCK: "Mock", READ_ONLY: "Read-only",
  PARTIAL: "Partial", NOT_BUILT: "Not built",
};
const QUALIFIER: Record<string, string> = { OFFLINE_VALIDATED: "Offline validated", LIVE_UNVERIFIED: "Live unverified", DEFERRED: "Deferred", UNAVAILABLE: "Unavailable", DISABLED: "Disabled" };

export function CapabilityReadiness() {
  const loaded = useAdminResource(() => Promise.resolve().then(() => api.admin.readiness()), []);
  if (loaded.state !== "ready") return null;
  const { capabilities, boundary } = loaded.data;
  // A malformed or empty response is shown as nothing (never as a fabricated status or a render crash).
  if (!Array.isArray(capabilities) || capabilities.length === 0) return null;
  return (
    <Panel title="Capability readiness">
      <p className="text-xs text-muted">{boundary}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Capability readiness</caption>
          <thead><tr className="text-xs text-muted">{["Capability", "Status", "Evidence and limits", "Managed by"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
          <tbody>
            {capabilities.map((c) => (
              <tr key={c.id} className="border-t border-default align-top">
                <th scope="row" className="py-1 pr-4 text-left font-medium">
                  {c.admin_path ? <Link href={c.admin_path} className="underline underline-offset-2">{c.label}</Link> : c.label}
                </th>
                <td className="py-1 pr-4">
                  <StatusLabel tone={c.status === "OPERATIONAL" ? "ok" : c.status === "CONFIGURED_BUT_UNAVAILABLE" ? "warn" : "neutral"}>{LABEL[c.status] ?? c.status}</StatusLabel>
                  {c.qualifiers.length ? <div className="mt-1 text-xs text-muted">{c.qualifiers.map((q) => QUALIFIER[q] ?? q).join(" · ")}</div> : null}
                </td>
                <td className="py-1 pr-4">
                  <div>{c.evidence}</div>
                  {c.limitations.length ? <ul className="list-disc pl-4 text-xs text-muted">{c.limitations.map((l) => <li key={l}>{l}</li>)}</ul> : null}
                </td>
                <td className="py-1 pr-4 text-xs">{c.ownership}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
