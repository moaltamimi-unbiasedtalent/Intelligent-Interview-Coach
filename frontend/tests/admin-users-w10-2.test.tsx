import { readFileSync, readdirSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.2 Admin users / sessions / workspaces UI. Permissions come from the server; async content is
// always awaited with findBy*/waitFor (never a synchronous query right after a static container).

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/users" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const users = vi.fn();
const detail = vi.fn();
const setStatus = vi.fn();
const setRole = vi.fn();
const revoke = vi.fn();
const workspaces = vi.fn();
const wsDetail = vi.fn();
const addMember = vi.fn();
const removeMember = vi.fn();
const setMemberRole = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    users: (...a: unknown[]) => users(...a), userDetail: (...a: unknown[]) => detail(...a),
    setStatus: (...a: unknown[]) => setStatus(...a), requestRoleChange: (...a: unknown[]) => setRole(...a),
    revokeSessions: (...a: unknown[]) => revoke(...a), workspaces: (...a: unknown[]) => workspaces(...a),
    workspaceDetail: (...a: unknown[]) => wsDetail(...a), addWorkspaceMember: (...a: unknown[]) => addMember(...a),
    removeWorkspaceMember: (...a: unknown[]) => removeMember(...a), setWorkspaceMemberRole: (...a: unknown[]) => setMemberRole(...a),
  } },
}));

import { UserDetailView } from "@/components/admin/UserDetailView";
import { UsersView } from "@/components/admin/UsersView";
import { WorkspaceDetailView } from "@/components/admin/WorkspaceDetailView";
import { WorkspacesView } from "@/components/admin/WorkspacesView";

const ALL = ["platform.users.read", "platform.users.manage", "platform.users.role.assign", "platform.users.sessions.revoke",
  "platform.workspaces.read", "platform.workspaces.manage"];

const U = (id: number, over = {}) => ({ user_id: id, email: `u${id}@example.com`, display_name: null, status: "active",
  platform_role: "user", tier: "basic", onboarding_completed: true, interface_locale: "en", email_verified: false,
  created_at: "2026-10-01T00:00:00", updated_at: "2026-10-01T00:00:00", workspace_count: 1, active_session_count: 2, ...over });

const DETAIL = (over = {}) => ({
  account: U(7), access: { platform_role: "user", capabilities: [], assignable_roles: ["user", "platform_admin", "support_operator"], is_self: false },
  sessions: { active_count: 2, recent: [{ created_at: "2026-10-01T10:00:00", last_used_at: "2026-10-02T10:00:00", expires_at: "2026-10-30T10:00:00" }] },
  workspaces: [{ workspace_id: 3, name: "Team Alpha", workspace_status: "active", role: "workspace_member", membership_status: "active", joined_at: null }],
  audit: [{ event_type: "admin.account_status_change", result: "success", actor_user_id: 1, request_id: "req-1", created_at: null, context: { before: "active", after: "deactivated" } }],
  ...over,
});

const WS = { workspace: { id: 3, name: "Team Alpha", status: "active", owner_user_id: 1, owner_email: "o@example.com", member_count: 2, created_at: null },
  members: [{ user_id: 1, email: "o@example.com", account_status: "active", role: "workspace_owner", membership_status: "active", joined_at: null },
            { user_id: 2, email: "m@example.com", account_status: "active", role: "workspace_member", membership_status: "active", joined_at: null }],
  active_share_count: 4, active_owner_count: 1, workspace_roles: ["workspace_owner", "workspace_member"] };

beforeEach(() => {
  mockPerms = ALL;
  users.mockResolvedValue({ items: [U(1), U(2)], total: 60, page: 1, page_size: 25 });
  detail.mockResolvedValue(DETAIL());
  workspaces.mockResolvedValue({ items: [WS.workspace], total: 1, page: 1, page_size: 25 });
  wsDetail.mockResolvedValue(WS);
  for (const m of [setStatus, setRole, addMember, removeMember, setMemberRole]) m.mockResolvedValue({ sessions_revoked: 2 });
  revoke.mockResolvedValue({ user_id: 7, sessions_revoked: 2 });
});
afterEach(() => vi.clearAllMocks());

describe("Users list", () => {
  it("renders accounts from the server with session and workspace counts and links to detail", async () => {
    render(<UsersView />);
    const link = await screen.findByRole("link", { name: "u1@example.com" });
    expect(link).toHaveAttribute("href", "/admin/users/1");
    expect(screen.getByText("Page 1 of 3 (60 total)")).toBeInTheDocument();
  });

  it("searches and filters server-side, resetting to page 1", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await screen.findByRole("link", { name: "u1@example.com" });
    await user.type(screen.getByLabelText("Email or account id"), "jane");
    await user.selectOptions(screen.getByLabelText("Status"), "deactivated");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(users).toHaveBeenLastCalledWith(expect.objectContaining({ q: "jane", status: "deactivated", page: 1 })));
  });

  it("paginates server-side", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await screen.findByRole("link", { name: "u1@example.com" });
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(users).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("shows an empty state and fetches nothing without users.read", async () => {
    users.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    render(<UsersView />);
    expect(await screen.findByText("No accounts match.")).toBeInTheDocument();
    mockPerms = ["platform.workspaces.read"];
    users.mockClear();
    render(<UsersView />);
    expect((await screen.findAllByText(/does not include access/))[0]).toBeInTheDocument();
    expect(users).not.toHaveBeenCalled();
  });
});

