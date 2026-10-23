"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import type { AdminMonitoring } from "@/lib/admin/types";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, useAdminResource, ScrollRegion } from "./ui";

export function ProvidersView() {
  return (
    <PermissionGate anyOf={[P.integrations]}>
      <Body />
    </PermissionGate>
  );
}

const SIGNAL_LABELS: Record<string, string> = {
  api_error_rate: "API error rate",
  provider_health: "Language model provider",
  worker_health: "Background worker",
  job_backlog: "Job queue",
  indexing_progress: "Knowledge indexing",
  quota_reaper: "Usage reservation release",
  ai_budget: "AI budget",
};
const SIGNAL_TONE = { ok: "ok", failing: "warn", unknown: "neutral" } as const;
const SIGNAL_TEXT = { ok: "OK", failing: "Failing", unknown: "No evidence yet" } as const;

/** Alert and AI budget state (05C). The payload is validated here: a malformed shape shows an explicit unavailable state, never a crash and never a healthy-looking value. */
export function MonitoringPanel({ monitoring }: { monitoring: unknown }) {
  const m = monitoring as AdminMonitoring | null | undefined;
  const valid =
    !!m && typeof m === "object" && !!m.alerts && typeof m.alerts.active === "number" && Array.isArray(m.signals) &&
    m.signals.every((s) => s && typeof s.code === "string" && (s.status === "ok" || s.status === "failing" || s.status === "unknown"));
  if (!valid || !m) {
    return (
      <Panel title="Alerts and AI budget">
        <p className="text-sm" role="status">Monitoring state is unavailable. This is not a healthy state.</p>
      </Panel>
    );
  }
  const b = m.budget;
  return (
    <Panel title="Alerts and AI budget">
      <KeyValue
        rows={[
          ["Active operational alerts", String(m.alerts.active)],
          ["AI budget state", b ? b.state.replace(/_/g, " ") : "Unavailable"],
          ["AI budget enforcement", b ? b.enforcement.replace(/_/g, " ") : "Unavailable"],
          ["Budget class", b?.budget_class ?? "Not set"],
          ["Remaining to stop threshold (USD, estimate)", b?.remaining_to_stop_usd ?? "Not available"],
          ["Remaining requests", b?.remaining_requests != null ? String(b.remaining_requests) : "Not available"],
        ]}
      />
      <ScrollRegion label="Health signals (scrollable table)">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Derived health signals</caption>
          <thead>
            <tr className="text-xs text-muted">
              <th scope="col" className="py-1 pr-4 font-medium">Signal</th>
              <th scope="col" className="py-1 pr-4 font-medium">State</th>
            </tr>
          </thead>
          <tbody>
            {m.signals.map((s) => (
              <tr key={s.code} className="border-t border-default">
                <th scope="row" className="py-1 pr-4 text-left font-medium">{SIGNAL_LABELS[s.code] ?? s.code.replace(/_/g, " ")}</th>
                <td className="py-1 pr-4"><StatusLabel tone={SIGNAL_TONE[s.status]}>{SIGNAL_TEXT[s.status]}</StatusLabel></td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
      <p className="text-xs text-muted">{typeof m.note === "string" ? m.note : ""}</p>
      <p className="text-xs text-muted">Alerts are in-app only. Open them on <Link href="/admin/security" className="underline underline-offset-2">Security</Link>.</p>
    </Panel>
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
          <MonitoringPanel monitoring={loaded.data.monitoring} />
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
