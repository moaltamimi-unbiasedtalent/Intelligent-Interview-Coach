import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 03E2: the governed report builder UI over the merged 03E1 API. The real API client runs against a stubbed fetch, so the client-boundary guards are exercised.

let mockPerms: string[] = [];
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

import { ReportBuilderView } from "@/components/admin/ReportBuilderView";
import { api } from "@/lib/api/client";
import {
  definitionQuery, figureText, isAdminReport, isPreviewResult, isReportRegistry, isSavedList, isValidateResult, offeredFilterLabels, problemsFromMessage,
  type BuilderDefinition, type PreviewResult, type ReportRegistry,
} from "@/lib/admin/reportBuilder";

const STD = ["platform.overview.read", "platform.reports.read"];
const COM = ["platform.overview.read", "platform.reports.commercial.read"];

const REG = (over: Partial<ReportRegistry> = {}): ReportRegistry => ({
  report_types: [
    { report_id: "product", title: "Product report", description: "Funnel figures.", permission_required: "platform.reports.read", windows: ["7d", "30d", "90d"],
      metrics: [
        { metric_id: "registrations", label: "Registrations", description: "New accounts.", unit: "count", coverage: "Historical", suppression: "cohort", dimensions: [], must_group_by: null, comparable: true },
        { metric_id: "feedback", label: "Feedback items", description: "Feedback.", unit: "count", coverage: "Historical", suppression: "cohort", dimensions: ["feedback_category"], must_group_by: null, comparable: true },
      ] },
  ],
  dimensions: [{ dimension_id: "feedback_category", label: "Feedback category", description: "Safe categories.", kind: "category", max_buckets: 20 }],
  windows: ["7d", "30d", "90d"], chart_kinds: ["trend", "funnel", "share_of_whole", "distribution", "table"], comparisons: ["none", "previous_period"],
  limits: { max_metrics: 12, max_filters: 3, max_filter_values: 10, max_export_rows: 2000, max_definition_bytes: 2048 }, min_cohort: 5, rules: ["Aggregates only."], ...over,
});
const COMREG = (): ReportRegistry => ({
  ...REG(),
  report_types: [{ report_id: "commercial", title: "Commercial report", description: "Mock.", permission_required: "platform.reports.commercial.read", windows: ["30d"],
    metrics: [{ metric_id: "mock_mrr", label: "Mock MRR", description: "Mock.", unit: "usd", coverage: "Mock", suppression: "operational", dimensions: ["feedback_category"], must_group_by: "feedback_category", comparable: false }] }],
});

const PREVIEW = (over: Partial<PreviewResult> = {}): PreviewResult => ({
  report_id: "product", title: "Product report", window: "30d", window_start: "2026-09-22T00:00:00+00:00", window_end: "2026-10-22T00:00:00+00:00", generated_at: "x", utc: true, group_by: null,
  filters: [], chart: "distribution", comparison: "none", previous_window_start: null, previous_window_end: null, privacy: "Aggregates only.",
  metrics: [{ metric_id: "registrations", label: "Registrations", unit: "count", period: "30d", coverage: "Historical", suppression: "cohort", state: "ok", value: 42, partial: false, note: "",
    group_dimension: null, buckets: null, previous: null }], ...over,
});

const j = (body: unknown, status = 200, headers: Record<string, string> = {}) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
type Handler = (url: URL, init?: RequestInit) => Response | undefined;
let handlers: Handler[] = [];
let calls: { method: string; path: string; search: string; body?: unknown }[] = [];

