import { readFileSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// W12.4B secure provider and secret administration UI. The sentinel exists only in this test source; the UI never receives or renders a stored value.

const SENTINEL = "DO_NOT_LEAK_W12_04B_SECRET_SENTINEL";
let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/integrations" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const one = vi.fn();
const replace = vi.fn();
const remove = vi.fn();
const stepUp = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { integration: (...a: unknown[]) => one(...a), testIntegration: vi.fn(), integrations: vi.fn(),
    replaceCredential: (...a: unknown[]) => replace(...a), removeCredential: (...a: unknown[]) => remove(...a), stepUp: (...a: unknown[]) => stepUp(...a) } },
}));

import { IntegrationDetailView } from "@/components/admin/IntegrationDetailView";
import { ApiError } from "@/lib/api/errors";

const SLOT = (o: Record<string, unknown> = {}) => ({ slot: "api_key", label: "API key", external_name: "OPENROUTER_API_KEY", configured: false, source: "none",
  writable: true, source_kind: "none", managed: false, managed_readable: null, revision: null, last_rotated_at: null, environment_fallback: false,
  required: true, min_length: 8, max_length: 4096, applies: "restart", ...o });
const DETAIL = (slot: Record<string, unknown>, store: Record<string, unknown> = { name: "managed_with_environment_fallback", writable: true, state: "writable", reason: null }) => ({
  code: "openrouter", name: "OpenRouter (language models)", category: "ai_model", category_label: "AI / model", adapter: "OpenRouter chat API", description: "Chat model provider.",
  classification: "runtime_active", configuration_status: "configured", slots: [SLOT(slot)], settings: [],
  runtime: { enabled: true, managed: "environment", toggle_supported: false, note: "Runtime state is owned by the deployment environment." }, store,
  health: { status: "not_tested", last_tested_at: null, category: null, latency_ms: null }, test: { supported: true, note: "One key check." },
  validation_note: "Healthy only after a successful manual test.", audit: [] });
const MANAGED = { configured: true, source: "managed", source_kind: "managed", managed: true, managed_readable: true, revision: 2, last_rotated_at: "2026-10-14T09:00:00" };
const ENV = { configured: true, source: "environment", source_kind: "environment", environment_fallback: true };
const ROTATE = ["platform.integrations.read", "platform.integrations.manage", "platform.integrations.secret.rotate"];

beforeEach(() => {
  mockPerms = ROTATE;
  one.mockResolvedValue(DETAIL(MANAGED));
  replace.mockResolvedValue({ integration: "openrouter", slot: "api_key", configured: true, action: "rotated", revision: 3 });
  remove.mockResolvedValue({ integration: "openrouter", slot: "api_key", removed: true });
  stepUp.mockResolvedValue({ elevated: true });
});
afterEach(() => vi.clearAllMocks());

describe("credential source and store state", () => {
  it("labels the three sources honestly and never equates configured with healthy", async () => {
    for (const [slot, label] of [[MANAGED, /Managed secure store/], [ENV, /Source: Environment/], [{}, /Not configured/]] as const) {
      one.mockResolvedValue(DETAIL(slot as Record<string, unknown>));
      const { unmount } = render(<IntegrationDetailView code="openrouter" />);
      expect(await screen.findByTestId("source-api_key")).toHaveTextContent(label);
      expect(screen.getByText(/Configured only means a value exists, not that it is valid or healthy/)).toBeInTheDocument();
      expect(screen.getByText("Not tested")).toBeInTheDocument();
      unmount();
    }
  });

  it("explains that a managed credential overrides the environment and that the environment value is not changed", async () => {
    one.mockResolvedValue(DETAIL(ENV));
    render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByTestId("source-api_key")).toHaveTextContent(/overrides the environment value \(OPENROUTER_API_KEY\), which is not changed/);
  });

  it("an unavailable writable store is reported as unavailable with a bounded reason and offers no credential action", async () => {
    one.mockResolvedValue(DETAIL({ ...ENV, writable: false }, { name: "managed_with_environment_fallback", writable: false, state: "unavailable", reason: "key_missing" }));
    render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByTestId("store-state")).toHaveTextContent(/Secure writable credential store unavailable: its encryption key is not configured/);
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
  });

  it("a read-only (environment) store says credentials are managed in the deployment", async () => {
    one.mockResolvedValue(DETAIL({ ...ENV, writable: false }, { name: "environment", writable: false, state: "read_only", reason: null }));
    render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByTestId("store-state")).toHaveTextContent(/managed in the deployment environment \(read-only\)/);
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
  });

  it("tells the operator when a rotation needs a restart and when it applies on next use", async () => {
    one.mockResolvedValue(DETAIL({ ...MANAGED, applies: "next_use" }));
    const { unmount } = render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByText(/used on the next request that needs it/)).toBeInTheDocument();
    unmount();
    one.mockResolvedValue(DETAIL(MANAGED));
    render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByText(/used after the API and worker restart/)).toBeInTheDocument();
  });
});

