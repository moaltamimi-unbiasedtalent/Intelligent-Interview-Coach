import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import recorded from "../e2e/fixtures/admin-responses.json";

// 03D2 Command Center and AI operations views: chart, missing-data and suppression rendering, permission handling and malformed responses.
// The fetch layer is stubbed, so the REAL client boundary (type guards in lib/admin/commandCenterGuard.ts) is exercised end to end.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

import { AiOperationsDashboard, BreakdownChart, CommandCenterDashboard, MetricTile } from "@/components/admin/CommandCenterDashboard";
import { MalformedCommandCenterResponse, assertCcDefinitions, assertCcSection, isCcBucket, isCcMetric, isCcSection } from "@/lib/admin/commandCenterGuard";
import type { CcMetric, CcSection } from "@/lib/admin/commandCenterGuard";
import { api } from "@/lib/api/client";
import { MISSING_LABEL, formatBucket, formatMetricFigure, formatMicroUsd } from "@/lib/admin/commandCenterFormat";
import { P } from "@/lib/admin/capabilities";

const REC = recorded as Record<string, any>;
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

const metric = (over: Partial<CcMetric> = {}): CcMetric => ({
  metric_id: "m", label: "Metric", unit: "count", period: "30d", state: "ok", value: 7, numerator: null, denominator: null, coverage: "Historical.", partial: false, note: "",
  evidence: "captured", evidence_source: "fact_table:x", suppression: "operational", dimensions: [], cost_micro_usd: null, breakdowns: [], ...over,
});
const section = (metrics: CcMetric[], over: Partial<CcSection> = {}): CcSection => ({
  section_id: "ai_operations", title: "AI operations", period: "30d", window_start: "2026-09-22T00:00:00+00:00", window_end: "2026-10-22T00:00:00+00:00",
  generated_at: "2026-10-22T00:00:00+00:00", utc: true, privacy: "Aggregates only.", captured_since: null, metrics, components: [], ...over,
});

function respond(map: Record<string, { status?: number; body: unknown }>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = new URL(url, "http://x").pathname.replace(/^.*\/api\/v1/, "");
    const hit = map[path];
    if (!hit) return new Response(JSON.stringify({ error: { code: "not_found", message: "x" } }), { status: 404, headers: { "content-type": "application/json" } });
    return new Response(JSON.stringify(hit.body), { status: hit.status ?? 200, headers: { "content-type": "application/json" } });
  }));
}
const recordedRoutes = () => Object.fromEntries(Object.keys(REC).filter((k) => k.startsWith("/admin/command-center/")).map((k) => [k, { body: REC[k] }]));

beforeEach(() => { mockPerms = []; });
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

