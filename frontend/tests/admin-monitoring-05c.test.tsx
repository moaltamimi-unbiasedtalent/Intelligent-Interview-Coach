import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 05C: Admin provider readiness shows alert and AI budget state. The payload is validated at the component boundary: a malformed 200 shows an explicit unavailable state and never a
// crash or a healthy-looking value; "no evidence yet" is never rendered as OK.

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/providers" }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a>,
}));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "platform_admin", admin_permissions: ["platform.integrations.read"] }, status: "authenticated" }),
  useAuth: () => ({ account: { platform_role: "platform_admin", admin_permissions: ["platform.integrations.read"] }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const providers = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { admin: { providers: () => providers() } } }));

import { MonitoringPanel, ProvidersView } from "@/components/admin/ProvidersView";

const base = {
  providers: [],
  speech: {},
  ocr: { engine: "tesseract", available: true, pdf_ocr_available: true, poppler_available: true, live_quality: "UNVALIDATED" },
  pause: {}, pause_durable: true, rate_limit_mode: "in_memory_process_local", rate_limit_distributed: false, note: "No provider is contacted here.",
};
const monitoring = {
  alerts: { active: 2, by_category: { provider_unhealthy: 1, ai_budget_attention: 1 } },
  budget: { state: "open", enforcement: "enforcing", budget_class: "production", reason: null, remaining_to_stop_usd: "3.250000", remaining_requests: 880 },
  signals: [
    { code: "api_error_rate", status: "ok" }, { code: "provider_health", status: "failing" }, { code: "worker_health", status: "unknown" },
    { code: "job_backlog", status: "unknown" }, { code: "indexing_progress", status: "ok" }, { code: "quota_reaper", status: "ok" }, { code: "ai_budget", status: "ok" },
  ],
  note: "Derived from recorded facts; nothing is probed.",
};

beforeEach(() => providers.mockReset());

describe("Admin provider readiness: alert and budget state", () => {
  it("shows alert count, budget state, headroom and every signal, with unknown kept distinct from OK", async () => {
    providers.mockResolvedValue({ ...base, monitoring });
    render(<ProvidersView />);
    const panel = (await screen.findByText("Alerts and AI budget")).closest("section") ?? document.body;
    const scope = within(panel as HTMLElement);
    expect(scope.getByText("Active operational alerts")).toBeInTheDocument();
    expect(scope.getByText("2")).toBeInTheDocument();
    expect(scope.getByText("enforcing")).toBeInTheDocument();
    expect(scope.getByText("production")).toBeInTheDocument();
    expect(scope.getByText("3.250000")).toBeInTheDocument();
    expect(scope.getByText("880")).toBeInTheDocument();
    expect(scope.getByText("Language model provider")).toBeInTheDocument();
    expect(scope.getAllByText(/No evidence yet/).length).toBe(2);
    expect(scope.getAllByText(/Failing/).length).toBe(1);
    expect(document.body.textContent).not.toMatch(/sk-[a-z0-9]/i);
  });

  it("an older server without monitoring shows an explicit unavailable state, not a healthy one", async () => {
    providers.mockResolvedValue({ ...base });
    render(<ProvidersView />);
    expect(await screen.findByText(/Monitoring state is unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/not a healthy state/)).toBeInTheDocument();
  });

  it.each([
    ["null", null],
    ["a string", "ok"],
    ["a list", []],
    ["alerts missing", { signals: [] }],
    ["signal with an unknown status", { alerts: { active: 0, by_category: {} }, signals: [{ code: "x", status: "great" }], budget: null, note: "" }],
    ["signals not an array", { alerts: { active: 0, by_category: {} }, signals: "none", budget: null, note: "" }],
  ])("a malformed monitoring payload (%s) never crashes the page", (_name, payload) => {
    render(<MonitoringPanel monitoring={payload} />);
    expect(screen.getByText(/Monitoring state is unavailable/)).toBeInTheDocument();
  });

  it("a missing budget renders as unavailable, not as zero", () => {
    render(<MonitoringPanel monitoring={{ ...monitoring, budget: null }} />);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });
});
