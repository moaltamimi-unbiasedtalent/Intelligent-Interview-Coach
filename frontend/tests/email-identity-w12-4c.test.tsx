import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// W12.4C email and identity UI. Link states are driven by stable server error codes (never English matching) and every identity message
// shown here is localised from the interface catalogue. No token, link, recipient or message content is ever rendered in Admin.

let mockPerms: string[] = [];
let tokenParam = "tok_abc";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  usePathname: () => "/admin/integrations",
  useSearchParams: () => new URLSearchParams(tokenParam ? `token=${tokenParam}` : ""),
}));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
  useAuth: () => ({ account: { user_id: 1, email: "me@example.test", email_verified: false, platform_role: "user", auth_method: "session", display_name: null, providers: ["password"] },
    status: "authenticated", signOut: async () => {} }),
}));

const verify = vi.fn();
const reset = vi.fn();
const forgot = vi.fn();
const register = vi.fn();
const resend = vi.fn();
const delivery = vi.fn();
const sendTest = vi.fn();
const integration = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: {
      auth: { verifyEmail: (...a: unknown[]) => verify(...a), resetPassword: (...a: unknown[]) => reset(...a), forgotPassword: (...a: unknown[]) => forgot(...a),
        register: (...a: unknown[]) => register(...a), resendVerification: (...a: unknown[]) => resend(...a) },
      admin: { integration: (...a: unknown[]) => integration(...a), emailDelivery: (...a: unknown[]) => delivery(...a), sendTestEmail: (...a: unknown[]) => sendTest(...a),
        testIntegration: vi.fn(), replaceCredential: vi.fn(), removeCredential: vi.fn(), stepUp: vi.fn() },
    },
  };
});

import { ApiError } from "@/lib/api/errors";
import { VerifyEmailPanel } from "@/components/auth/VerifyEmailPanel";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { EmailDeliveryPanel } from "@/components/admin/EmailDeliveryPanel";
import { IntegrationDetailView } from "@/components/admin/IntegrationDetailView";

const coded = (code: string, status = 400, kind: "validation" | "rateLimited" | "unavailable" = "validation") =>
  new ApiError({ kind, status, code, message: "server english text" });

beforeEach(() => { tokenParam = "tok_abc"; mockPerms = []; });
afterEach(() => vi.clearAllMocks());