describe("guards: the real recorded responses are accepted, malformed ones are not", () => {
  it("accepts every recorded section and the definitions", () => {
    for (const [k, v] of Object.entries(REC).filter(([k]) => k.startsWith("/admin/command-center/") && !k.endsWith("definitions"))) expect(isCcSection(v), k).toBe(true);
    expect(() => assertCcDefinitions(REC["/admin/command-center/definitions"])).not.toThrow();
  });

  it.each([
    ["an empty object", {}],
    ["null", null],
    ["metrics is not an array", { ...REC["/admin/command-center/jobs"], metrics: {} }],
    ["a metric without a state", { ...REC["/admin/command-center/jobs"], metrics: [{ ...REC["/admin/command-center/jobs"].metrics[0], state: undefined }] }],
    ["an unknown period", { ...REC["/admin/command-center/jobs"], period: "1y" }],
    ["components is a string", { ...REC["/admin/command-center/jobs"], components: "x" }],
  ])("rejects a section with %s", (_n, body) => {
    expect(isCcSection(body)).toBe(false);
    expect(() => assertCcSection(body)).toThrow(MalformedCommandCenterResponse);
  });

  it("rejects the contract break of a figure under a missing state (a number must never stand in for 'not captured')", () => {
    expect(isCcMetric(metric({ state: "not_captured", value: 0, evidence: "not_captured" }))).toBe(false);
    expect(isCcMetric(metric({ state: "suppressed", value: 3, evidence: "suppressed" }))).toBe(false);
    expect(isCcMetric(metric({ state: "ok", value: null }))).toBe(false);
    expect(isCcMetric(metric({ state: "unavailable", value: null, evidence: "unavailable" }))).toBe(true);
  });

  it("rejects a non-integer, negative or non-numeric micro-USD cost", () => {
    for (const bad of [1.5, -1, "12", Number.NaN]) expect(isCcMetric(metric({ unit: "usd", cost_micro_usd: bad as never }))).toBe(false);
    expect(isCcMetric(metric({ unit: "usd", value: 1.2345, cost_micro_usd: 1_234_500 }))).toBe(true);
  });

  it("rejects an unknown unit, an unknown evidence status and a bucket whose state and value disagree", () => {
    expect(isCcMetric(metric({ unit: "eur" as never }))).toBe(false);
    expect(isCcMetric(metric({ evidence: "great" as never }))).toBe(false);
    expect(isCcBucket({ key: "a", label: "a", state: "suppressed", value: 0, partial: false })).toBe(false);
    expect(isCcBucket({ key: "a", label: "a", state: "ok", value: null, partial: false })).toBe(false);
    expect(isCcBucket({ key: "a", label: "a", state: "unavailable", value: null, partial: false })).toBe(true);
  });

  it("rejects malformed definitions", () => {
    expect(() => assertCcDefinitions({})).toThrow(MalformedCommandCenterResponse);
    expect(() => assertCcDefinitions({ ...REC["/admin/command-center/definitions"], metrics: [{ metric_id: "x" }] })).toThrow(MalformedCommandCenterResponse);
  });

  it("the API client throws on a malformed 200 and never returns a silent empty success", async () => {
    respond({ "/admin/command-center/jobs": { body: {} }, "/admin/command-center/definitions": { body: { metrics: [] } } });
    await expect(api.admin.commandCenterSection("jobs", "30d")).rejects.toBeInstanceOf(MalformedCommandCenterResponse);
    await expect(api.admin.commandCenterDefinitions()).rejects.toBeInstanceOf(MalformedCommandCenterResponse);
  });
});

describe("display rules: missing is never zero; cost is exact integer micro-USD", () => {
  it("shows the state, never 0, for every missing state", () => {
    for (const state of ["suppressed", "unavailable", "not_captured"] as const) {
      const text = formatMetricFigure({ state, value: null, unit: "count", cost_micro_usd: null });
      expect(text).toBe(MISSING_LABEL[state]);
      expect(text).not.toMatch(/\b0\b/);
    }
    expect(formatMetricFigure({ state: "ok", value: 0, unit: "count", cost_micro_usd: null })).toBe("0");
    expect(formatBucket({ key: "a", label: "a", state: "suppressed", value: null, partial: false }, "count")).toBe(MISSING_LABEL.suppressed);
  });

  it("converts micro-USD without floating point and never rounds", () => {
    expect(formatMicroUsd(1_234_500)).toBe("USD 1.2345");
    expect(formatMicroUsd(1)).toBe("USD 0.000001");
    expect(formatMicroUsd(500_000)).toBe("USD 0.50");
    expect(formatMicroUsd(12_000_000)).toBe("USD 12.00");
    expect(formatMicroUsd(123_456_789_012)).toBe("USD 123,456.789012");
  });

  it("formats units", () => {
    expect(formatMetricFigure({ state: "ok", value: 12.5, unit: "percent", cost_micro_usd: null })).toBe("12.5%");
    expect(formatMetricFigure({ state: "ok", value: 840, unit: "milliseconds", cost_micro_usd: null })).toBe("840 ms");
    expect(formatMetricFigure({ state: "ok", value: 15000, unit: "tokens", cost_micro_usd: null })).toBe("15,000 tokens");
  });
});

