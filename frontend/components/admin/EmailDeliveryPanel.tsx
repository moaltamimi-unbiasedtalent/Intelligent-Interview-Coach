"use client";

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { EmailDeliveryStatus, EmailTestResult } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, ResourceState, StatusLabel, Table, apiMessage, btn, useAdminResource } from "./ui";

// W12.4C: transactional email readiness and bounded delivery diagnostics. Provider accepted is NOT delivered, and no delivery event is
// collected, so "delivery confirmed" is never shown. No recipient, token, link or message content exists in this data.

const HEADLINE: Record<EmailDeliveryStatus["status"], { label: string; tone: "ok" | "warn" | "neutral" }> = {
  not_configured: { label: "NOT CONFIGURED", tone: "neutral" },
  configured_not_tested: { label: "CONFIGURED, NOT TESTED", tone: "neutral" },
  last_test_passed: { label: "CONNECTION TEST PASSED", tone: "ok" },
  provider_accepted: { label: "PROVIDER ACCEPTED A SUBMISSION (not a delivery confirmation)", tone: "ok" },
  delivery_failed: { label: "SUBMISSION FAILED", tone: "warn" },
  delivery_unknown: { label: "OUTCOME UNKNOWN", tone: "warn" },
};
const SENDER: Record<EmailDeliveryStatus["sender_verification"], string> = {
  unknown: "Unknown (run the connection test)",
  verified_by_last_test: "Verified at the last connection test",
  not_verified_by_last_test: "Not verified at the last connection test",
};
const ATTEMPT: Record<string, string> = {
  provider_accepted: "Accepted by the provider", failed: "Not accepted", not_configured: "Not configured", delivery_unknown: "Outcome unknown", captured: "Captured (development adapter)",
};
const label = (s: string | null) => (s ? s.replace(/_/g, " ") : "none");

export function EmailDeliveryPanel({ canTest, onChanged }: { canTest: boolean; onChanged?: () => void }) {
  const loaded = useAdminResource(() => api.admin.emailDelivery("email_brevo"), []);
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState<EmailTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setError(null);
    try {
      setResult(await api.admin.sendTestEmail("email_brevo"));
      loaded.reload();
      onChanged?.();
    } catch (e) {
      setError(apiMessage(e));
    }
  };

  return (
    <Panel title="Email delivery">
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? <Body d={loaded.data} /> : null}
      </ResourceState>
      {canTest ? (
        <div className="grid gap-2">
          <div><button type="button" className={btn} onClick={() => { setResult(null); setConfirm(true); }}>Send test email to my address</button></div>
          {result ? (
            <p role="status" className="rounded border border-border px-3 py-2 text-sm" data-testid="test-email-result">{result.note}</p>
          ) : null}
          {error ? <p role="alert" className="text-sm">{error}</p> : null}
        </div>
      ) : null}
      <ActionDialog open={confirm} title="Send one real test email?" confirmLabel="Send test email" askReason={false} onClose={() => setConfirm(false)} onConfirm={send}>
        <p>
          This sends ONE message through the live email provider to <strong>your own account address only</strong>. It is a fixed test message with no link
          and no token. It is audited and limited to a few per hour. A successful submission is not proof of delivery: check your inbox.
        </p>
      </ActionDialog>
    </Panel>
  );
}

function Body({ d }: { d: EmailDeliveryStatus }) {
  const h = HEADLINE[d.status];
  const x = d.diagnostics;
  return (
    <div className="grid gap-3">
      <p className="flex flex-wrap items-center gap-3 text-sm font-medium" data-testid="email-headline">
        <StatusLabel tone={h.tone}>{h.label}</StatusLabel>
      </p>
      {d.restart_required ? (
        <p role="status" className="rounded border border-border px-3 py-2 text-sm" data-testid="restart-required">
          Credential saved, provider client restart required, connection not yet revalidated. {d.restart_reason}
        </p>
      ) : null}
      <KeyValue rows={[
        ["Provider selected", d.provider_selected],
        ["Adapter in this process", label(d.adapter_in_process)],
        ["Provider account", d.provider_account.configured ? `Configured (${label(d.provider_account.source_kind)})` : "Not configured"],
        ["Sender address", d.sender_configured ? "Configured" : "Not configured"],
        ["Sender verification", SENDER[d.sender_verification]],
        ["Connection test", `${label(d.last_test.state)}${d.last_test.category ? ` (${label(d.last_test.category)})` : ""}`],
        ["Link origin", d.link_origin.configured ? (d.link_origin.https ? "Configured, https" : "Configured, NOT https") : "Not configured"],
        ["Verification email pipeline", label(d.identity_pipeline.verification)],
        ["Recovery email pipeline", label(d.identity_pipeline.recovery)],
        ["Delivery confirmation", "Not collected (no delivery events)"],
        ["Live delivery", "Unverified"],
      ]} />
      <KeyValue rows={[
        ["Accepted in the last 24 hours", String(x.last_24h.provider_accepted)],
        ["Not accepted in the last 24 hours", String(x.last_24h.failed)],
        ["Outcome unknown in the last 24 hours", String(x.last_24h.delivery_unknown)],
        ["Last accepted", x.last_accepted?.at ?? "never"],
        ["Last failure", x.last_failure ? `${x.last_failure.at} (${label(x.last_failure.failure_category)})` : "none"],
      ]} />
      <Table caption="Recent email submissions" rows={x.recent.filter((a): a is NonNullable<typeof a> => a !== null)
        .map((a) => ({ at: a.at, type: label(a.message_type), result: ATTEMPT[a.status] ?? a.status, reason: label(a.failure_category) }))}
        cols={["at", "type", "result", "reason"]} />
      <p className="text-xs text-muted">
        {d.note} Records hold no recipient, token, link or message content and are kept for {x.retention_days} days.
      </p>
    </div>
  );
}