beforeEach(() => {
  calls = [];
  handlers = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://x.test");
    const path = url.pathname.replace(/^\/api\/v1/, "");
    calls.push({ method: init?.method ?? "GET", path, search: url.search, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    for (const h of handlers) { const r = h(url, init); if (r) return r; }
    if (path.endsWith("/registry")) return j(path.includes("commercial") ? COMREG() : REG());
    if (path.endsWith("/saved")) return j({ items: [], max_saved: 25 });
    if (path.endsWith("/validate")) return j({ valid: true, problems: [] });
    if (path.endsWith("/preview")) return j(PREVIEW());
    return j({ error: { code: "not_found", message: "x", request_id: "r" } }, 404);
  }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function ready() {
  render(<ReportBuilderView />);
  await screen.findByRole("heading", { name: "Builder" });
  await screen.findByText("Definition is valid");
}

describe("client-boundary guards (negative)", () => {
  const def: BuilderDefinition = { report_id: "product", metric_ids: ["registrations"], window: "30d", group_by: null, filters: [], chart: null, comparison: "none" };

  it("accepts the documented shapes", () => {
    expect(isReportRegistry(REG())).toBe(true);
    expect(isPreviewResult(PREVIEW())).toBe(true);
    expect(isValidateResult({ valid: false, problems: [{ code: "x", field: "f", message: "m" }] })).toBe(true);
    expect(isSavedList({ items: [], max_saved: 25 })).toBe(true);
  });
  it("rejects an empty object, null and arrays for every response type", () => {
    for (const g of [isReportRegistry, isPreviewResult, isValidateResult, isSavedList]) for (const bad of [{}, null, [], "x", 3]) expect(g(bad)).toBe(false);
  });
  it("rejects a registry whose metric names an unregistered dimension or an impossible must-group", () => {
    const r = REG();
    r.report_types[0].metrics[1].dimensions = ["not_registered"];
    expect(isReportRegistry(r)).toBe(false);
    const r2 = REG();
    r2.report_types[0].metrics[0].must_group_by = "feedback_category";
    expect(isReportRegistry(r2)).toBe(false);
  });
  it("rejects a metric or bucket that is not ok but carries a figure (never a number for a suppressed value)", () => {
    const p = PREVIEW();
    p.metrics[0].state = "suppressed";
    expect(isPreviewResult(p)).toBe(false);
    const q = PREVIEW({ metrics: [{ ...PREVIEW().metrics[0], buckets: [{ label: "a", state: "suppressed", value: 0 }] }] });
    expect(isPreviewResult(q)).toBe(false);
    const r = PREVIEW({ metrics: [{ ...PREVIEW().metrics[0], value: null }] });
    expect(isPreviewResult(r)).toBe(false);                                             // ok without a figure and without buckets
  });
  it("rejects wrong field types and a valid=true result that lists problems", () => {
    expect(isPreviewResult({ ...PREVIEW(), metrics: "none" })).toBe(false);
    expect(isPreviewResult({ ...PREVIEW(), window_end: 5 })).toBe(false);
    expect(isValidateResult({ valid: true, problems: [{ code: "a", field: "b", message: "c" }] })).toBe(false);
    expect(isValidateResult({ valid: false, problems: [] })).toBe(false);
    expect(isSavedList({ items: [{ id: "1" }], max_saved: 25 })).toBe(false);
    expect(isSavedList({ items: [{ id: 1, name: "n", report_id: "product", definition: null, valid: true, shared: false, revision: 1, editable: true, created_at: null, updated_at: null }], max_saved: 25 })).toBe(false);
  });
  it("a malformed 200 from the real client is an explicit error, not a value", async () => {
    handlers.push((u) => (u.pathname.endsWith("/registry") ? j({}) : undefined));
    await expect(api.admin.reportBuilder.standard.registry()).rejects.toMatchObject({ code: "malformed_response" });
    handlers.unshift((u) => (u.pathname.endsWith("/preview") ? j({ report_id: "product" }) : undefined));
    await expect(api.admin.reportBuilder.standard.preview(def)).rejects.toMatchObject({ code: "malformed_response" });
  });
  it("the fixed standard report shape is checked too: a malformed 200 is rejected", async () => {
    const ok = { period: "30d", window_start: null, window_end: "x", generated_at: "x", utc: true, privacy: "p", sections: [{ section_id: "s", title: "t", coverage: "c", captured_since: null, note: "",
      metrics: [{ metric_id: "m", label: "l", figure: null, unit: "count", state: "suppressed", coverage: "", note: "" }], tables: [] }] };
    expect(isAdminReport(ok)).toBe(true);
    for (const bad of [{}, null, { ...ok, sections: "x" }, { ...ok, sections: [{ ...ok.sections[0], metrics: [{ metric_id: "m" }] }] }, { ...ok, utc: "yes" }]) expect(isAdminReport(bad)).toBe(false);
    handlers.push((u) => (u.pathname.endsWith("/admin/reports/product") ? j({ sections: [null] }) : undefined));
    await expect(api.admin.report("product", "30d")).rejects.toMatchObject({ code: "malformed_response" });
  });
  it("builds the query only from the definition's registered ids", () => {
    const q = definitionQuery({ ...def, metric_ids: ["a", "b"], group_by: "feedback_category", filters: [{ dimension_id: "feedback_category", values: ["bug", "idea"] }], chart: "table", comparison: "previous_period" });
    expect(q).toContain("metric_ids=a&metric_ids=b");
    expect(q).toContain("filter=feedback_category%3Abug&filter=feedback_category%3Aidea");
  });
  it("parses stable problem codes and never invents one; shows states, never zero for missing", () => {
    expect(problemsFromMessage("[unknown_metric] A metric id is not registered.; [window_not_allowed] The window must be one of 7d.")).toEqual([
      { code: "unknown_metric", field: "", message: "A metric id is not registered." }, { code: "window_not_allowed", field: "", message: "The window must be one of 7d." }]);
    expect(problemsFromMessage("Something odd")).toEqual([]);
    expect(figureText("suppressed", null, "count")).toBe("Suppressed: small cohort");
    expect(figureText("not_captured", null, "count")).toBe("Not captured");
    expect(figureText("ok", 0, "count")).toBe("0");
    expect(offeredFilterLabels(PREVIEW({ metrics: [{ ...PREVIEW().metrics[0], buckets: [{ label: "bug", state: "ok", value: 9 }, { label: "<script>", state: "suppressed", value: null }] }] }))).toEqual(["bug"]);
  });
});

describe("builder UI", () => {
  it("offers only registered choices and no free-text field besides the save name", async () => {
    mockPerms = STD;
    await ready();
    const boxes = screen.getAllByRole("textbox");
    expect(boxes).toHaveLength(1);
    expect(boxes[0]).toHaveAccessibleName(/Name \(3 to 60 characters\)/);
    expect(screen.getByRole("checkbox", { name: /Registrations/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Feedback items/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Window (UTC)").querySelectorAll("option")).toHaveLength(3);
    expect(screen.queryByText(/mock_mrr|Commercial report/)).toBeNull();
    expect(calls.some((c) => c.path.includes("commercial"))).toBe(false);                 // never requested without the commercial permission
  });

  it("shows the API's stable problem codes and disables run and export while invalid", async () => {
    mockPerms = STD;
    handlers.push((u) => (u.pathname.endsWith("/validate") ? j({ valid: false, problems: [{ code: "chart_incompatible", field: "chart", message: "This chart cannot be built from the selected metrics." }] }) : undefined));
    render(<ReportBuilderView />);
    const alert = await screen.findByText(/This definition cannot be run/);
    expect(within(alert.closest("[role=alert]") as HTMLElement).getByText("[chart_incompatible]")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run preview" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Export JSON" })).toBeDisabled();
  });

  it("renders a suppressed bucket and a not-captured metric as such, never as zero, with a data table equivalent", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    handlers.push((u) => (u.pathname.endsWith("/preview") ? j(PREVIEW({
      group_by: "feedback_category", chart: "distribution",
      metrics: [{ ...PREVIEW().metrics[0], metric_id: "feedback", label: "Feedback items", state: "ok", value: null, group_dimension: "feedback_category",
        buckets: [{ label: "bug", state: "ok", value: 9 }, { label: "idea", state: "suppressed", value: null }, { label: "other", state: "unavailable", value: null }] },
      { ...PREVIEW().metrics[0], state: "not_captured", value: null, note: "No evidence." }] })) : undefined));
    await ready();
    await user.click(screen.getByRole("button", { name: "Run preview" }));
    await screen.findByRole("heading", { name: "Preview: Product report" });
    const table = screen.getByRole("table", { name: /Data table equivalent of the chart/ });
    expect(within(table).getByRole("row", { name: /idea.*Suppressed: small cohort/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /other.*Unavailable/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /bug.*9/ })).toBeInTheDocument();
    expect(screen.getAllByText("Not captured").length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: /idea Suppressed: small cohort/ })).toBeInTheDocument();
    const zeroCells = screen.queryAllByRole("cell").filter((c) => c.textContent?.trim() === "0");
    expect(zeroCells).toHaveLength(0);
  });

  it("a malformed preview 200 shows the explicit error and keeps the page alive", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    handlers.push((u) => (u.pathname.endsWith("/preview") ? j({ nonsense: true }) : undefined));
    await ready();
    await user.click(screen.getByRole("button", { name: "Run preview" }));
    expect(await screen.findByText(/unexpected form/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Builder" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Preview:/ })).toBeNull();
  });

  it("a malformed registry shows the Admin error state", async () => {
    mockPerms = STD;
    handlers.push((u) => (u.pathname.endsWith("/registry") ? j({ report_types: "x" }) : undefined));
    render(<ReportBuilderView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("That request could not be processed.");
  });

  it("a refused export or a 503 audit failure shows an explicit error and creates no file", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    const create = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    handlers.push((u) => (u.pathname.endsWith("/export") ? j({ error: { code: "http_503", message: "The export could not be audited, so nothing was exported.", request_id: "r" } }, 503) : undefined));
    await ready();
    await user.click(screen.getByRole("button", { name: "Export CSV" }));
    const note = await screen.findByText(/nothing was exported\. No file was downloaded\./);
    expect(note.closest("[role=alert]")).not.toBeNull();
    expect(create).not.toHaveBeenCalled();
    handlers.unshift((u) => (u.pathname.endsWith("/export") ? j({ error: { code: "http_403", message: "Administrator access required.", request_id: "r" } }, 403) : undefined));
    await user.click(screen.getByRole("button", { name: "Export JSON" }));
    await waitFor(() => expect(screen.getByRole("alert", { name: "" })).toHaveTextContent(/refused/));
    expect(create).not.toHaveBeenCalled();
  });

  it("an export that returns the wrong content type is refused and no file is created", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    const create = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    handlers.push((u) => (u.pathname.endsWith("/export") ? new Response("<html>", { status: 200, headers: { "content-type": "text/html" } }) : undefined));
    await ready();
    await user.click(screen.getByRole("button", { name: "Export CSV" }));
    expect(await screen.findByText(/No file was downloaded/)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it("a successful export downloads the file after the audited response and posts only the registered definition", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    const create = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    handlers.push((u) => (u.pathname.endsWith("/export") ? new Response("a,b\r\n", { status: 200, headers: { "content-type": "text/csv; charset=utf-8", "content-disposition": 'attachment; filename="ask4mo-product-30d-20261022.csv"', "x-export-rows": "1" } }) : undefined));
    await ready();
    await user.click(screen.getByRole("button", { name: "Export CSV" }));
    expect(await screen.findByText(/Downloaded ask4mo-product-30d-20261022\.csv \(1 rows\)/)).toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(1);
    const body = calls.find((c) => c.path.endsWith("/export"))!.body as { format: string; definition: BuilderDefinition };
    expect(body.format).toBe("csv");
    expect(body.definition).toEqual({ report_id: "product", metric_ids: ["registrations"], window: "30d", group_by: null, filters: [], chart: null, comparison: "none" });
  });

  it("commercial reports are offered only to the commercial permission, and never request the standard family", async () => {
    mockPerms = COM;
    render(<ReportBuilderView />);
    await screen.findByRole("heading", { name: "Builder" });
    expect(screen.getByText(/MOCK BILLING: NOT LIVE REVENUE/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Commercial report" })).toBeInTheDocument();
    expect(calls.some((c) => c.path.startsWith("/admin/report-builder/registry"))).toBe(false);
    // a must-group metric forces its grouping dimension; the select cannot be left empty
    expect(screen.getByLabelText("Group by")).toBeDisabled();
    expect(screen.getByLabelText("Group by")).toHaveValue("feedback_category");
    expect(screen.getByLabelText("Comparison")).toBeDisabled();
  });

  it("a holder of both permissions can switch family; neither permission renders no builder", async () => {
    mockPerms = [...STD, "platform.reports.commercial.read"];
    const user = userEvent.setup();
    const { unmount } = render(<ReportBuilderView />);
    await screen.findByRole("heading", { name: "Product report" });
    await user.click(screen.getByRole("button", { name: "Commercial (mock billing)" }));
    await screen.findByRole("heading", { name: "Commercial report" });
    unmount();
    mockPerms = ["platform.overview.read"];
    render(<ReportBuilderView />);
    expect(screen.getByRole("status")).toHaveTextContent(/does not include report access/);
  });
});

describe("saved configuration management", () => {
  const SAVED = (over = {}) => ({ id: 7, name: "My report", report_id: "product", definition: { report_id: "product", metric_ids: ["registrations"], window: "7d", group_by: null, filters: [], chart: null, comparison: "none" },
    valid: true, shared: false, revision: 3, editable: true, created_at: null, updated_at: null, ...over });

  it("loads, updates with the expected revision, shares, renames and deletes with the revision", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    let item = SAVED();
    handlers.push((u, init) => {
      if (u.pathname.endsWith("/saved") && (init?.method ?? "GET") === "GET") return j({ items: [item], max_saved: 25 });
      if (/\/saved\/7$/.test(u.pathname) && init?.method === "PUT") { item = { ...item, ...JSON.parse(String(init.body)), revision: item.revision + 1 }; return j(item); }
      if (/\/saved\/7$/.test(u.pathname) && init?.method === "DELETE") return new Response(null, { status: 204 });
      return undefined;
    });
    await ready();
    await user.click(await screen.findByRole("button", { name: "Load My report into the builder" }));
    expect(screen.getByLabelText("Window (UTC)")).toHaveValue("7d");
    await waitFor(() => expect(screen.getByRole("button", { name: /Update "My report"/ })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: /Update "My report"/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect((calls.find((c) => c.method === "PUT")!.body as { expected_revision: number }).expected_revision).toBe(3);
    await screen.findByText("Updated.");
    await user.click(await screen.findByRole("button", { name: "Share My report" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(2));
    const second = calls.filter((c) => c.method === "PUT")[1].body as { expected_revision: number; shared: boolean };
    expect(second).toMatchObject({ expected_revision: 4, shared: true });
    await user.click(await screen.findByRole("button", { name: "Rename My report" }));
    const input = screen.getByLabelText("New name");
    await user.clear(input);
    await user.type(input, "Weekly view");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(3));
    expect((calls.filter((c) => c.method === "PUT")[2].body as { name: string; expected_revision: number })).toMatchObject({ name: "Weekly view", expected_revision: 5 });
    await user.click(await screen.findByRole("button", { name: "Delete Weekly view" }));
    await user.click(screen.getByRole("button", { name: "Confirm delete Weekly view" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
    expect(calls.find((c) => c.method === "DELETE")!.path).toBe("/admin/report-builder/saved/7");
    expect(calls.find((c) => c.method === "DELETE")!.search).toBe("?expected_revision=6");
  });

  it("a revision conflict is shown and nothing is overwritten; a shared item is read only; an invalid one cannot be loaded", async () => {
    mockPerms = STD;
    const user = userEvent.setup();
    handlers.push((u, init) => {
      if (u.pathname.endsWith("/saved") && (init?.method ?? "GET") === "GET") {
        return j({ items: [SAVED(), SAVED({ id: 8, name: "Theirs", editable: false, shared: true }), SAVED({ id: 9, name: "Broken", valid: false, definition: null })], max_saved: 25 });
      }
      if (/\/saved\/7$/.test(u.pathname) && init?.method === "PUT") return j({ error: { code: "conflict", message: "stale", request_id: "r" } }, 409);
      return undefined;
    });
    await ready();
    await user.click(await screen.findByRole("button", { name: "Share My report" }));
    expect(await screen.findByText(/changed elsewhere/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rename Theirs" })).toBeNull();
    expect(screen.getByText("Shared with you (read only)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load Broken into the builder" })).toBeDisabled();
    expect(screen.getByText("No longer valid")).toBeInTheDocument();
  });

  it("a malformed saved list shows the Admin error state, not a crash or an empty list", async () => {
    mockPerms = STD;
    handlers.push((u) => (u.pathname.endsWith("/saved") ? j({ items: "x" }) : undefined));
    render(<ReportBuilderView />);
    await screen.findByRole("heading", { name: "Builder" });
    expect(await screen.findByText("That request could not be processed.")).toBeInTheDocument();
    expect(screen.queryByText("No saved reports yet.")).toBeNull();
  });
});
