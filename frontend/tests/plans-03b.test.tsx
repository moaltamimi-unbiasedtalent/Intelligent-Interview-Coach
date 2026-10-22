import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 03B (REQ-OWN-02) Admin Plans UI: matrix and comparison, assignment preview and bulk assign, explanation, rollback, history and
// stale-revision handling. Server-resolved permissions only; the network layer is mocked.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/plans" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const f = {
  plans: vi.fn(), plan: vi.fn(), assignable: vi.fn(), createDraft: vi.fn(), updateDraft: vi.fn(), activate: vi.fn(), retire: vi.fn(),
  matrix: vi.fn(), compare: vi.fn(), explain: vi.fn(), subject: vi.fn(), history: vi.fn(), restore: vi.fn(), preview: vi.fn(), bulk: vi.fn(),
  setUserPlan: vi.fn(), setWorkspacePlan: vi.fn(),
};
vi.mock("@/lib/api/client", () => ({
  api: {
    admin: {
      plans: (...a: unknown[]) => f.plans(...a), plan: (...a: unknown[]) => f.plan(...a), assignablePlans: (...a: unknown[]) => f.assignable(...a),
      createPlanDraft: (...a: unknown[]) => f.createDraft(...a), updatePlanDraft: (...a: unknown[]) => f.updateDraft(...a),
      activatePlan: (...a: unknown[]) => f.activate(...a), retirePlan: (...a: unknown[]) => f.retire(...a),
      planMatrix: (...a: unknown[]) => f.matrix(...a), comparePlans: (...a: unknown[]) => f.compare(...a),
      explainPlanAccess: (...a: unknown[]) => f.explain(...a), planSubject: (...a: unknown[]) => f.subject(...a),
      planVersionAssignments: (...a: unknown[]) => f.history(...a), restorePlanAsDraft: (...a: unknown[]) => f.restore(...a),
      previewPlanAssignment: (...a: unknown[]) => f.preview(...a), bulkAssignPlan: (...a: unknown[]) => f.bulk(...a),
      setUserPlan: (...a: unknown[]) => f.setUserPlan(...a), setWorkspacePlan: (...a: unknown[]) => f.setWorkspacePlan(...a),
    },
  },
}));

import { PlanControl } from "@/components/admin/PlanControl";
import { PlanDetailView } from "@/components/admin/PlanDetailView";
import { parseIds } from "@/components/admin/PlanAssignPanel";
import { PlansView } from "@/components/admin/PlansView";

