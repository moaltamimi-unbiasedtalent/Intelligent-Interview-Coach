import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";

// P10B-W10.13 Admin Security UI. APIs are mocked; real SQL semantics (append-only audit, two-person role changes, step-up) are proven by tests/test_security_w10_13.py.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/security" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { user_id: 7, platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
const m = {
  events: vi.fn(), audit: vi.fn(), alerts: vi.fn(), ack: vi.fn(), resolve: vi.fn(), incidents: vi.fn(), incident: vi.fn(), create: vi.fn(), status: vi.fn(),
  roleChanges: vi.fn(), approve: vi.fn(), reject: vi.fn(), stepUp: vi.fn(), exportAudit: vi.fn(),
};
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    securityEvents: (...a: unknown[]) => m.events(...a), auditPage: (...a: unknown[]) => m.audit(...a), alerts: (...a: unknown[]) => m.alerts(...a),
    acknowledgeAlert: (...a: unknown[]) => m.ack(...a), resolveAlert: (...a: unknown[]) => m.resolve(...a), incidents: (...a: unknown[]) => m.incidents(...a),
    incident: (...a: unknown[]) => m.incident(...a), createIncident: (...a: unknown[]) => m.create(...a), incidentStatus: (...a: unknown[]) => m.status(...a),
    updateIncident: vi.fn(), linkIncidentTicket: vi.fn(), roleChanges: (...a: unknown[]) => m.roleChanges(...a), approveRoleChange: (...a: unknown[]) => m.approve(...a),
    rejectRoleChange: (...a: unknown[]) => m.reject(...a), cancelRoleChange: vi.fn(), stepUp: (...a: unknown[]) => m.stepUp(...a), exportAudit: (...a: unknown[]) => m.exportAudit(...a),
  } },
}));

import { SecurityView } from "@/components/admin/SecurityView";

const EVENT = { id: 1, event_type: "account.login", category: "authentication", severity: "low", actor_user_id: 3, target_type: null, target_id: null, result: "failure", request_id: "req-1", created_at: "2026-10-06T10:00:00" };
const ALERT = (o: Record<string, unknown> = {}) => ({ public_id: "a1", category: "job_failed", severity: "medium", state: "active", source_type: "job", source_id: "j", title: "A background job failed terminally",
  occurrence_count: 2, first_seen_at: "x", last_seen_at: "y", acknowledged_at: null, resolved_at: null, revision: 3, ...o });
const INC = { public_id: "i1", title: "Provider latency", severity: "high", status: "open", affected_service: "agent", started_at: "x", resolved_at: null, owner_admin_user_id: null,
  affected_user_estimate: null, root_cause: null, remediation: null, created_at: "x", updated_at: "x", revision: 0 };
const ROLE = (o: Record<string, unknown> = {}) => ({ public_id: "r1", target_user_id: 9, before_role: "user", requested_role: "billing_admin", requester_user_id: 2, approver_user_id: null,
  status: "pending", reason: "covers billing", requested_at: "x", decided_at: null, applied_at: null, revision: 0, ...o });
const SEC_PERMS = ["platform.security.read", "platform.security.manage", "platform.incidents.manage", "platform.audit.read", "platform.audit.export"];

