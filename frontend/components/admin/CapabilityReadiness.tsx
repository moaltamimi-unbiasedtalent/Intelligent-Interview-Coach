"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import type { CapabilityReadinessRow } from "@/lib/admin/types";
import { Panel, StatusLabel, useAdminResource, ScrollRegion } from "./ui";

// Derived capability readiness (W12.4F). Read-only: every row is computed by the server from existing sources. A status here never means "production ready".

const LABEL: Record<string, string> = {
  OPERATIONAL: "Operational", CONFIGURED_BUT_UNAVAILABLE: "Configured but unavailable", ENVIRONMENT_MANAGED: "Environment-managed", MOCK: "Mock", READ_ONLY: "Read-only",
  PARTIAL: "Partial", NOT_BUILT: "Not built",
};
const QUALIFIER: Record<string, string> = { OFFLINE_VALIDATED: "Offline validated", LIVE_UNVERIFIED: "Live unverified", DEFERRED: "Deferred", UNAVAILABLE: "Unavailable", DISABLED: "Disabled" };

const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");

/** A readiness row is rendered only when every field the table reads is present with the right type and a known status; anything else is treated as an unavailable response. */
export function isValidCapabilityRow(r: unknown): r is CapabilityReadinessRow {
  if (!r || typeof r !== "object") return false;
  const c = r as Record<string, unknown>;
  return typeof c.id === "string" && c.id !== "" && typeof c.label === "string" && c.label !== "" && typeof c.status === "string" && Object.hasOwn(LABEL, c.status)
    && strings(c.qualifiers) && typeof c.ownership === "string" && typeof c.evidence === "string" && strings(c.limitations)
    && (c.admin_path === null || typeof c.admin_path === "string");
}

export function CapabilityReadiness() {
  const loaded = useAdminResource(() => Promise.resolve().then(() => api.admin.readiness()), []);
  if (loaded.state === "loading") return null;
  const data = loaded.state === "ready" ? loaded.data : null;
  const capabilities = data?.capabilities;
  const boundary = data?.boundary;
  // W12.5: a failed, malformed or empty response is an explicit, accessible unavailable state. No readiness data is ever invented, and the Command Center never crashes.
  if (!Array.isArray(capabilities) || capabilities.length === 0 || !capabilities.every(isValidCapabilityRow)) {
    return (
      <Panel title="Capability readiness">
        <p role="status" className="text-sm">Capability readiness is unavailable right now. No status is shown rather than guessing one. Reload the page to try again; the individual pages for each area are still available from the navigation.</p>
      </Panel>
    );
  }
  return (
    <Panel title="Capability readiness">
      <p className="text-xs text-muted">{boundary}</p>
      {/* Below md each capability is a labelled card (no column dropped); from md up it is a table inside a keyboard-scrollable region. Explicit roles keep table semantics. */}
      <ScrollRegion label="Capability readiness (scrollable table)">
        <table role="table" className="w-full text-left text-sm max-md:block">
          <caption className="sr-only">Capability readiness</caption>
          <thead role="rowgroup" className="max-md:sr-only"><tr role="row" className="text-xs text-muted">{["Capability", "Status", "Evidence and limits", "Managed by"].map((c) => <th key={c} role="columnheader" scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
          <tbody role="rowgroup" className="max-md:grid max-md:gap-3">
            {capabilities.map((c) => (
              <tr key={c.id} role="row" className="border-t border-default align-top max-md:block max-md:rounded-lg max-md:border max-md:border-border max-md:px-3 max-md:py-2">
                <th role="rowheader" scope="row" className="py-1 pr-4 text-left font-medium max-md:block max-md:pr-0">
                  {c.admin_path ? <Link href={c.admin_path} className="underline underline-offset-2">{c.label}</Link> : c.label}
                </th>
                <td role="cell" className="py-1 pr-4 max-md:block max-md:pr-0">
                  <StatusLabel tone={c.status === "OPERATIONAL" ? "ok" : c.status === "CONFIGURED_BUT_UNAVAILABLE" ? "warn" : "neutral"}>{LABEL[c.status] ?? c.status}</StatusLabel>
                  {c.qualifiers.length ? <div className="mt-1 text-xs text-muted">{c.qualifiers.map((q) => QUALIFIER[q] ?? q).join(" · ")}</div> : null}
                </td>
                <td role="cell" className="py-1 pr-4 max-md:block max-md:pr-0">
                  <div>{c.evidence}</div>
                  {c.limitations.length ? <ul className="list-disc pl-4 text-xs text-muted">{c.limitations.map((l) => <li key={l}>{l}</li>)}</ul> : null}
                </td>
                <td role="cell" className="py-1 pr-4 text-xs max-md:block max-md:pr-0 max-md:pt-1"><span className="text-muted md:hidden">Managed by: </span>{c.ownership}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </Panel>
  );
}
