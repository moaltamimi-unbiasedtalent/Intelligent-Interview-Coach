import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// W12.4D-B billing provider readiness UI: fixed states only, never healthy / approved, nothing secret.
let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/integrations" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
const readiness = vi.fn();
const integration = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { admin: { integration: (...a: unknown[]) => integration(...a), billingReadiness: (...a: unknown[]) => readiness(...a),
    testIntegration: vi.fn(), replaceCredential: vi.fn(), removeCredential: vi.fn(), stepUp: vi.fn(), emailDelivery: vi.fn(), sendTestEmail: vi.fn() } } };
});

import { BillingProviderReadinessPanel } from "@/components/admin/BillingProviderReadinessPanel";
import { IntegrationDetailView } from "@/components/admin/IntegrationDetailView";

const R = (over: Record<string, unknown> = {}) => ({
  status: "sandbox_access_unverified", provider_selected: "stripe_managed_payments", environment: "sandbox", checks: [], configuration_problem: null,
  sandbox: { api: { configured: true, source_kind: "managed" }, webhook: { configured: true, source_kind: "environment" } }, live_slots_populated: false,
  eligibility: "not_confirmed", merchant_of_record: "not_confirmed", sandbox_access: "unverified", live_billing: "disabled", checkout: "not_implemented",
  refunds: "not_implemented", webhooks: "not_implemented", last_successful_check: null, last_failure_category: null, api_version: "2026-09-30.endive",
  managed_payments_required: true, ...over });
beforeEach(() => { mockPerms = ["platform.integrations.read"]; readiness.mockResolvedValue(R()); });
afterEach(() => vi.clearAllMocks());

describe("billing provider readiness panel", () => {
  it.each([
    ["not_configured", /NOT CONFIGURED/], ["sandbox_access_unverified", /SANDBOX ACCESS UNVERIFIED/], ["configuration_error", /CONFIGURATION ERROR/],
    ["live_disabled", /LIVE BILLING DISABLED/], ["provider_unavailable", /PROVIDER UNAVAILABLE/], ["eligibility_not_confirmed", /ELIGIBILITY NOT CONFIRMED/],
  ])("%s is its own state, and eligibility, merchant of record and sandbox access always read as not confirmed", async (status, re) => {
    readiness.mockResolvedValue(R({ status }));
    render(<BillingProviderReadinessPanel />);
    expect(await screen.findByTestId("billing-readiness-headline")).toHaveTextContent(re);
    expect(screen.getByText("Managed Payments seller eligibility").nextSibling).toHaveTextContent("Not confirmed");
    expect(screen.getByText("Merchant of record").nextSibling).toHaveTextContent("Not confirmed");
    expect(screen.getByText("Live billing").nextSibling).toHaveTextContent("Disabled");
    expect(screen.getByText("Checkout").nextSibling).toHaveTextContent("Not implemented");
    expect(screen.queryByText(/healthy|approved|payments are enabled|ready to take/i)).not.toBeInTheDocument();
  });

  it("explains an environment mismatch without revealing any value", async () => {
    readiness.mockResolvedValue(R({ status: "configuration_error", configuration_problem: "credential_environment_mismatch" }));
    render(<BillingProviderReadinessPanel />);
    expect(await screen.findByTestId("billing-readiness-problem")).toHaveTextContent(/other environment is stored in a sandbox slot/);
    expect(document.body.innerHTML).not.toMatch(/sk_(test|live)_|whsec_/);
  });

  it("states live credentials are inert and nothing here contacts Stripe", async () => {
    readiness.mockResolvedValue(R({ live_slots_populated: true }));
    render(<BillingProviderReadinessPanel />);
    expect(await screen.findByText(/Yes \(inert: live billing is disabled\)/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing contacts Stripe, no payment can be taken/)).toBeInTheDocument();
  });

  it("is shown on the Stripe integration detail only, with no test-connection control", async () => {
    mockPerms = ["platform.integrations.read", "platform.integrations.manage"];
    const slot = (s: string, n: string, req = true) => ({ slot: s, label: s, external_name: n, configured: false, source: "none", writable: false, source_kind: "none", managed: false,
      managed_readable: null, revision: null, last_rotated_at: null, environment_fallback: false, required: req, min_length: 16, max_length: 4096, applies: "restart" });
    const detail = { code: "stripe_managed_payments", name: "Stripe Managed Payments (billing provider)", category: "payments", category_label: "Payments / billing", adapter: "Stripe",
      description: "Foundation.", classification: "code_present_not_validated", configuration_status: "unconfigured",
      slots: [slot("sandbox_api_key", "STRIPE_SANDBOX_SECRET_KEY"), slot("live_api_key", "STRIPE_LIVE_SECRET_KEY", false)], settings: [],
      runtime: { enabled: false, managed: "environment", toggle_supported: false, note: "n" }, store: { name: "environment", writable: false, state: "read_only", reason: null },
      health: { status: "not_tested", last_tested_at: null, category: null, latency_ms: null }, test: { supported: false, note: "No connection test exists in this wave." },
      validation_note: "FOUNDATION ONLY", audit: [] };
    integration.mockResolvedValue(detail);
    const { unmount } = render(<IntegrationDetailView code="stripe_managed_payments" />);
    expect(await screen.findByTestId("billing-readiness-headline")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Test connection" })).not.toBeInTheDocument();
    expect(screen.getByText("A manual test is not available for this integration.")).toBeInTheDocument();
    unmount();
    integration.mockResolvedValue({ ...detail, code: "adzuna" });
    render(<IntegrationDetailView code="adzuna" />);
    await screen.findByRole("heading", { name: "Credentials" });
    expect(screen.queryByTestId("billing-readiness-headline")).not.toBeInTheDocument();
  });
});