beforeEach(() => {
  mockPerms = SEC_PERMS;
  m.events.mockResolvedValue({ items: [EVENT], total: 1, page: 1, page_size: 25, anomalies: [{ rule: "authentication_failure_burst", actor_user_id: 3, count: 5, window_minutes: 15, threshold: 5, since: "x" }], advanced_anomaly_detection: false });
  m.audit.mockResolvedValue({ items: [{ id: 1, event_type: "admin.role_change.approved", result: "success", actor_user_id: 2, target_type: "role_change_request", target_id: "r1", request_id: "req-2", context: null, created_at: "x" }], total: 1, page: 1, page_size: 50 });
  m.alerts.mockResolvedValue({ items: [ALERT()], total: 1, page: 1, page_size: 25, categories: ["job_failed"], not_implemented: ["provider_outage", "error_rate"], delivery: "in_app_only" });
  m.incidents.mockResolvedValue({ items: [INC], total: 1, page: 1, page_size: 25, severities: ["low", "medium", "high", "critical"], statuses: [], services: ["agent", "platform"] });
  m.incident.mockResolvedValue({ ...INC, allowed_transitions: ["investigating", "resolved"], tickets: [{ public_id: "t1", status: "new", category: "technical", linked_at: "x" }], history: [{ id: 1, action: "created", prior_status: null, new_status: "open", actor_user_id: 2, request_id: "q", meta: null, created_at: "x" }] });
  m.roleChanges.mockResolvedValue({ items: [ROLE()], total: 1, page: 1, page_size: 25, assignable_roles: ["user"], viewer_user_id: 7 });
  for (const f of [m.ack, m.resolve, m.create, m.status, m.approve, m.reject, m.stepUp]) f.mockResolvedValue({});
});
afterEach(() => vi.clearAllMocks());

const tab = (name: string) => screen.getByRole("tab", { name });