describe("tiles and charts", () => {
  it("a cost tile shows the exact micro-USD amount, the partial-coverage wording, period, numerator and denominator, coverage, evidence and suppression", () => {
    render(<MetricTile m={metric({ metric_id: "ai_op_known_cost", label: "Known cost (USD, partial coverage)", unit: "usd", value: 1.2345, cost_micro_usd: 1_234_500, partial: true,
      evidence: "partial", numerator: 40, denominator: 100, suppression: "cohort", coverage: "Captured since the first AI usage fact." })} />);
    const g = screen.getByRole("heading", { name: "Known cost (USD, partial coverage)", level: 4 }).parentElement as HTMLElement;
    expect(within(g).getByText("USD 1.2345")).toBeInTheDocument();
    expect(within(g).getByText(/Known cost, partial coverage/)).toBeInTheDocument();
    expect(within(g).getByText("40 of 100")).toBeInTheDocument();
    expect(within(g).getByText("Last 30 days")).toBeInTheDocument();
    expect(within(g).getByText("Evidence: Partial coverage")).toBeInTheDocument();
    expect(within(g).getByText(/Captured since the first AI usage fact/)).toBeInTheDocument();
    expect(within(g).getByText(/small-cohort floor applies/)).toBeInTheDocument();
  });

  it("not captured, unavailable and suppressed tiles render as those states and never as zero", () => {
    render(<>
      <MetricTile m={metric({ metric_id: "a", label: "A", state: "not_captured", value: null, evidence: "not_captured" })} />
      <MetricTile m={metric({ metric_id: "b", label: "B", state: "unavailable", value: null, evidence: "unavailable" })} />
      <MetricTile m={metric({ metric_id: "c", label: "C", state: "suppressed", value: null, evidence: "suppressed", suppression: "cohort" })} />
    </>);
    expect(screen.getByTestId("fig-a")).toHaveTextContent("Not captured");
    expect(screen.getByTestId("fig-b")).toHaveTextContent("Unavailable");
    expect(screen.getByTestId("fig-c")).toHaveTextContent("Suppressed: small cohort");
    for (const id of ["a", "b", "c"]) expect(screen.getByTestId(`fig-${id}`).textContent).not.toMatch(/\d/);
    expect(screen.getByText(/Suppressed: below the privacy floor/)).toBeInTheDocument();
  });

  const bm = metric({ metric_id: "ai_op_usage_units", label: "AI usage units" });
  const bd = { dimension_id: "workflow", label: "Workflow", buckets: [
    { key: "career_ai", label: "career_ai", state: "ok" as const, value: 30, partial: false },
    { key: "practice_ai", label: "practice_ai", state: "ok" as const, value: 10, partial: true },
    { key: "agent", label: "agent", state: "suppressed" as const, value: null, partial: false },
    { key: "ocr", label: "ocr", state: "unavailable" as const, value: null, partial: false },
  ] };

  it("a breakdown chart prints every value, labels suppressed or unavailable buckets in text without drawing a bar, and has a data table equivalent", async () => {
    const { container } = render(<BreakdownChart metric={bm} breakdown={bd} />);
    const fig = screen.getByRole("figure", { name: /AI usage units by workflow/ });
    expect(within(fig).getAllByText("30")).toHaveLength(2);        // printed beside the bar and in the data table
    expect(within(fig).getByText("Practice ai (partial)")).toBeInTheDocument();
    expect(within(fig).getAllByText("Suppressed: small cohort").length).toBeGreaterThan(0);
    expect(within(fig).getAllByText("Unavailable").length).toBeGreaterThan(0);
    // two ok buckets are drawn; the two missing buckets draw no bar at all (never a zero-length bar)
    expect(container.querySelectorAll("li [aria-hidden='true']")).toHaveLength(2);
    await userEvent.setup().click(screen.getByText("Data table for this chart"));
    const table = screen.getByRole("table", { name: "AI usage units by Workflow" });
    expect(within(table).getAllByRole("row")).toHaveLength(5);
    expect(within(table).getByRole("rowheader", { name: "career_ai" })).toBeInTheDocument();
    expect(table.textContent).not.toMatch(/\b0\b/);
  });
});