describe("verification link states", () => {
  it("verifies once and shows success", async () => {
    verify.mockResolvedValue({ message: "Your email is verified." });
    render(<VerifyEmailPanel />);
    expect(await screen.findByText("Your email is verified.")).toBeInTheDocument();
    expect(verify).toHaveBeenCalledTimes(1);
    expect(document.body.textContent).not.toContain("tok_abc");
  });
  it.each([
    ["token_expired", /has expired/], ["token_used", /already used/], ["token_invalid", /invalid or has expired/],
  ])("%s shows its own localised message, never the server text", async (code, re) => {
    verify.mockRejectedValue(coded(code));
    render(<VerifyEmailPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent(re);
    expect(document.body.textContent).not.toContain("server english text");
  });
});

describe("password recovery states", () => {
  it("request: the neutral localised outcome is shown whatever the server answered", async () => {
    forgot.mockResolvedValue({ message: "server text that must not be needed" });
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);
    await user.type(screen.getByLabelText(/email/i), "someone@example.test");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));
    expect(await screen.findByText(/If an account exists for that email/)).toBeInTheDocument();
  });
  it.each([
    ["token_expired", /expired/], ["token_used", /already used/], ["token_invalid", /missing or invalid/],
  ])("reset with %s", async (code, re) => {
    reset.mockRejectedValue(coded(code));
    const user = userEvent.setup();
    render(<ResetPasswordForm />);
    await user.type(screen.getByLabelText(/new password/i), "a-long-enough-pass");
    await user.click(screen.getByRole("button", { name: /update password/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(re);
    expect(reset).toHaveBeenCalledWith("tok_abc", "a-long-enough-pass");
  });
  it("registration sends the interface language and shows the localised uniform outcome", async () => {
    register.mockResolvedValue({ message: "x" });
    const user = userEvent.setup();
    render(<RegisterForm />);
    await user.type(screen.getByLabelText(/^email/i), "new@example.test");
    await user.type(screen.getByLabelText(/^password/i), "a-long-enough-pass");
    await user.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(register).toHaveBeenCalledWith(expect.objectContaining({ email: "new@example.test", locale: "en" })));
    expect(await screen.findByText(/we've sent a verification link/)).toBeInTheDocument();
  });
});

const DELIVERY = (over: Record<string, unknown> = {}) => ({
  status: "configured_not_tested", provider_selected: "brevo", adapter_in_process: "brevo", provider_account: { configured: true, source_kind: "managed" },
  sender_configured: true, sender_verification: "unknown", restart_required: false, restart_reason: null,
  last_test: { state: "not_tested", last_tested_at: null, category: null }, delivery_confirmation: "not_collected", live_delivery: "unverified",
  link_origin: { configured: true, https: true }, identity_pipeline: { verification: "ready", recovery: "ready" },
  diagnostics: { retention_days: 30, last_attempt: null, last_accepted: null, last_failure: null, last_identity_attempt: null,
    last_24h: { provider_accepted: 0, failed: 0, delivery_unknown: 0, captured: 0 }, recent: [] },
  last_failure_category: null, note: "Provider accepted does not mean delivered.", ...over });

describe("Admin email delivery panel", () => {
  it.each([
    ["not_configured", /NOT CONFIGURED/], ["configured_not_tested", /CONFIGURED, NOT TESTED/], ["last_test_passed", /CONNECTION TEST PASSED/],
    ["provider_accepted", /PROVIDER ACCEPTED A SUBMISSION \(not a delivery confirmation\)/], ["delivery_failed", /SUBMISSION FAILED/], ["delivery_unknown", /OUTCOME UNKNOWN/],
  ])("%s is its own state and delivery is never confirmed", async (status, re) => {
    delivery.mockResolvedValue(DELIVERY({ status }));
    render(<EmailDeliveryPanel canTest={false} />);
    expect(await screen.findByTestId("email-headline")).toHaveTextContent(re);
    expect(screen.getByText("Not collected (no delivery events)")).toBeInTheDocument();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.queryByText(/^(Delivered|Delivery confirmed|Confirmed delivery)$/i)).not.toBeInTheDocument();   // no green delivered state exists
  });

  it("explains a restart-required rotation instead of claiming it is active", async () => {
    delivery.mockResolvedValue(DELIVERY({ restart_required: true, restart_reason: "The running client uses an earlier credential; restart the API and the worker." }));
    render(<EmailDeliveryPanel canTest={false} />);
    expect(await screen.findByTestId("restart-required")).toHaveTextContent(/restart required.*not yet revalidated/s);
  });

  it("shows bounded diagnostics only: categories and times, no recipient, token or link", async () => {
    delivery.mockResolvedValue(DELIVERY({ status: "delivery_failed", last_failure_category: "provider_auth_failed",
      diagnostics: { retention_days: 30, last_attempt: null, last_accepted: null, last_failure: { at: "2026-10-14T10:00:00", message_type: "password_reset", status: "failed", failure_category: "provider_auth_failed" },
        last_identity_attempt: null, last_24h: { provider_accepted: 3, failed: 1, delivery_unknown: 0, captured: 0 },
        recent: [{ at: "2026-10-14T10:00:00", message_type: "password_reset", status: "failed", failure_category: "provider_auth_failed" }] } }));
    render(<EmailDeliveryPanel canTest={false} />);
    await screen.findByTestId("email-headline");
    expect(screen.getAllByText(/provider auth failed/).length).toBeGreaterThan(0);
    expect(screen.getByText("Not accepted")).toBeInTheDocument();
    expect(document.body.innerHTML).not.toMatch(/token=|@example|https?:\/\//);
  });

  it("the test-email action is hidden without manage permission", async () => {
    delivery.mockResolvedValue(DELIVERY());
    render(<EmailDeliveryPanel canTest={false} />);
    await screen.findByTestId("email-headline");
    expect(screen.queryByRole("button", { name: /send test email/i })).not.toBeInTheDocument();
  });

  it("the test email names its external side effect, needs confirmation, sends once and never calls it delivery", async () => {
    delivery.mockResolvedValue(DELIVERY());
    sendTest.mockResolvedValue({ status: "provider_accepted", failure_category: null, adapter: "brevo", note: "Submitted to the provider. That is not a delivery confirmation: check your inbox." });
    const user = userEvent.setup();
    render(<EmailDeliveryPanel canTest />);
    await user.click(await screen.findByRole("button", { name: "Send test email to my address" }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent(/ONE message through the live email provider/);
    expect(dialog).toHaveTextContent(/your own account address only/);
    expect(sendTest).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Send test email" }));
    await waitFor(() => expect(sendTest).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId("test-email-result")).toHaveTextContent(/not a delivery confirmation/);
  });
});

describe("Brevo integration detail", () => {
  const DETAIL = {
    code: "email_brevo", name: "Brevo (transactional email)", category: "communications", category_label: "Email / communications", adapter: "Brevo email API",
    description: "Sends account emails.", classification: "configured_inactive", configuration_status: "configured",
    slots: [{ slot: "api_key", label: "API key", external_name: "BREVO_API_KEY", configured: true, source: "managed", writable: true, source_kind: "managed", managed: true,
      managed_readable: true, revision: 1, last_rotated_at: "2026-10-14T09:00:00", environment_fallback: false, required: true, min_length: 8, max_length: 4096, applies: "restart" }],
    settings: [], runtime: { enabled: false, managed: "environment", toggle_supported: false, note: "n" },
    store: { name: "managed_with_environment_fallback", writable: true, state: "writable", reason: null },
    health: { status: "not_tested", last_tested_at: null, category: null, latency_ms: null }, test: { supported: true, note: "Sends no email." },
    validation_note: "Live delivery UNVERIFIED.", audit: [] };
  beforeEach(() => { integration.mockResolvedValue(DETAIL); delivery.mockResolvedValue(DELIVERY()); });

  it("operations_admin (manage, no secret.rotate) sees diagnostics and the test action but no credential control", async () => {
    mockPerms = ["platform.integrations.read", "platform.integrations.manage"];
    render(<IntegrationDetailView code="email_brevo" />);
    expect(await screen.findByTestId("email-headline")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send test email to my address" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test connection" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });
  it("read-only inspection has neither the test action nor the credential controls", async () => {
    mockPerms = ["platform.integrations.read"];
    render(<IntegrationDetailView code="email_brevo" />);
    await screen.findByTestId("email-headline");
    expect(screen.queryByRole("button", { name: /send test email/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
  });
  it("other integrations do not render the email panel", async () => {
    mockPerms = ["platform.integrations.read"];
    integration.mockResolvedValue({ ...DETAIL, code: "adzuna", name: "Adzuna" });
    render(<IntegrationDetailView code="adzuna" />);
    await screen.findByRole("heading", { name: "Credentials" });
    expect(screen.queryByTestId("email-headline")).not.toBeInTheDocument();
    expect(delivery).not.toHaveBeenCalled();
  });
});