describe("Admin Security", () => {
  it("shows the security tabs the caller is permitted, with the metadata-only notice and no candidate content", async () => {
    render(<SecurityView />);
    expect(await screen.findByText("authentication failure burst")).toBeInTheDocument();
    for (const t of ["Security events", "Audit", "Incidents", "Alerts"]) expect(tab(t)).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Role approvals" })).not.toBeInTheDocument();
    expect(screen.getByText(/never shows candidate content, email addresses, IP addresses or session tokens/)).toBeInTheDocument();
    expect(screen.getByText("Severity: low")).toBeInTheDocument();                          // severity is text, not colour alone
  });

  it("events filters re-query the server and pagination is server-side", async () => {
    const user = userEvent.setup();
    render(<SecurityView />);
    await screen.findByText("req-1");
    await user.selectOptions(screen.getByLabelText("Category"), "authorization");
    await waitFor(() => expect(m.events).toHaveBeenLastCalledWith(expect.objectContaining({ category: "authorization", page: 1, page_size: 25 })));
  });

  it("alerts: security.read cannot acknowledge or resolve; security.manage can, with a revision", async () => {
    const user = userEvent.setup();
    mockPerms = ["platform.security.read"];
    const { unmount } = render(<SecurityView />);
    await user.click(tab("Alerts"));
    await screen.findByText("A background job failed terminally");
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
    expect(screen.getByText(/provider outage, error rate/)).toBeInTheDocument();             // unsupported categories are disclosed, not faked
    unmount();
    mockPerms = SEC_PERMS;
    render(<SecurityView />);
    await user.click(tab("Alerts"));
    await user.click(await screen.findByRole("button", { name: "Acknowledge" }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Acknowledge" }));
    await waitFor(() => expect(m.ack).toHaveBeenCalledWith("a1", 3));
  });

  it("incidents: create, status transition, history, linked ticket identifiers, a metadata-only warning and NO delete control", async () => {
    const user = userEvent.setup();
    render(<SecurityView />);
    await user.click(tab("Incidents"));
    await screen.findByText("Provider latency");
    expect(screen.getAllByText(/Do not paste candidate content, credentials or secrets/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Create incident" }));
    const dlg = screen.getByRole("alertdialog");
    await user.type(within(dlg).getByLabelText("Title"), "New incident");
    await user.click(within(dlg).getByRole("button", { name: "Create" }));
    await waitFor(() => expect(m.create).toHaveBeenCalledWith({ title: "New incident", severity: "medium", affected_service: "agent" }));
    await user.click(screen.getAllByRole("button", { name: "Open" })[0]);
    expect(await screen.findByText("t1")).toBeInTheDocument();                                 // identifier, never the ticket body
    await user.click(screen.getByRole("button", { name: "Move to investigating" }));
    await waitFor(() => expect(m.status).toHaveBeenCalledWith("i1", "investigating", 0));
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("incident mutations are hidden without incidents.manage", async () => {
    const user = userEvent.setup();
    mockPerms = ["platform.security.read"];
    render(<SecurityView />);
    await user.click(tab("Incidents"));
    await screen.findByText("Provider latency");
    expect(screen.queryByRole("button", { name: "Create incident" })).not.toBeInTheDocument();
  });

  it("a stale incident revision surfaces the conflict message", async () => {
    const user = userEvent.setup();
    m.status.mockRejectedValue(new ApiError({ kind: "http", status: 409, code: "conflict", message: "This incident changed. Reload and try again." } as any));
    render(<SecurityView />);
    await user.click(tab("Incidents"));
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[0]);
    await user.click(await screen.findByRole("button", { name: "Move to resolved" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This incident changed");
  });

  it("audit export needs audit.export, a reason and confirmation", async () => {
    const user = userEvent.setup();
    mockPerms = ["platform.audit.read"];
    const { unmount } = render(<SecurityView />);
    await screen.findByText("req-2");
    expect(screen.queryByRole("button", { name: "Export audit events" })).not.toBeInTheDocument();
    unmount();
    mockPerms = SEC_PERMS;
    m.exportAudit.mockResolvedValue({ content: "id\n", filename: "audit-export.csv", count: 0 });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    render(<SecurityView />);
    await user.click(tab("Audit"));
    await user.click(await screen.findByRole("button", { name: "Export audit events" }));
    const dlg = screen.getByRole("alertdialog");
    await user.click(within(dlg).getByRole("button", { name: "Export" }));
    expect(await within(dlg).findByText("A reason is required.")).toBeInTheDocument();
    expect(m.exportAudit).not.toHaveBeenCalled();
    await user.type(within(dlg).getByLabelText(/Reason/), "access review Q4");
    await user.click(within(dlg).getByRole("button", { name: "Export" }));
    await waitFor(() => expect(m.exportAudit).toHaveBeenCalledWith(expect.objectContaining({ format: "csv", period: "7d", reason: "access review Q4" })));
  });

  it("role approvals: the requester cannot approve their own request", async () => {
    mockPerms = ["platform.users.role.assign"];
    m.roleChanges.mockResolvedValue({ items: [ROLE({ requester_user_id: 7 })], total: 1, page: 1, page_size: 25, assignable_roles: [], viewer_user_id: 7 });
    render(<SecurityView />);
    expect(await screen.findByText(/You requested this; a different Admin must approve/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("role approvals: a different Admin approves; step-up is requested when the server says so, then the action is retried", async () => {
    const user = userEvent.setup();
    mockPerms = ["platform.users.role.assign"];
    m.approve.mockRejectedValueOnce(new ApiError({ kind: "http", status: 403, code: "step_up_required", message: "Confirm your password to continue." } as any)).mockResolvedValue({ outcome: "applied" });
    render(<SecurityView />);
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    const dlg = await screen.findByTestId("step-up-dialog");
    expect(within(dlg).getByText(/Confirm your password/)).toBeInTheDocument();
    const pw = within(dlg).getByLabelText("Current password");
    expect(pw).toHaveAttribute("type", "password");
    expect(pw).toHaveAttribute("autocomplete", "current-password");
    expect(within(dlg).getByRole("button", { name: "Cancel" })).toHaveFocus();            // safe default
    await user.type(pw, "my-current-password");
    await user.click(within(dlg).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(m.stepUp).toHaveBeenCalledWith("my-current-password"));
    await waitFor(() => expect(m.approve).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Role change approved and applied.")).toBeInTheDocument();
  });

  it("the step-up dialog never persists the password and states it is not MFA", () => {
    const src = readFileSync(join(__dirname, "../components/admin/StepUp.tsx"), "utf8");
    expect(src).not.toMatch(/localStorage|sessionStorage|document\.cookie|console\./);
    expect(src).toMatch(/not MFA/);
    const view = readFileSync(join(__dirname, "../components/admin/SecurityView.tsx"), "utf8");
    expect(view).not.toMatch(/platform_role\s*===|role\s*===\s*"platform_admin"|localStorage|sessionStorage/);   // permissions, never role names
  });

  it("a caller with no security permission gets access denied", () => {
    mockPerms = [];
    render(<SecurityView />);
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
