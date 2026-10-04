import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.12 Admin Reports UI. APIs are mocked; the real SQL, suppression and cohort maths are proven by tests/test_reporting_w10_12.py.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/reports" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { user_id: 7, platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
const report = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { admin: { report: (...a: unknown[]) => report(...a) } } }));

import { ReportsView } from "@/components/admin/ReportsView";

const M = (o: Record<string, unknown>) => ({ metric_id: "m", label: "Metric", figure: 1, unit: "count", state: "available", coverage: "", note: "", ...o });
const SEC = (o: Record<string, unknown> = {}) => ({ section_id: "s", title: "Section", coverage: "Historical", captured_since: null, note: "", metrics: [], tables: [], ...o });
const REP = (sections: unknown[], o: Record<string, unknown> = {}) => ({ period: "30d", window_start: "2026-09-05T00:00:00+00:00", window_end: "2026-10-05T00:00:00+00:00", generated_at: "x", utc: true,
  privacy: "Aggregates only.", sections, mock_billing: false, label: null, ...o });

beforeEach(() => {
  mockPerms = ["platform.reports.read"];
  report.mockImplementation(async (kind: string) => REP([SEC({ section_id: kind, title: `${kind} section`, metrics: [M({ metric_id: "registrations", label: "Registrations", figure: 12 })] })]));
});
afterEach(() => vi.clearAllMocks());

describe("Admin Reports", () => {
  it("a reports.read principal sees Product, Quality, Operations and AI economics but never Commercial, and never requests it", async () => {
    render(<ReportsView />);
    expect(await screen.findByText("Registrations")).toBeInTheDocument();
    for (const name of ["Product", "Quality", "Operations", "AI economics"]) expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Commercial" })).not.toBeInTheDocument();
    expect(screen.queryByText(/MOCK BILLING/)).not.toBeInTheDocument();
    for (const call of report.mock.calls) expect(call[0]).not.toBe("commercial");
  });

  it("a commercial-only principal sees only Commercial with the MOCK BILLING warning", async () => {
    mockPerms = ["platform.reports.commercial.read"];
    report.mockResolvedValue(REP([SEC({ section_id: "mock_billing", title: "MOCK BILLING - NOT LIVE REVENUE", metrics: [M({ metric_id: "mock_mrr", label: "Mock MRR", figure: null, state: "unavailable", note: "Unconfigured: not zero revenue." })] })], { mock_billing: true, label: "MOCK BILLING - NOT LIVE REVENUE" }));
    render(<ReportsView />);
    expect(await screen.findByText("Mock MRR")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("MOCK BILLING — NOT LIVE REVENUE");
    expect(screen.getAllByRole("tab")).toHaveLength(1);
    expect(screen.getByRole("tab", { name: "Commercial" })).toBeInTheDocument();
    expect(report).toHaveBeenCalledWith("commercial", "30d");
    expect(screen.getByText("Unconfigured: not zero revenue.")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();                                          // missing price is never rendered as zero
  });

  it("both permissions show all five tabs", async () => {
    mockPerms = ["platform.reports.read", "platform.reports.commercial.read"];
    render(<ReportsView />);
    await screen.findByText("Registrations");
    expect(screen.getAllByRole("tab")).toHaveLength(5);
  });

  it("changing the period refetches with a fixed period id", async () => {
    render(<ReportsView />);
    await screen.findByText("Registrations");
    await userEvent.selectOptions(screen.getByLabelText("Period (UTC)"), "90d");
    await waitFor(() => expect(report).toHaveBeenLastCalledWith("product", "90d"));
    expect(screen.getAllByRole("option").map((o) => (o as HTMLOptionElement).value)).toEqual(["7d", "30d", "90d", "all_time"]);   // no free date input
  });

  it("a suppressed metric shows text, never 0 or a threshold, and partial coverage is textual", async () => {
    report.mockResolvedValue(REP([SEC({ metrics: [M({ metric_id: "a", label: "Activation", figure: null, state: "suppressed" }), M({ metric_id: "b", label: "Known cost", figure: 0.06, unit: "usd", state: "partial", coverage: "Cost coverage 50.0% of usage units" })] })]));
    render(<ReportsView />);
    expect(await screen.findAllByText("Suppressed: small cohort")).not.toHaveLength(0);
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.queryByText(/<\s*5/)).not.toBeInTheDocument();
    expect(screen.getByText("0.06 USD")).toBeInTheDocument();
    expect(screen.getByText("Partial coverage")).toBeInTheDocument();
    expect(screen.getByText("Cost coverage 50.0% of usage units")).toBeInTheDocument();
  });

  it("unknown tokens and cost render as Not captured, not zero", async () => {
    report.mockResolvedValue(REP([SEC({ metrics: [M({ metric_id: "t", label: "Known tokens", figure: null, state: "not_captured" }), M({ metric_id: "c", label: "Known cost", figure: null, state: "not_captured" })] })]));
    render(<ReportsView />);
    expect((await screen.findAllByText("Not captured")).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.queryByText(/\$0/)).not.toBeInTheDocument();
  });

  it("tables label columns, mark suppressed cells and carry a caption", async () => {
    report.mockResolvedValue(REP([SEC({ tables: [{ table_id: "t", title: "Usage by workflow", columns: ["Model calls", "Known cost USD"], note: "n",
      rows: [{ label: "agent", cells: [{ figure: null, suppressed: true }, { figure: null, suppressed: true }] }, { label: "practice", cells: [{ figure: 40, suppressed: false }, { figure: null, suppressed: false }] }] }] })]));
    render(<ReportsView />);
    const table = await screen.findByRole("table", { name: "Usage by workflow" });
    expect(within(table).getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Group", "Model calls", "Known cost USD"]);
    expect(within(table).getAllByText("Suppressed: small cohort")).toHaveLength(2);
    expect(within(table).getByText("40")).toBeInTheDocument();
    expect(within(table).getByText("Not captured")).toBeInTheDocument();
  });

  it("denies the view without a reports permission", () => {
    mockPerms = ["platform.overview.read"];
    render(<ReportsView />);
    expect(screen.getByText(/does not include access/)).toBeInTheDocument();
  });

  it("the source offers no per-user drilldown, no export and no role-name authorization", () => {
    const t = readFileSync(join(process.cwd(), "components/admin/ReportsView.tsx"), "utf8");
    expect(t).not.toMatch(/localStorage|sessionStorage|platform_admin|billing_admin|operations_admin|href=|download|exportTo|Export/);
    expect(t).not.toContain("—".repeat(2));
  });
});
