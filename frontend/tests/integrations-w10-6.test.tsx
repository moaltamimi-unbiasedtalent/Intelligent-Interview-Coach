import { readFileSync, readdirSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.6 Admin integrations UI. No secret value ever reaches the browser; async content awaited with findBy*.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/integrations" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const list = vi.fn();
const one = vi.fn();
const test = vi.fn();
const replace = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { integrations: (...a: unknown[]) => list(...a), integration: (...a: unknown[]) => one(...a),
    testIntegration: (...a: unknown[]) => test(...a), replaceCredential: (...a: unknown[]) => replace(...a) } },
}));

import { IntegrationDetailView } from "@/components/admin/IntegrationDetailView";
import { IntegrationsView } from "@/components/admin/IntegrationsView";

const ROW = (over: Record<string, unknown> = {}) => ({
  code: "openrouter", name: "OpenRouter (language models)", category: "ai_model", category_label: "AI / model", adapter: "OpenRouter chat API",
  description: "Chat model provider.", classification: "runtime_active", configuration_status: "configured",
  slots: [{ slot: "api_key", label: "API key", external_name: "OPENROUTER_API_KEY", configured: true, source: "environment", writable: false }],
  settings: [], runtime: { enabled: true, managed: "environment", toggle_supported: false, note: "Runtime state is owned by the deployment environment." },
  store: { name: "environment", writable: false },
  health: { status: "not_tested", last_tested_at: null, category: null, latency_ms: null },
  test: { supported: true, note: "Calls one key-information endpoint." }, validation_note: "Healthy only after a successful manual test.", ...over });
const GOOGLE = ROW({ code: "google_oidc", name: "Google sign-in (OIDC)", category: "authentication", category_label: "Authentication",
  classification: "code_present_not_validated", test: { supported: false, note: "No manual probe." },
  validation_note: "Backend support present; end-to-end sign-in is not validated." });
const ADZUNA = ROW({ code: "adzuna", name: "Adzuna (job market data)", classification: "supported_unconfigured", configuration_status: "unconfigured",
  slots: [{ slot: "app_key", label: "Application key", external_name: "ADZUNA_APP_KEY", configured: false, source: "none", writable: false }],
  test: { supported: false, note: "No manual probe." } });
const DETAIL = (over: Record<string, unknown> = {}) => ({ ...ROW(over), audit: [{ event_type: "admin.integration_test_run", result: "success", actor_user_id: 1, request_id: "req-1", created_at: null, context: { category: "ok" } }] });

beforeEach(() => {
  mockPerms = ["platform.integrations.read", "platform.integrations.manage"];
  list.mockResolvedValue({ items: [ROW(), GOOGLE, ADZUNA] });
  one.mockResolvedValue(DETAIL());
  test.mockResolvedValue({ integration: "openrouter", outcome: "success", category: "ok", latency_ms: 12 });
  replace.mockResolvedValue({ integration: "openrouter", slot: "api_key", configured: true });
});
afterEach(() => vi.clearAllMocks());

describe("Integrations inventory", () => {
  it("lists integrations with separate support, credential and health states - configured is never shown as healthy", async () => {
    render(<IntegrationsView />);
    const row = (await screen.findByRole("link", { name: "OpenRouter (language models)" })).closest("tr") as HTMLElement;
    expect(within(row).getByText("In use")).toBeInTheDocument();
    expect(within(row).getByText("Configured")).toBeInTheDocument();
    expect(within(row).getByText("Not tested")).toBeInTheDocument();
    expect(within(row).queryByText(/succeeded/)).not.toBeInTheDocument();
    const google = screen.getByRole("link", { name: "Google sign-in (OIDC)" }).closest("tr") as HTMLElement;
    expect(within(google).getByText("Code present, not validated")).toBeInTheDocument();
    const adzuna = screen.getByRole("link", { name: "Adzuna (job market data)" }).closest("tr") as HTMLElement;
    expect(within(adzuna).getByText("Supported, not configured")).toBeInTheDocument();
    expect(within(adzuna).getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText(/supported is not connected, configured is not healthy/)).toBeInTheDocument();
  });

  it("shows a healthy label only when the server reports a successful manual test, and an unhealthy one on failure", async () => {
    list.mockResolvedValue({ items: [ROW({ health: { status: "healthy", last_tested_at: "2026-10-03T10:00:00", category: "ok", latency_ms: 9 } }),
      ROW({ code: "malware_scanner", name: "ClamAV", health: { status: "unhealthy", last_tested_at: "2026-10-03T10:00:00", category: "unavailable", latency_ms: null } })] });
    render(<IntegrationsView />);
    expect(await screen.findByText("Last test succeeded")).toBeInTheDocument();
    expect(screen.getByText("Last test failed")).toBeInTheDocument();
  });

  it("without integrations.read nothing is fetched", async () => {
    mockPerms = ["platform.users.read"];
    render(<IntegrationsView />);
    expect(await screen.findByText(/does not include access/)).toBeInTheDocument();
    expect(list).not.toHaveBeenCalled();
  });
});