describe("User detail", () => {
  it("shows account, access, sessions, workspaces and admin audit - and no private-content sections", async () => {
    render(<UserDetailView userId={7} />);
    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
    for (const h of ["Access", "Sessions", "Workspaces", "Admin actions on this account"]) {
      expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
    }
    expect(screen.getByText("req-1")).toBeInTheDocument();
    expect(screen.getByText("active to deactivated")).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/resume|curriculum vitae|interview answer|memories|conversation|token/i);
    // session display carries only the three stored timestamps
    const sessionTable = screen.getByRole("table", { name: "Active sessions" });
    expect(within(sessionTable).getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["created_at", "last_used_at", "expires_at"]);
  });

  it("hides every write control for a read-only role", async () => {
    mockPerms = ["platform.users.read"];
    render(<UserDetailView userId={7} />);
    await screen.findByRole("heading", { name: "Account" });
    for (const name of [/Deactivate account/, /Reactivate account/, /Change role/, /Force logout/]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("deactivation dialog defaults focus to Cancel, confirms once and reports sessions ended", async () => {
    const user = userEvent.setup();
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: "Deactivate account" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.type(within(dialog).getByLabelText(/Reason/), "abuse report");
    await user.click(within(dialog).getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(setStatus).toHaveBeenCalledWith(7, "deactivated", "abuse report"));
    expect(setStatus).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/2 session\(s\) ended/)).toBeInTheDocument();
  });

  it("a failed write shows the error inside the dialog and is not retried", async () => {
    const user = userEvent.setup();
    setStatus.mockRejectedValue(new Error("This would leave no active platform administrator."));
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: "Deactivate account" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Deactivate" }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/no active platform administrator/);
    expect(setStatus).toHaveBeenCalledTimes(1);
  });

  it("a self-view cannot start a deactivation", async () => {
    detail.mockResolvedValue(DETAIL({ access: { platform_role: "platform_admin", capabilities: ["platform.overview.read"], assignable_roles: ["user", "platform_admin"], is_self: true } }));
    render(<UserDetailView userId={7} />);
    expect(await screen.findByRole("button", { name: "Deactivate account" })).toBeDisabled();
    expect(screen.getByText("You cannot deactivate your own account.")).toBeInTheDocument();
  });

  it("role selector offers only the server-provided presets and warns about administrator roles", async () => {
    const user = userEvent.setup();
    render(<UserDetailView userId={7} />);
    const select = await screen.findByLabelText("Role preset");
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["user", "platform_admin", "support_operator"]);
    await user.selectOptions(select, "platform_admin");
    await user.click(screen.getByRole("button", { name: "Request role change" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/Granting an administrator role/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Reason/), "covers on-call");
    await user.click(within(dialog).getByRole("button", { name: "Request role change" }));
    await waitFor(() => expect(setRole).toHaveBeenCalledWith(7, "platform_admin", "covers on-call"));
    expect(await screen.findByText(/a different Admin must approve it/)).toBeInTheDocument();
  });

  it("force logout confirms, then reports the truthful count", async () => {
    const user = userEvent.setup();
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: /Force logout/ }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Revoke sessions" }));
    await waitFor(() => expect(revoke).toHaveBeenCalledWith(7, undefined));
    expect(await screen.findByText("2 session(s) revoked.")).toBeInTheDocument();
  });

  it("an inactive account offers reactivation and says old sessions are not restored", async () => {
    const user = userEvent.setup();
    detail.mockResolvedValue(DETAIL({ account: U(7, { status: "deactivated", active_session_count: 0 }) }));
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: "Reactivate account" }));
    expect(within(screen.getByRole("alertdialog")).getByText(/Old sessions are not restored/)).toBeInTheDocument();
  });
});

describe("Workspaces", () => {
  it("lists workspaces and links to detail", async () => {
    render(<WorkspacesView />);
    expect(await screen.findByRole("link", { name: "Team Alpha" })).toHaveAttribute("href", "/admin/workspaces/3");
  });

  it("detail shows members, share count only, and manages membership with confirmation", async () => {
    const user = userEvent.setup();
    render(<WorkspaceDetailView workspaceId={3} />);
    expect(await screen.findByRole("heading", { name: "Members" })).toBeInTheDocument();
    expect(screen.getByText("Shared items are never listed here; only their count.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Existing account id"), "9");
    await user.click(screen.getByRole("button", { name: "Add member" }));
    await waitFor(() => expect(addMember).toHaveBeenCalledWith(3, 9, "workspace_member"));
    await user.click(screen.getByRole("button", { name: "Remove: m@example.com" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Remove member" }));
    await waitFor(() => expect(removeMember).toHaveBeenCalledWith(3, 2));
  });

  it("read-only workspace permission shows no membership controls", async () => {
    mockPerms = ["platform.workspaces.read"];
    render(<WorkspaceDetailView workspaceId={3} />);
    await screen.findByRole("heading", { name: "Members" });
    expect(screen.queryByRole("button", { name: "Add member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove:/ })).not.toBeInTheDocument();
    expect(screen.getByText(/can view membership but not change it/)).toBeInTheDocument();
  });
});

describe("authorisation is by permission, not by role name", () => {
  it("admin components contain no role-name checks and no browser storage", () => {
    for (const f of readdirSync("components/admin").filter((n) => n.endsWith(".tsx"))) {
      const src = readFileSync(`components/admin/${f}`, "utf8");
      expect(src, f).not.toMatch(/platform_role\s*===|===\s*"platform_admin"|localStorage|sessionStorage/);
      expect(src, f).not.toContain('from "next/link"');
    }
  });
});
