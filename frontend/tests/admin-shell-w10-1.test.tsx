import { readFileSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.1 - capability-aware Admin shell. Permissions come from the server (account.admin_permissions);
// the frontend only reflects them. Frontend gating is UX; the API authorises every request.

type Account = { platform_role: string; admin_permissions?: string[] } | null;
let mockAccount: Account = null;
let mockPath = "/admin";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => mockPath }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: mockAccount, status: "authenticated" }),
  useAuth: () => ({ account: mockAccount, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const home = vi.fn();
const providers = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { home: () => home(), providers: () => providers(), users: vi.fn(), audit: vi.fn(), workspaces: vi.fn() } },
}));

import { AdminShell } from "@/components/admin/AdminShell";
import { CommandCenter } from "@/components/admin/CommandCenter";
import { ProvidersView } from "@/components/admin/ProvidersView";
import { MoreMenu } from "@/components/layout/MoreMenu";

const ALL = [
  "platform.overview.read", "platform.users.read", "platform.workspaces.read",
  "platform.audit.read", "platform.integrations.read", "platform.ai.read", "platform.knowledge.read",
];

const HOME = {
  build: { version: "0.1.0", git_sha: "abc1234", build_time: "2026-10-02T10:00:00Z", environment: "staging", source: "x" },
  migrations: { repository_head: "0014_opportunities", database_revision: "0013_x", state: "mismatch", warning: "Database revision differs from the repository migration head." },
  health: { database: "reachable", providers_probed: false, note: "" },
  rate_limit: { mode: "in_memory_process_local", distributed: false, shared_store_requested: false, note: "" },
  pause: { paused: { ocr: true, agent: false }, durable: false, note: "Process-local and non-durable." },
  privacy_requests: { status: "not_operational", note: "Privacy-request administration is not available yet." },
  accounts: { users_total: 5, platform_admins: 1, premium_accounts: 2 },
  workspaces: { workspaces_total: 3 },
  diagnostics_links: [{ label: "Knowledge readiness", path: "/review/rag" }],
  boundary: "Operational metadata only.",
};

beforeEach(() => {
  mockAccount = { platform_role: "platform_admin", admin_permissions: ALL };
  mockPath = "/admin";
  home.mockResolvedValue(HOME);
});
afterEach(() => vi.clearAllMocks());

const navLinks = () => within(screen.getByRole("navigation", { name: "Admin" })).getAllByRole("link").map((a) => a.textContent ?? "");

describe("A1-A3 capability-aware navigation", () => {
  it("A1 shows only destinations the server permitted", () => {
    mockAccount = { platform_role: "support_operator", admin_permissions: ["platform.overview.read", "platform.users.read"] };
    render(<AdminShell><p>body</p></AdminShell>);
    const links = navLinks().join("|");
    expect(links).toContain("Overview");
    expect(links).toContain("Users");
    for (const hidden of ["Workspaces", "Audit", "Provider status", "Review"]) expect(links).not.toContain(hidden);
  });

  it("A2 a platform admin with these permissions sees the operational destinations, none of the future ones", () => {
    render(<AdminShell><p>body</p></AdminShell>);
    const links = navLinks();
    expect(links).toHaveLength(8);   // six W10.1 destinations plus Integrations (W10.6) and Knowledge (W10.8)
    const text = links.join("|");
    for (const ok of ["Overview", "Users", "Workspaces", "Review / Diagnostics", "Audit", "Provider status", "Integrations", "Knowledge"]) expect(text).toContain(ok);
    for (const future of ["Support", "Billing", "Subscriptions", "Jobs", "Knowledge administration", "Privacy requests", "Incidents", "Feature Flags"]) {
      expect(text).not.toContain(future);
    }
  });

  it("W10.3: Support appears only with platform.support.read", () => {
    render(<AdminShell><p>body</p></AdminShell>);
    expect(navLinks().join("|")).not.toContain("Support");
  });

  it("W10.3: a support operator sees Support", () => {
    mockAccount = { platform_role: "support_operator", admin_permissions: ["platform.overview.read", "platform.support.read"] };
    render(<AdminShell><p>body</p></AdminShell>);
    expect(navLinks().join("|")).toContain("Support");
  });

  it("A3 a candidate (no permissions) gets access denied and no admin navigation or body", () => {
    mockAccount = { platform_role: "user", admin_permissions: [] };
    render(<AdminShell><p>secret-body</p></AdminShell>);
    expect(screen.queryByRole("navigation", { name: "Admin" })).not.toBeInTheDocument();
    expect(screen.queryByText("secret-body")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("A3b a client-side role string alone grants nothing (no permissions from the server)", () => {
    mockAccount = { platform_role: "platform_admin" };
    render(<AdminShell><p>secret-body</p></AdminShell>);
    expect(screen.queryByText("secret-body")).not.toBeInTheDocument();
  });

  it("A3c the More menu follows the same server permissions", async () => {
    mockAccount = { platform_role: "knowledge_admin", admin_permissions: ["platform.overview.read", "platform.knowledge.read"] };
    render(<MoreMenu />);
    await userEvent.click(screen.getByRole("button", { name: /nav.more/ }));
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /Admin/ })).toHaveAttribute("href", "/admin");
    expect(within(menu).getByRole("menuitem", { name: /nav.review/ })).toBeInTheDocument();
  });
});