describe("dashboard: permissions, states and failures", () => {
  it("hides sections the account may not read and names them as not permitted; never requests their routes", async () => {
    mockPerms = [P.overview, P.jobsRead];
    respond(recordedRoutes());
    render(<CommandCenterDashboard />);
    await screen.findByRole("heading", { name: "Platform health", level: 3 });
    await screen.findByRole("heading", { name: "Job queue health", level: 3 });
    expect(screen.queryByRole("heading", { name: "AI operations", level: 3 })).not.toBeInTheDocument();
    expect(screen.getByText(/Not permitted for your administrator role: AI operations, Knowledge readiness, Alerts, Auth and security signals, Candidate activity/)).toBeInTheDocument();
    const urls = (fetch as unknown as { mock: { calls: string[][] } }).mock.calls.map((c) => c[0]);
    expect(urls.some((u) => u.includes("/ai-operations") || u.includes("/alerts") || u.includes("/candidate-activity"))).toBe(false);
  });

  it("renders every section from the recorded real responses: not captured and suppressed never appear as zero", async () => {
    mockPerms = Object.values(P);
    respond(recordedRoutes());
    render(<CommandCenterDashboard />);
    for (const t of ["Platform health", "AI operations", "Job queue health", "Knowledge readiness", "Alerts", "Auth and security signals", "Candidate activity"])
      await screen.findByRole("heading", { name: t, level: 3 });
    await waitFor(() => expect(screen.queryAllByText("Loading...")).toHaveLength(0));
    expect(screen.getByTestId("fig-ai_op_known_cost")).toHaveTextContent("Not captured");
    expect(screen.getByTestId("fig-registrations")).toHaveTextContent("Suppressed: small cohort");
    expect(screen.getByTestId("fig-jobs_finished")).toHaveTextContent("Unavailable");
    expect(screen.getAllByText(/Known cost, partial coverage/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("a malformed 200 renders the explicit Admin error state for that section, the others still render, nothing crashes", async () => {
    mockPerms = [P.overview, P.jobsRead];
    respond({ ...recordedRoutes(), "/admin/command-center/jobs": { body: { metrics: [] } } });
    render(<CommandCenterDashboard />);
    await screen.findByRole("heading", { name: "Platform health", level: 3 });
    const jobs = (await screen.findByRole("heading", { name: "Job queue health", level: 3 })).closest("section") as HTMLElement;
    expect(await within(jobs).findByRole("alert")).toHaveTextContent("That request could not be processed.");
    expect(within(jobs).queryByText("Queued jobs")).not.toBeInTheDocument();         // not a silent empty success
    expect(screen.getByTestId("fig-platform_workers_active")).toBeInTheDocument();
  });

  it("malformed definitions show the error state but the figures still render", async () => {
    mockPerms = [P.overview];
    respond({ ...recordedRoutes(), "/admin/command-center/definitions": { body: {} } });
    render(<CommandCenterDashboard />);
    expect(await screen.findByText(/Metric definitions: That request could not be processed/)).toBeInTheDocument();
    await screen.findByTestId("fig-platform_workers_active");
  });

  it("a 403 from the server renders 'Not permitted', not an error", async () => {
    mockPerms = [P.overview, P.ai];
    respond({ ...recordedRoutes(), "/admin/command-center/ai-operations": { status: 403, body: { error: { code: "forbidden", message: "no" } } } });
    render(<AiOperationsDashboard />);
    expect(await screen.findByText(/Not permitted: your administrator role does not include AI operations/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("changing the period refetches with the fixed period value", async () => {
    mockPerms = [P.overview];
    respond(recordedRoutes());
    render(<CommandCenterDashboard />);
    await screen.findByTestId("fig-platform_workers_active");
    await userEvent.setup().selectOptions(screen.getByLabelText("Period"), "7d");
    await waitFor(() => {
      const urls = (fetch as unknown as { mock: { calls: string[][] } }).mock.calls.map((c) => c[0]);
      expect(urls.some((u) => u.includes("/health?period=7d"))).toBe(true);
    });
  });

  it("the AI operations view has labelled regions, semantic headings and charts with table equivalents when data exists", async () => {
    mockPerms = [P.overview, P.ai];
    const withData = clone(REC["/admin/command-center/ai-operations"]);
    const m = withData.metrics.find((x: any) => x.metric_id === "ai_op_usage_units");
    Object.assign(m, { state: "ok", value: 40, evidence: "captured", note: "", breakdowns: [{ dimension_id: "workflow", label: "Workflow", buckets: [
      { key: "agent", label: "agent", state: "ok", value: 25, partial: false }, { key: "practice", label: "practice", state: "ok", value: 15, partial: false }] }] });
    respond({ ...recordedRoutes(), "/admin/command-center/ai-operations": { body: withData } });
    render(<AiOperationsDashboard />);
    await screen.findByRole("figure", { name: /AI usage units by workflow/ });
    expect(screen.getByRole("heading", { name: "AI operations", level: 2 })).toBeInTheDocument();
    expect(screen.getAllByRole("region", { name: "AI operations" })).toHaveLength(2);   // the dashboard and its section are both labelled regions
    expect(screen.getByTestId("fig-ai_op_usage_units")).toHaveTextContent("40");
  });
});