const KEYS = ["current_market_research", "standard_history", "standard_progress", "standard_model_profiles", "premium_preview"];
const BOUNDS = (k: string) => ({ kind: "boolean", min_limit: null, max_limit: null, premium_only: k === "premium_preview" });
const ROWS = [
  { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", enabled_entitlements: 5, total_entitlements: 5, subscribers: { users: 3, workspaces: 1 }, revision: "r2", family_revision: "famP", created_at: null, activated_at: "2026-10-01", retired_at: null },
  { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", enabled_entitlements: 4, total_entitlements: 5, subscribers: { users: 40, workspaces: 0 }, revision: "r1", family_revision: "famB", created_at: null, activated_at: "2026-10-01", retired_at: null },
];
const MATRIX = {
  entitlements: KEYS.map((k) => ({ code: k, label: `Label ${k}`, description: `Desc ${k}`, type: "boolean", bounds: BOUNDS(k) })),
  versions: [
    { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", revision: "r2", values: Object.fromEntries(KEYS.map((k) => [k, { enabled: true, limit: null }])) },
    { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", revision: "r1", values: Object.fromEntries(KEYS.map((k) => [k, { enabled: k !== "premium_preview", limit: null }])) },
  ],
};
const PREVIEW = {
  plan_code: "premium", target_version: 1, subject_type: "user", requested: 3, found: 3, missing: 0, unchanged: 1, would_change: 2,
  by_current_plan: { basic: 2, premium: 1, none: 0 },
  entitlement_effect: KEYS.map((k) => ({ code: k, label: `Label ${k}`, gain: k === "premium_preview" ? 2 : 0, lose: 0, limit_changed: 0 })),
  preview_revision: "prev-1",
};
const DETAIL = (over = {}) => ({
  id: 3, plan_code: "premium", version: 2, display_name: "Premium (preview)", status: "retired", editable: false, revision: "rev-3", family_revision: "fam-3",
  entitlements: KEYS.map((k) => ({ code: k, label: `Label ${k}`, description: `Desc ${k}`, type: "boolean", enabled: true, limit: null, bounds: BOUNDS(k) })),
  subscribers: { users: 1, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: "2026-10-05", ...over,
});

beforeEach(() => {
  mockPerms = ["platform.plans.read", "platform.plans.manage", "platform.subscriptions.manage"];
  f.plans.mockResolvedValue({ items: ROWS });
  f.plan.mockResolvedValue(DETAIL());
  f.assignable.mockResolvedValue([{ plan_code: "basic", version: 1, display_name: "Basic" }, { plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
  f.matrix.mockResolvedValue(MATRIX);
  f.compare.mockResolvedValue({
    left: { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", subscribers: { users: 40, workspaces: 0 } },
    right: { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", subscribers: { users: 3, workspaces: 1 } },
    rows: KEYS.map((k) => ({ code: k, label: `Label ${k}`, left: { enabled: k !== "premium_preview", limit: null }, right: { enabled: true, limit: null }, differs: k === "premium_preview" })),
    changed: 1, note: "Subscribers stay pinned to their version.",
  });
  f.preview.mockResolvedValue(PREVIEW);
  f.bulk.mockResolvedValue({ plan_code: "premium", version: 1, subject_type: "user", requested: 3, changed: 2, unchanged: 1 });
  f.history.mockResolvedValue({ plan_code: "premium", version: 2, total: 1, page: 1, page_size: 10, items: [{ subject_type: "user", subject_id: 9, status: "active", source: "admin", started_at: "2026-10-02T10:00:00Z", ended_at: null }] });
  f.restore.mockResolvedValue({ id: 8, plan_code: "premium", version: 3, copied_from: 2 });
  f.subject.mockResolvedValue({ subject_type: "user", subject_id: 7, current: null, history: [], revision: "subj-1" });
  f.explain.mockResolvedValue({
    subject_type: "user", subject_id: 7, plan_code: "basic", plan_version: 1, plan_version_status: "active", source: "subscription",
    items: KEYS.map((k) => ({ code: k, label: `Label ${k}`, allowed: k !== "premium_preview", limit: null, unlimited: k !== "premium_preview",
      reason: k === "premium_preview" ? "disabled_by_plan_version" : "granted_by_plan_version" })),
    layers: [
      { layer: "authorization", evaluated_here: false, note: "Decided per request by ownership and permissions." },
      { layer: "capability", evaluated_here: false, note: "Decided by the deployment." },
      { layer: "entitlement", evaluated_here: true, note: "What the plan grants." },
      { layer: "billing_state", evaluated_here: false, note: "Billing never grants access." },
    ],
    note: "Plan data only.",
  });
  for (const m of [f.createDraft, f.updateDraft, f.activate, f.retire, f.setUserPlan, f.setWorkspacePlan]) m.mockResolvedValue({ version: 2 });
});
afterEach(() => vi.clearAllMocks());

describe("parseIds", () => {
  it("accepts comma or space separated whole numbers, de-duplicates, and refuses anything else", () => {
    expect(parseIds("1, 2 3,3")).toEqual([1, 2, 3]);
    expect(parseIds("")).toBeNull();
    expect(parseIds("1, x")).toBeNull();
    expect(parseIds("0")).toBeNull();
    expect(parseIds("-4")).toBeNull();
    expect(parseIds("1.5")).toBeNull();
    expect(parseIds(Array.from({ length: 101 }, (_, i) => i + 1).join(","))).toBeNull();
    expect(parseIds(Array.from({ length: 100 }, (_, i) => i + 1).join(","))).toHaveLength(100);
  });
});

describe("Entitlement matrix and comparison", () => {
  it("shows every entitlement against every version, marks the Premium-only key, and compares two versions", async () => {
    const user = userEvent.setup();
    render(<PlansView />);
    const table = await screen.findByRole("table", { name: "Registered entitlements by plan version" });
    expect(within(table).getAllByRole("row")).toHaveLength(1 + KEYS.length);
    expect(within(table).getByText(/Premium only: never enabled in Basic/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Compare this version"), "1");
    await user.selectOptions(screen.getByLabelText("with this version"), "2");
    await user.click(screen.getByRole("button", { name: "Compare versions" }));
    await waitFor(() => expect(f.compare).toHaveBeenCalledWith(1, 2));
    expect(await screen.findByText("1 of 5 entitlements differ.")).toBeInTheDocument();
    expect(screen.getByText("Differs")).toBeInTheDocument();
    expect(screen.getByText(/Subscribers stay pinned/)).toBeInTheDocument();
  });

  it("compare stays disabled until both versions are chosen and shows a failure as an alert", async () => {
    const user = userEvent.setup();
    f.compare.mockRejectedValue(new Error("Plan version not found."));
    render(<PlansView />);
    await screen.findByRole("table", { name: "Registered entitlements by plan version" });
    expect(screen.getByRole("button", { name: "Compare versions" })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Compare this version"), "1");
    await user.selectOptions(screen.getByLabelText("with this version"), "2");
    await user.click(screen.getByRole("button", { name: "Compare versions" }));
    expect(await screen.findByText("Plan version not found.")).toBeInTheDocument();
  });
});

describe("Assign plans (preview then bulk)", () => {
  async function fill(user: ReturnType<typeof userEvent.setup>, ids = "7, 8, 9") {
    await screen.findByRole("option", { name: "Premium (preview) (version 1)" });
    await user.selectOptions(screen.getByLabelText("Plan to assign"), "premium");
    await user.type(screen.getByLabelText(/Ids \(comma or space separated/), ids);
  }

  it("previews counts only, then assigns with the preview revision after confirmation", async () => {
    const user = userEvent.setup();
    render(<PlansView />);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    await waitFor(() => expect(f.preview).toHaveBeenCalledWith("premium", "user", [7, 8, 9]));
    expect(await screen.findByText(/Requested 3, found 3, not found 0\. 2 would change, 1 already on this version\./)).toBeInTheDocument();
    expect(screen.getByText(/Basic 2, Premium 1, no active subscription 0/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Assign 2 accounts" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(within(dialog).getByText(/change together or none do/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Assign" }));
    await waitFor(() => expect(f.bulk).toHaveBeenCalledWith("premium", "user", [7, 8, 9], "prev-1"));
    expect(await screen.findByText(/Assigned: 2 changed, 1 already on version 1/)).toBeInTheDocument();
  });

  it("a stale preview is refused inside the dialog and nothing is claimed as assigned", async () => {
    const user = userEvent.setup();
    f.bulk.mockRejectedValue(new Error("The plan changed since it was loaded. Reload and review the current state before trying again."));
    render(<PlansView />);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    await user.click(await screen.findByRole("button", { name: "Assign 2 accounts" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Assign" }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/changed since it was loaded/);
    expect(f.bulk).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Assigned:/)).not.toBeInTheDocument();
  });

  it("missing subjects block the assignment and invalid input never reaches the server", async () => {
    const user = userEvent.setup();
    f.preview.mockResolvedValue({ ...PREVIEW, found: 2, missing: 1 });
    render(<PlansView />);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    expect(await screen.findByText(/Some ids do not exist/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Assign \d+ accounts$/ })).toBeDisabled();
    await user.clear(screen.getByLabelText(/Ids \(comma or space separated/));
    await user.type(screen.getByLabelText(/Ids \(comma or space separated/), "abc");
    f.preview.mockClear();
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/whole-number ids/);
    expect(f.preview).not.toHaveBeenCalled();
  });

  it("is absent without subscriptions.manage", async () => {
    mockPerms = ["platform.plans.read"];
    render(<PlansView />);
    await screen.findByRole("table", { name: "Registered entitlements by plan version" });
    expect(screen.queryByRole("heading", { name: "Assign plans" })).not.toBeInTheDocument();
    expect(f.assignable).not.toHaveBeenCalled();
  });
});

describe("Explain effective access", () => {
  it("shows allowed and refused entitlements with the reason, and the four separate layers", async () => {
    const user = userEvent.setup();
    render(<PlansView />);
    await user.selectOptions(await screen.findByLabelText("Explain access for"), "user");
    await user.type(screen.getByLabelText("Subject id"), "7");
    await user.click(screen.getByRole("button", { name: "Explain access" }));
    await waitFor(() => expect(f.explain).toHaveBeenCalledWith({ user_id: 7 }));
    expect(await screen.findByText("basic version 1 (active)")).toBeInTheDocument();
    expect(screen.getByText("The subject's plan version disables it.")).toBeInTheDocument();
    expect(screen.getAllByText("The subject's plan version enables it.")).toHaveLength(4);
    expect(screen.getByText("Refused")).toBeInTheDocument();
    const layers = within(screen.getByRole("heading", { name: "Four separate layers" }).parentElement!);
    for (const name of ["Authorization", "Capability", "Entitlement", "Billing state"]) expect(layers.getByText(name)).toBeInTheDocument();
    expect(screen.getByText(/Billing never grants access/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/@|\$|€|per month|invoice number/i);
  });

  it("asks for a workspace id with the workspace parameter and refuses a non-numeric id locally", async () => {
    const user = userEvent.setup();
    render(<PlansView />);
    await user.selectOptions(await screen.findByLabelText("Explain access for"), "workspace");
    await user.type(screen.getByLabelText("Subject id"), "12");
    await user.click(screen.getByRole("button", { name: "Explain access" }));
    await waitFor(() => expect(f.explain).toHaveBeenCalledWith({ workspace_id: 12 }));
    await user.clear(screen.getByLabelText("Subject id"));
    await user.type(screen.getByLabelText("Subject id"), "x1");
    f.explain.mockClear();
    await user.click(screen.getByRole("button", { name: "Explain access" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter one whole-number id.");
    expect(f.explain).not.toHaveBeenCalled();
  });
});

describe("Plan detail: rollback, history and revisions", () => {
  it("restores a retired version as a new draft with the family revision and shows its assignment history", async () => {
    const user = userEvent.setup();
    render(<PlanDetailView versionId={3} />);
    expect(await screen.findByRole("heading", { name: "Assignment history" })).toBeInTheDocument();
    expect(await screen.findByText("user 9")).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 1 \(1 total\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restore this version as a new draft" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Restore as draft" }));
    await waitFor(() => expect(f.restore).toHaveBeenCalledWith(3, "fam-3"));
    expect(await screen.findByText(/Draft version 3 created from version 2/)).toBeInTheDocument();
  });

  it("a draft has no rollback control and a stale save shows the server message without losing the edit", async () => {
    const user = userEvent.setup();
    f.plan.mockResolvedValue(DETAIL({ status: "draft", editable: true }));
    f.updateDraft.mockRejectedValue(new Error("The plan changed since it was loaded. Reload and review the current state before trying again."));
    render(<PlanDetailView versionId={3} />);
    const box = await screen.findByLabelText("Include Label standard_history");
    expect(screen.queryByRole("button", { name: /Restore this version/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Premium only: it cannot be enabled in the Basic plan\./)).toBeInTheDocument();
    await user.click(box);
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/changed since it was loaded/);
    expect(f.updateDraft).toHaveBeenCalledWith(3, { standard_history: { enabled: false, limit: null } }, "rev-3");
    expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled();      // the unsaved edit is still there
  });

  it("read-only operators see history but no restore control", async () => {
    mockPerms = ["platform.plans.read"];
    render(<PlanDetailView versionId={3} />);
    await screen.findByRole("heading", { name: "Assignment history" });
    expect(screen.queryByRole("button", { name: /Restore this version/ })).not.toBeInTheDocument();
  });
});

describe("Subject plan control revision handling", () => {
  it("a conflicting change is reported inside the dialog and the revision is reloaded", async () => {
    const user = userEvent.setup();
    f.setUserPlan.mockRejectedValue(new Error("The plan changed since it was loaded. Reload and review the current state before trying again."));
    render(<PlanControl plan={{ current: null, history: [] }} subject={{ kind: "user", id: 7 }} onChanged={() => {}} />);
    await screen.findByRole("option", { name: "Premium (preview) (version 1)" });
    await user.selectOptions(screen.getByLabelText("Change plan"), "premium");
    await user.click(screen.getByRole("button", { name: "Change plan" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Change plan" }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/changed since it was loaded/);
    await waitFor(() => expect(f.subject).toHaveBeenCalledTimes(2));            // initial load + reload after the conflict
  });
});

describe("Plans page copy", () => {
  it("keeps plans and money separate: no price, currency or provider wording on the plans page", async () => {
    render(<PlansView />);
    await screen.findByRole("table", { name: "Registered entitlements by plan version" });
    expect(document.body.textContent).not.toMatch(/\$|€|EUR|USD|per month|per year|stripe|checkout/i);
  });
});
