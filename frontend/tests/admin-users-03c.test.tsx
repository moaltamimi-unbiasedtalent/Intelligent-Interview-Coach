import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 03C Admin Users completion: sort/filter, complete detail, strict actions (reason + account revision), protection hints, no private content.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/users" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const users = vi.fn();
const detail = vi.fn();
const userAction = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    users: (...a: unknown[]) => users(...a), userDetail: (...a: unknown[]) => detail(...a), userAction: (...a: unknown[]) => userAction(...a),
    assignablePlans: () => Promise.resolve([{ plan_code: "premium", version: 1, display_name: "Premium (preview)" }]),
    requestRoleChange: vi.fn(),
  } },
}));

import { UserDetailView } from "@/components/admin/UserDetailView";
import { UsersView } from "@/components/admin/UsersView";

const ALL = ["platform.users.read", "platform.users.manage", "platform.users.role.assign", "platform.users.sessions.revoke", "platform.subscriptions.manage",
  "platform.privacy.execute", "platform.privacy.read", "platform.support.read"];
const REV = "0123456789abcdef";

const U = (id: number, over = {}) => ({ user_id: id, email: `u${id}@example.com`, display_name: null, status: "active", platform_role: "user", tier: "basic",
  onboarding_completed: true, interface_locale: "en", email_verified: false, created_at: "2026-10-01T00:00:00", updated_at: "2026-10-01T00:00:00",
  workspace_count: 1, active_session_count: 2, last_activity: "7d", ...over });

const DETAIL = (over = {}) => ({
  revision: REV, account: U(7), access: { platform_role: "user", capabilities: [], assignable_roles: ["user", "support_operator"], is_self: false },
  sessions: { active_count: 2, recent: [] }, workspaces: [], audit: [],
  plan: { current: { plan_code: "basic", version: 1, display_name: "Basic", status: "active", source: "system_default", started_at: "2026-10-01", ended_at: null }, history: [] },
  auth: { methods: [{ method: "password", email_verified: false, linked_at: null }, { method: "google", email_verified: true, linked_at: null }], local_sign_in: true, email_verified: false, pending_verification_links: 1 },
  activity: { last_active: "7d" },
  cases: { support_open: 2, support_total: 3, privacy_open: 1, privacy_total: 1, pending_role_change: false, open_deletion_request_id: null, open_deletion_status: null },
  membership: { active: 1, total: 2, owner_of_active: 1 },
  ...over,
});

beforeEach(() => {
  mockPerms = ALL;
  users.mockResolvedValue({ items: [U(1), U(2)], total: 2, page: 1, page_size: 25 });
  detail.mockResolvedValue(DETAIL());
  userAction.mockResolvedValue({ user_id: 7, action: "x", changed: true, links_expired: 1, mail_accepted: true, sessions_revoked: 0, revision: "fedcba9876543210" });
});
afterEach(() => vi.clearAllMocks());

describe("Users list: sort, filters and activity", () => {
  it("sends sort, direction and the new filters to the server and shows the activity bucket", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await screen.findByRole("link", { name: "u1@example.com" });
    expect(screen.getAllByText("7d").length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Sort by"), "email");
    await user.selectOptions(screen.getByLabelText("Order"), "asc");
    await user.selectOptions(screen.getByLabelText("Last active"), "never");
    await user.selectOptions(screen.getByLabelText("Sign-in method"), "password");
    await user.selectOptions(screen.getByLabelText("Open case"), "support");
    await user.selectOptions(screen.getByLabelText("Workspace member"), "true");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(users).toHaveBeenLastCalledWith(expect.objectContaining({
      sort: "email", direction: "asc", last_active: "never", auth_method: "password", open_case: "support", has_workspace: "true", page: 1 })));
  });
});

describe("User detail: complete, content-free", () => {
  it("shows sign-in methods, case counts, membership summary and activity bucket without any private content or secret", async () => {
    render(<UserDetailView userId={7} />);
    await screen.findByRole("heading", { name: "Sign-in and verification" });
    expect(screen.getByText("Email and password, Google sign-in")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();           // support open / total
    expect(screen.getByText("Within 7 days")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cases and membership" })).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/resume|curriculum vitae|interview answer|memories|conversation|token|password hash/i);
  });

  it("hides every new write control for a read-only role", async () => {
    mockPerms = ["platform.users.read"];
    render(<UserDetailView userId={7} />);
    await screen.findByRole("heading", { name: "Sign-in and verification" });
    for (const name of [/Resend verification/, /Expire verification/, /Record deletion request/, /Change plan/, /Force logout/]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("resend verification needs a reason, sends the revision and reports the truthful outcome", async () => {
    const user = userEvent.setup();
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: "Resend verification email" }));
    const dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Resend" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("A reason is required.");
    expect(userAction).not.toHaveBeenCalled();
    await user.type(within(dialog).getByLabelText(/Reason/), "user lost the email");
    await user.click(within(dialog).getByRole("button", { name: "Resend" }));
    await waitFor(() => expect(userAction).toHaveBeenCalledWith(7, "resend-verification", { expected_revision: REV, reason: "user lost the email" }));
    expect(await screen.findByText(/Verification email submitted/)).toBeInTheDocument();
  });

  it("expire verification and plan change use the strict action with reason and revision", async () => {
    const user = userEvent.setup();
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: "Expire verification links" }));
    await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "suspected misuse");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Expire links" }));
    await waitFor(() => expect(userAction).toHaveBeenCalledWith(7, "expire-verification", { expected_revision: REV, reason: "suspected misuse" }));
    await user.selectOptions(await screen.findByLabelText("Change plan"), "premium");
    await user.click(screen.getByRole("button", { name: "Change plan" }));
    await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "pilot upgrade");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Change plan" }));
    await waitFor(() => expect(userAction).toHaveBeenCalledWith(7, "assign-plan", { expected_revision: REV, reason: "pilot upgrade", plan_code: "premium" }));
  });

  it("records a deletion request without deleting anything and disables a second one", async () => {
    const user = userEvent.setup();
    render(<UserDetailView userId={7} />);
    expect(await screen.findByText(/Nothing is deleted here/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Record deletion request" }));
    await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "asked by letter");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Record request" }));
    await waitFor(() => expect(userAction).toHaveBeenCalledWith(7, "request-deletion", { expected_revision: REV, reason: "asked by letter" }));
  });

  it("a stale-revision refusal is shown inside the dialog and is not retried", async () => {
    const user = userEvent.setup();
    userAction.mockRejectedValue(new Error("This account changed since you loaded it. Reload and review before acting."));
    render(<UserDetailView userId={7} />);
    await user.click(await screen.findByRole("button", { name: "Deactivate account" }));
    await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "abuse report");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Deactivate" }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/changed since you loaded it/);
    expect(userAction).toHaveBeenCalledTimes(1);
  });

  it("a self-view disables every action the server refuses for your own account", async () => {
    detail.mockResolvedValue(DETAIL({ access: { platform_role: "platform_admin", capabilities: ["platform.users.read"], assignable_roles: ["user"], is_self: true } }));
    render(<UserDetailView userId={7} />);
    await screen.findByRole("heading", { name: "Sign-in and verification" });
    for (const name of ["Deactivate account", /Force logout/, "Resend verification email", "Expire verification links", "Record deletion request"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    expect(screen.getByText("You cannot change your own plan.")).toBeInTheDocument();
  });
});
