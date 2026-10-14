"use client";

import { api } from "@/lib/api/client";
import type { BillingProviderReadiness } from "@/lib/admin/types";
import { KeyValue, Panel, ResourceState, StatusLabel, useAdminResource } from "./ui";

// W12.4D-B: readiness of the owner-selected billing provider. A foundation only: nothing here contacts Stripe, and none of these states means that
// payments work. "Configured" never means "healthy", and Managed Payments eligibility and sandbox access are shown as not confirmed.

const STATUS: Record<BillingProviderReadiness["status"], { label: string; tone: "ok" | "warn" | "neutral" }> = {
  not_configured: { label: "NOT CONFIGURED", tone: "neutral" },
  configured_not_tested: { label: "CONFIGURED, NOT TESTED", tone: "neutral" },
  sandbox_access_unverified: { label: "SANDBOX ACCESS UNVERIFIED", tone: "neutral" },
  configuration_error: { label: "CONFIGURATION ERROR", tone: "warn" },
  provider_unavailable: { label: "PROVIDER UNAVAILABLE", tone: "warn" },
  eligibility_not_confirmed: { label: "ELIGIBILITY NOT CONFIRMED", tone: "neutral" },
  live_disabled: { label: "LIVE BILLING DISABLED", tone: "neutral" },
};
const PROBLEM: Record<string, string> = {
  credential_environment_mismatch: "A credential that belongs to the other environment is stored in a sandbox slot. It is refused and never used.",
  credential_format: "A stored credential does not have the expected format for this environment.",
  invalid_environment: "STRIPE_ENVIRONMENT is not sandbox or live.",
};
const label = (s: string | null) => (s ? s.replace(/_/g, " ") : "none");
const slot = (s: { configured: boolean; source_kind: string }) => (s.configured ? `Configured (${label(s.source_kind)})` : "Not configured");

export function BillingProviderReadinessPanel() {
  const loaded = useAdminResource(() => api.admin.billingReadiness("stripe_managed_payments"), []);
  return (
    <Panel title="Billing provider readiness">
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? <Body d={loaded.data} /> : null}
      </ResourceState>
    </Panel>
  );
}

function Body({ d }: { d: BillingProviderReadiness }) {
  const s = STATUS[d.status];
  return (
    <div className="grid gap-3">
      <p className="flex flex-wrap items-center gap-3 text-sm font-medium" data-testid="billing-readiness-headline">
        <StatusLabel tone={s.tone}>{s.label}</StatusLabel>
      </p>
      {d.configuration_problem ? <p role="alert" className="text-sm" data-testid="billing-readiness-problem">{PROBLEM[d.configuration_problem] ?? "The configuration is not valid."}</p> : null}
      <KeyValue rows={[
        ["Provider selected", label(d.provider_selected)],
        ["Environment", d.environment ? label(d.environment) : "invalid"],
        ["Sandbox API access", slot(d.sandbox.api)],
        ["Sandbox webhook signing", slot(d.sandbox.webhook)],
        ["Live credentials stored", d.live_slots_populated ? "Yes (inert: live billing is disabled)" : "No"],
        ["Managed Payments seller eligibility", "Not confirmed"],
        ["Merchant of record", "Not confirmed"],
        ["Sandbox access", "Unverified"],
        ["Live billing", "Disabled"],
        ["Checkout", "Not implemented"],
        ["Refunds", "Not implemented"],
        ["Webhooks", "Not implemented"],
        ["Last successful check", d.last_successful_check ?? "never"],
        ["Last failure", label(d.last_failure_category)],
        ["API version pinned", d.api_version],
      ]} />
      <p className="text-xs text-muted">
        This is the technical foundation only. Nothing contacts Stripe, no payment can be taken, and Managed Payments availability for this seller (account, product
        classification and sandbox access) has not been verified. Sandbox and live credentials are separate and never interchangeable.
      </p>
    </div>
  );
}