describe("A4 no client-side mapping or storage", () => {
  it("the capability module has no role-to-permission map and no browser storage", () => {
    const src = readFileSync("lib/admin/capabilities.ts", "utf8");
    expect(src).not.toMatch(/platform_admin|support_operator|billing_admin|ROLE_PRESETS/);
    expect(src).not.toMatch(/localStorage|sessionStorage|indexedDB|document\.cookie/);
    for (const f of ["components/admin/AdminShell.tsx", "components/admin/ui.tsx", "components/admin/CommandCenter.tsx"]) {
      expect(readFileSync(f, "utf8")).not.toMatch(/localStorage|sessionStorage|indexedDB/);
    }
  });

  it("rendering the shell does not touch web storage", () => {
    const get = vi.spyOn(Storage.prototype, "getItem");
    const set = vi.spyOn(Storage.prototype, "setItem");
    render(<AdminShell><p>x</p></AdminShell>);
    expect(get).not.toHaveBeenCalled();
    expect(set).not.toHaveBeenCalled();
  });
});

describe("A5 Command Center is truthful", () => {
  it("shows build metadata, a migration warning, health not tested and no fake privacy count", async () => {
    render(<CommandCenter />);
    expect(await screen.findByText("abc1234")).toBeInTheDocument();
    expect(screen.getByText("0014_opportunities")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/differs from the repository migration head/);
    expect(screen.getByText("Health not tested")).toBeInTheDocument();
    expect(screen.getByText(/In memory, per process/)).toBeInTheDocument();
    expect(screen.getByText(/non-durable/i)).toBeInTheDocument();
    expect(screen.getByText(/Privacy-request administration is not available yet/)).toBeInTheDocument();   // no stats supplied: no fake count
    expect(screen.queryByText(/open privacy requests/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Knowledge readiness" })).toHaveAttribute("href", "/review/rag");
  });

  it("shows unknown build details honestly", async () => {
    home.mockResolvedValue({ ...HOME, build: { ...HOME.build, git_sha: "unknown", build_time: "unknown" },
      migrations: { ...HOME.migrations, state: "unknown", warning: null } });
    render(<CommandCenter />);
    expect(await screen.findByText(/not injected into this deployment/)).toBeInTheDocument();
  });

  it("a candidate-permission-less account does not fetch the Command Center", async () => {
    mockAccount = { platform_role: "user", admin_permissions: [] };
    render(<CommandCenter />);
    expect(await screen.findByRole("status")).toHaveTextContent(/does not include access/);
    expect(home).not.toHaveBeenCalled();
  });
});

describe("A6 provider status does not equate configured with healthy", () => {
  it("renders configured + 'Health not tested' and no secret-looking value", async () => {
    providers.mockResolvedValue({
      providers: [{ provider_id: "openrouter", label: "Language model provider (OpenRouter)", configured: true, enabled: true,
        externally_managed: true, writable: false, status: "configured_health_not_tested", health: "Health not tested",
        live_validation: "UNVALIDATED", mode: null }],
      speech: {}, ocr: { engine: "tesseract", available: true, pdf_ocr_available: true, poppler_available: true, live_quality: "UNVALIDATED" },
      pause: {}, pause_durable: false, rate_limit_mode: "in_memory_process_local", rate_limit_distributed: false, note: "No provider is contacted here.",
    });
    render(<ProvidersView />);
    expect(await screen.findByText("Language model provider (OpenRouter)")).toBeInTheDocument();
    expect(screen.getByText("Health not tested")).toBeInTheDocument();
    expect(screen.getByText(/Configured/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/sk-[a-z0-9]/i);
  });
});

describe("A7 accessibility", () => {
  it("has a labelled nav, marks the current page and keeps every link keyboard reachable", async () => {
    mockPath = "/admin/users";
    render(<AdminShell><p>x</p></AdminShell>);
    const nav = screen.getByRole("navigation", { name: "Admin" });
    const current = within(nav).getAllByRole("link").filter((a) => a.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Users");
    await userEvent.tab();
    expect(within(nav).getAllByRole("link")[0]).toHaveFocus();
    expect(within(nav).getAllByRole("link").every((a) => a.getAttribute("tabindex") !== "-1")).toBe(true);
  });

  it("status is conveyed by text, not colour alone", async () => {
    render(<CommandCenter />);
    await waitFor(() => expect(screen.getByText("Revision mismatch")).toBeInTheDocument());
  });
});