describe("Integration detail", () => {
  it("states environment credentials are managed outside Ask4Mo: no value, no rotate, no replace, no reveal", async () => {
    render(<IntegrationDetailView code="openrouter" />);
    const slots = await screen.findByRole("list", { name: "Credential slots" });
    expect(within(slots).getByText("Configured")).toBeInTheDocument();
    expect(within(slots).getByText(/Managed outside Ask4Mo \(set OPENROUTER_API_KEY in the deployment environment\)/)).toBeInTheDocument();
    for (const name of [/Replace/, /Set credential/, /Rotate/, /Delete/, /Reveal/, /Show/, /View/]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
    expect(document.querySelector('input[type="password"]')).toBeNull();
    expect(screen.getByText(/never displays a credential, part of one, or a masked form of one/)).toBeInTheDocument();
    expect(screen.getByText(/Configured only means a value exists, not that it is valid/)).toBeInTheDocument();
  });

  it("runs ONE manual test on request only, shows the safe outcome and refetches (no automatic probing on load)", async () => {
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await screen.findByRole("heading", { name: "Connection test" });
    expect(test).not.toHaveBeenCalled();
    expect(screen.getByText(/nothing is checked automatically/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(test).toHaveBeenCalledTimes(1));
    expect(test).toHaveBeenCalledWith("openrouter");
    expect(await screen.findByText("Connection test succeeded.")).toBeInTheDocument();
    test.mockResolvedValue({ integration: "openrouter", outcome: "failure", category: "unauthorized", latency_ms: 4 });
    await user.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText("Connection test failed (unauthorized).")).toBeInTheDocument();
  });

  it("an unsupported integration offers no test and says so; a read-only role has no test button", async () => {
    one.mockResolvedValue(DETAIL({ code: "google_oidc", test: { supported: false, note: "No manual probe." } }));
    const { unmount } = render(<IntegrationDetailView code="google_oidc" />);
    expect(await screen.findByText("A manual test is not available for this integration.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Test connection" })).not.toBeInTheDocument();
    unmount();
    one.mockResolvedValue(DETAIL());
    mockPerms = ["platform.integrations.read"];
    render(<IntegrationDetailView code="openrouter" />);
    await screen.findByRole("heading", { name: "Connection test" });
    expect(screen.queryByRole("button", { name: "Test connection" })).not.toBeInTheDocument();
  });

  it("a failed test shows a safe message and is not retried", async () => {
    const user = userEvent.setup();
    test.mockRejectedValue(new Error("A manual connection test is not available for this integration."));
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Test connection" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/not available/);
    expect(test).toHaveBeenCalledTimes(1);
  });

  it("shows recent management events with ids only, and no runtime toggle", async () => {
    render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByText("admin.integration_test_run")).toBeInTheDocument();
    expect(screen.getByText("req-1")).toBeInTheDocument();
    expect(screen.getByText("Deployment environment (read-only)")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(document.querySelector('input[type="url"], input[name*="url" i], input[name*="endpoint" i]')).toBeNull();
  });
});

describe("write-only credential form (only for a writable store and secret.rotate)", () => {
  const WRITABLE = (configured = false) => DETAIL({ store: { name: "in_memory_test", writable: true },
    slots: [{ slot: "api_key", label: "API key", external_name: "OPENROUTER_API_KEY", configured, source: configured ? "in_memory_test" : "none", writable: true }] });

  it("clears the input immediately, sends the value once, never shows it back and warns the old value is unviewable", async () => {
    mockPerms = ["platform.integrations.read", "platform.integrations.secret.rotate"];
    one.mockResolvedValue(WRITABLE(true));
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Replace credential" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/previous value cannot be viewed from Ask4Mo/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    const input = within(dialog).getByLabelText("New credential") as HTMLInputElement;
    expect(input.type).toBe("password");
    await user.type(input, "super-secret-credential-123");
    await user.click(within(dialog).getByRole("button", { name: "Save credential" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("openrouter", "api_key", "super-secret-credential-123"));
    expect(input.value).toBe("");                                   // cleared immediately, not repopulated
    expect(await screen.findByText(/cannot be viewed from Ask4Mo/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("super-secret-credential-123");
  });

  it("a rejected write keeps the dialog open with a safe error, clears the input and does not retry", async () => {
    mockPerms = ["platform.integrations.read", "platform.integrations.secret.rotate"];
    one.mockResolvedValue(WRITABLE());
    replace.mockRejectedValue(new Error("The credential could not be saved."));
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Set credential" }));
    const dialog = screen.getByRole("alertdialog");
    const input = within(dialog).getByLabelText("New credential") as HTMLInputElement;
    await user.type(input, "another-credential-value-9");
    await user.click(within(dialog).getByRole("button", { name: "Save credential" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/could not be saved/);
    expect(input.value).toBe("");
    expect(replace).toHaveBeenCalledTimes(1);
    expect(document.body.textContent).not.toContain("another-credential-value-9");
  });

  it("without secret.rotate, or with a read-only store, there is no credential action", async () => {
    one.mockResolvedValue(WRITABLE(true));
    const { unmount } = render(<IntegrationDetailView code="openrouter" />);
    await screen.findByRole("heading", { name: "Credentials" });
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
    unmount();
    mockPerms = ["platform.integrations.read", "platform.integrations.secret.rotate"];
    one.mockResolvedValue(DETAIL());
    render(<IntegrationDetailView code="openrouter" />);
    await screen.findByRole("heading", { name: "Credentials" });
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
  });
});

describe("no secret handling in client code and no role-name authorisation", () => {
  it("integration components never store a credential in state or browser storage and do not compare role names", () => {
    for (const f of readdirSync("components/admin").filter((n) => /Integration/.test(n))) {
      const src = readFileSync(`components/admin/${f}`, "utf8");
      expect(src, f).not.toMatch(/localStorage|sessionStorage|platform_role\s*===|===\s*"platform_admin"/);
      expect(src, f).not.toContain('from "next/link"');
      expect(src, f).not.toMatch(/useState<string>\(""\)\s*;?\s*\/\/\s*credential/i);
    }
    const detail = readFileSync("components/admin/IntegrationDetailView.tsx", "utf8");
    expect(detail).toContain("valueRef");                           // uncontrolled input: the value is not React state
    expect(detail).not.toMatch(/useState[^;]*(credential|secret|password)/i);
  });
});