describe("configure, rotate and remove", () => {
  it("configure: blank password input, step-up on demand, then the SAME write retries, the input clears and no value is rendered", async () => {
    one.mockResolvedValue(DETAIL({}));
    replace.mockRejectedValueOnce(new ApiError({ kind: "forbidden", status: 403, code: "step_up_required", message: "Confirm your password to continue." }));
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Configure credential" }));
    const dialog = screen.getByRole("alertdialog");
    const input = within(dialog).getByLabelText("Credential") as HTMLInputElement;
    expect(input.type).toBe("password");
    expect(input.value).toBe("");
    await user.type(input, SENTINEL);
    await user.click(within(dialog).getByRole("button", { name: "Save credential" }));
    const step = await screen.findByTestId("step-up-dialog");
    await user.type(within(step).getByLabelText("Current password"), "correct horse battery");
    await user.click(within(step).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(replace).toHaveBeenCalledTimes(2));
    expect(replace).toHaveBeenLastCalledWith("openrouter", "api_key", SENTINEL, null);
    expect(stepUp).toHaveBeenCalledWith("correct horse battery");
    expect(input.value).toBe("");
    expect(await screen.findByText(/It is saved but not tested/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(SENTINEL);
    expect(document.body.innerHTML).not.toContain(SENTINEL);
  });

  it("rotate: sends the shown revision so a stale page cannot overwrite a newer value", async () => {
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Replace credential" }));
    const dialog = screen.getByRole("alertdialog");
    await user.type(within(dialog).getByLabelText("New credential"), "a-brand-new-credential-1");
    await user.click(within(dialog).getByRole("button", { name: "Save credential" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("openrouter", "api_key", "a-brand-new-credential-1", 2));
    expect(await screen.findByText(/Credential replaced/)).toBeInTheDocument();
  });

  it("remove: explicit confirmation, explains the environment fallback, and uses the revision", async () => {
    one.mockResolvedValue(DETAIL({ ...MANAGED, environment_fallback: true }));
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Remove managed credential" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/deployment environment credential will be used again/)).toBeInTheDocument();
    expect(remove).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith("openrouter", "api_key", 2));
    expect(await screen.findByText(/environment credential is used again/)).toBeInTheDocument();
  });

  it("remove with no environment credential says it becomes not configured", async () => {
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Remove managed credential" }));
    expect(within(screen.getByRole("alertdialog")).getByText(/this credential will be not configured/)).toBeInTheDocument();
  });

  it("a failed save keeps a safe message, clears the input and never retries by itself", async () => {
    one.mockResolvedValue(DETAIL({}));
    replace.mockRejectedValue(new ApiError({ kind: "server", status: 503, code: "http_503", message: "The secure credential store is unavailable right now." }));
    const user = userEvent.setup();
    render(<IntegrationDetailView code="openrouter" />);
    await user.click(await screen.findByRole("button", { name: "Configure credential" }));
    const dialog = screen.getByRole("alertdialog");
    const input = within(dialog).getByLabelText("Credential") as HTMLInputElement;
    await user.type(input, SENTINEL);
    await user.click(within(dialog).getByRole("button", { name: "Save credential" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/unavailable/);
    expect(input.value).toBe("");
    expect(replace).toHaveBeenCalledTimes(1);
    expect(document.body.textContent).not.toContain(SENTINEL);
  });
});

describe("permissions: operations_admin inspects but never rotates; platform_admin can", () => {
  it("without secret.rotate (operations_admin) there is no credential control and no password input", async () => {
    mockPerms = ["platform.integrations.read", "platform.integrations.manage"];
    render(<IntegrationDetailView code="openrouter" />);
    await screen.findByRole("heading", { name: "Credentials" });
    expect(screen.getByRole("button", { name: "Test connection" })).toBeInTheDocument();       // permitted non-secret action stays
    expect(screen.queryByRole("button", { name: /credential/i })).not.toBeInTheDocument();
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });

  it("with secret.rotate (platform_admin) the controls exist", async () => {
    render(<IntegrationDetailView code="openrouter" />);
    expect(await screen.findByRole("button", { name: "Replace credential" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove managed credential" })).toBeInTheDocument();
  });
});

describe("no secret anywhere", () => {
  it("renders no value, mask, prefix or suffix and the client code uses no browser storage or URL for a credential", async () => {
    render(<IntegrationDetailView code="openrouter" />);
    await screen.findByRole("heading", { name: "Credentials" });
    expect(document.body.innerHTML).not.toMatch(/\*{3,}|•{3,}|…|\.\.\.\w|sk-[A-Za-z0-9]|last (four|4)/i);
    for (const f of ["components/admin/IntegrationDetailView.tsx", "components/admin/StepUp.tsx", "lib/api/client.ts"]) {
      const src = readFileSync(f, "utf8");
      expect(src, f).not.toMatch(/localStorage|sessionStorage/);
    }
    const detail = readFileSync("components/admin/IntegrationDetailView.tsx", "utf8");
    expect(detail).toContain("valueRef");
    expect(detail).not.toMatch(/\?value=|searchParams|router\.(push|replace)\([^)]*value/);
    const client = readFileSync("lib/api/client.ts", "utf8");
    expect(client).toMatch(/replaceCredential[\s\S]{0,400}body:/);                        // the value travels in the body only
  });
});
