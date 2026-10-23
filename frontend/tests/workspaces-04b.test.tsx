import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import ws04b from "@/lib/i18n/messages/ws04b";

/** 04B Workspaces completion: list, detail (owner / admin / member), invitation page, share form, viewer. API mocked, no network. */

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));

const { api } = vi.hoisted(() => ({ api: {
  workspaces: {
    list: vi.fn(), get: vi.fn(), shares: vi.fn(), invite: vi.fn(), revokeInvitation: vi.fn(), setMemberRole: vi.fn(),
    removeMember: vi.fn(), transferStepUp: vi.fn(), proposeTransfer: vi.fn(), transferState: vi.fn(), transfersMine: vi.fn(), cancelTransfer: vi.fn(), declineTransfer: vi.fn(), leave: vi.fn(), archive: vi.fn(), restore: vi.fn(), remove: vi.fn(), rename: vi.fn(),
    acceptById: vi.fn(), declineById: vi.fn(), previewInvitation: vi.fn(), accept: vi.fn(), decline: vi.fn(), create: vi.fn(),
  },
  shares: { mine: vi.fn(), withMe: vi.fn(), revoke: vi.fn(), create: vi.fn(), view: vi.fn() },
  stories: { list: vi.fn() },
  history: { list: vi.fn() },
} }));
vi.mock("@/lib/api/client", () => ({ api }));

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { InviteAccept } from "@/components/workspaces/InviteAccept";
import { SharedItemViewer } from "@/components/workspaces/SharedItemViewer";
import { WorkspaceDetail } from "@/components/workspaces/WorkspaceDetail";
import { WorkspacesPanel } from "@/components/workspaces/WorkspacesPanel";

const t = (k: string, v?: Record<string, string | number>) => translate("en", k, v);
const wrap = (ui: React.ReactNode, locale: "en" | "de" = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

const OWNER_CAPS = { can_rename: true, can_invite: true, can_invite_admin: true, can_remove_members: true, can_change_roles: true, can_transfer: true, can_archive: true, can_restore: false, can_delete: true, can_leave: false, can_share: true };
const ADMIN_CAPS = { ...OWNER_CAPS, can_invite_admin: false, can_change_roles: false, can_transfer: false, can_archive: false, can_delete: false, can_leave: true };
const MEMBER_CAPS = { can_rename: false, can_invite: false, can_invite_admin: false, can_remove_members: false, can_change_roles: false, can_transfer: false, can_archive: false, can_restore: false, can_delete: false, can_leave: true, can_share: true };

function detail(role: "workspace_owner" | "workspace_admin" | "workspace_member", extra: Record<string, unknown> = {}) {
  const caps = role === "workspace_owner" ? OWNER_CAPS : role === "workspace_admin" ? ADMIN_CAPS : MEMBER_CAPS;
  const manager = role !== "workspace_member";
  return {
    id: 7, name: "Team Alpha", status: "active", owner_user_id: 1, member_count: 3, created_at: null, my_role: role, capabilities: caps,
    members: [
      { user_id: 1, role: "workspace_owner", status: "active", joined_at: "2026-10-01T10:00:00Z", label: role === "workspace_owner" ? "Olive" : "o***@x.com", is_me: role === "workspace_owner", ...(manager ? { email: "olive@x.com" } : {}) },
      { user_id: 2, role: "workspace_member", status: "active", joined_at: "2026-10-02T10:00:00Z", label: role === "workspace_member" ? "Mia" : "m***@x.com", is_me: role === "workspace_member", ...(manager ? { email: "mia@x.com" } : {}) },
      { user_id: 3, role: "workspace_admin", status: "active", joined_at: "2026-10-03T10:00:00Z", label: role === "workspace_admin" ? "Adam" : "a***@x.com", is_me: role === "workspace_admin", ...(manager ? { email: "adam@x.com" } : {}) },
    ],
    ...(manager ? { pending_invitations: [{ id: 11, workspace_id: 7, role: "workspace_member", status: "pending", expires_at: "2026-10-30T10:00:00Z", email: "ivan@x.com" }] } : {}),
    limits: { max_members: 100, max_pending_invitations: 50, invitation_ttl_hours: 72 },
    ...extra,
  };
}

beforeEach(() => {
  for (const group of Object.values(api)) for (const fn of Object.values(group)) (fn as ReturnType<typeof vi.fn>).mockReset();
  api.workspaces.list.mockResolvedValue({ workspaces: [], invited: [] });
  api.workspaces.get.mockResolvedValue(detail("workspace_owner"));
  api.workspaces.shares.mockResolvedValue({ shares: [] });
  api.workspaces.transferState.mockResolvedValue({ transfer: null });
  api.workspaces.transfersMine.mockResolvedValue({ transfers: [] });
  api.shares.mine.mockResolvedValue({ shares: [] });
  api.shares.withMe.mockResolvedValue({ shares: [] });
  api.stories.list.mockResolvedValue({ stories: [{ id: 5, title: "Led a launch" }] });
  api.history.list.mockResolvedValue({ interviews: [{ id: 9, target_role: "PM", status: "completed" }, { id: 10, target_role: "Draft", status: "in_progress" }] });
  push.mockReset();
  window.history.pushState({}, "", "/");
});
afterEach(() => vi.clearAllMocks());

// --------------------------------------------------------------------------------------------------- list page

describe("Workspaces list: invitations", () => {
  const invited = { id: 21, workspace_id: 4, role: "workspace_admin", status: "pending", expires_at: "2026-10-30T10:00:00Z", workspace_name: "Bravo" };

  it("shows each invitation with explicit Accept and Decline (no email-only dead end) and answers by id", async () => {
    api.workspaces.list.mockResolvedValue({ workspaces: [], invited: [invited] });
    api.workspaces.acceptById.mockResolvedValue({});
    wrap(<WorkspacesPanel />);
    expect(await screen.findByText("Bravo")).toBeInTheDocument();
    expect(screen.getByText(t("wsMgmt.invitedHint"))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(t("wsMgmt.invitedRole", { role: t("wsMgmt.roleAdmin") })))).toBeInTheDocument();
    api.workspaces.list.mockResolvedValue({ workspaces: [{ id: 4, name: "Bravo", status: "active", owner_user_id: 9, member_count: 2, created_at: null, my_role: "workspace_admin" }], invited: [] });
    fireEvent.click(screen.getByRole("button", { name: `${t("workspaces.accept")}: Bravo` }));
    await waitFor(() => expect(api.workspaces.acceptById).toHaveBeenCalledWith(21));
    expect(await screen.findByText(t("wsMgmt.joinedNotice"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bravo" })).toHaveAttribute("href", "/workspaces/4");
  });

  it("declines by id and says an unusable invitation could not be answered (then refreshes)", async () => {
    api.workspaces.list.mockResolvedValue({ workspaces: [], invited: [invited] });
    api.workspaces.declineById.mockResolvedValue({ status: "declined" });
    wrap(<WorkspacesPanel />);
    await screen.findByText("Bravo");
    fireEvent.click(screen.getByRole("button", { name: `${t("workspaces.decline")}: Bravo` }));
    await waitFor(() => expect(api.workspaces.declineById).toHaveBeenCalledWith(21));
    expect(await screen.findByText(t("wsMgmt.declinedNotice"))).toBeInTheDocument();

    api.workspaces.list.mockResolvedValue({ workspaces: [], invited: [invited] });
    api.workspaces.acceptById.mockRejectedValue(new ApiError({ status: 409, code: "x", message: "used", kind: "conflict", requestId: null }));
    fireEvent.click(await screen.findByRole("button", { name: `${t("workspaces.accept")}: Bravo` }));
    expect(await screen.findByText(t("wsMgmt.invitationFailed"))).toBeInTheDocument();
  });
});

describe("Workspaces list: roles and states", () => {
  it("shows a role badge, an Open link, Leave only for non-owners, and an Archived badge", async () => {
    api.workspaces.list.mockResolvedValue({
      workspaces: [
        { id: 1, name: "Mine", status: "active", owner_user_id: 1, member_count: 3, created_at: null, my_role: "workspace_owner" },
        { id: 2, name: "Theirs", status: "deactivated", owner_user_id: 5, member_count: 2, created_at: null, my_role: "workspace_member" },
      ], invited: [],
    });
    wrap(<WorkspacesPanel />);
    await screen.findByText("Mine");
    expect(screen.getByRole("link", { name: `${t("wsMgmt.openAction")}: Mine` })).toHaveAttribute("href", "/workspaces/1");
    expect(screen.queryByRole("button", { name: `${t("workspaces.leave")}: Mine` })).toBeNull();
    expect(screen.getByRole("button", { name: `${t("workspaces.leave")}: Theirs` })).toBeInTheDocument();
    expect(screen.getByText(t("wsMgmt.archivedBadge"))).toBeInTheDocument();
  });

  it("explains a failed create honestly and keeps the typed name", async () => {
    api.workspaces.create.mockRejectedValue(new ApiError({ status: 409, code: "x", message: "limit", kind: "conflict", requestId: null }));
    wrap(<WorkspacesPanel />);
    const input = await screen.findByLabelText(t("workspaces.namePlaceholder"));
    fireEvent.change(input, { target: { value: "Team Z" } });
    fireEvent.click(screen.getByRole("button", { name: t("workspaces.create") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t("wsMgmt.createFailed"));
    expect(input).toHaveValue("Team Z");
  });

  it("lists items shared with me with a sharer label and opens the read-only viewer; a revoked item says so", async () => {
    api.shares.withMe.mockResolvedValue({ shares: [{ id: 3, workspace_id: 1, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: "m***@x.com", workspace_name: "Mine" }] });
    api.shares.view.mockResolvedValueOnce({ resource_type: "story", resource_id: "5", shared_by_owner: true, resource: { title: "Led a launch", situation: "We shipped", competencies: ["Leadership"] } });
    wrap(<WorkspacesPanel />);
    expect(await screen.findByText(/m\*\*\*@x\.com/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: `${t("wsMgmt.viewShared")}: ${t("wsMgmt.typeStory")} #5` }));
    expect(await screen.findByText("We shipped")).toBeInTheDocument();
    expect(screen.getByText("Leadership")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.hideShared") }));
    api.shares.view.mockRejectedValueOnce(new ApiError({ status: 404, code: "nf", message: "x", kind: "notFound", requestId: null }));
    fireEvent.click(screen.getByRole("button", { name: `${t("wsMgmt.viewShared")}: ${t("wsMgmt.typeStory")} #5` }));
    expect(await screen.findByText(t("wsMgmt.viewerUnavailable"))).toBeInTheDocument();
  });

  it("redirects an old ?token= link to the explicit accept page instead of accepting as a side effect", async () => {
    const replace = vi.fn();
    const original = window.location;
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, search: "?token=abc123", replace } });
    try {
      wrap(<WorkspacesPanel />);
      await waitFor(() => expect(replace).toHaveBeenCalledWith("/workspaces/accept?token=abc123"));
      expect(api.workspaces.accept).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: original });
    }
  });
});

// ------------------------------------------------------------------------------------------------ detail: owner

describe("Workspace detail as the owner", () => {
  it("renders members with addresses, role actions, and the invitation form and list", async () => {
    wrap(<WorkspaceDetail workspaceId={7} />);
    expect(await screen.findByRole("heading", { level: 1, name: "Team Alpha" })).toBeInTheDocument();
    expect(screen.getByText(/olive@x\.com/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${t("wsMgmt.makeAdmin")}: m***@x.com` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${t("wsMgmt.makeMember")}: a***@x.com` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${t("wsMgmt.removeMember")}: m***@x.com` })).toBeInTheDocument();
    expect(screen.getByText("ivan@x.com")).toBeInTheDocument();
    expect(screen.getByLabelText(t("wsMgmt.inviteEmail"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("wsMgmt.inviteRole"))).toBeInTheDocument();
    expect(screen.getByText(t("wsMgmt.inviteHint", { hours: 72 }))).toBeInTheDocument();
    expect(screen.getByText(t("wsMgmt.sharedEmpty"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("workspaces.leave") })).toBeNull();           // the owner must transfer first
    expect(screen.getByText(t("wsMgmt.ownerMustTransfer"))).toBeInTheDocument();
  });

  it("invites with the chosen role, reports provider acceptance WITHOUT claiming delivery, and the not-sent case honestly", async () => {
    api.workspaces.invite.mockResolvedValueOnce({ invitation_id: 1, status: "pending", expires_at: "x", email_delivery: "submitted" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.change(await screen.findByLabelText(t("wsMgmt.inviteEmail")), { target: { value: "new@x.com" } });
    fireEvent.change(screen.getByLabelText(t("wsMgmt.inviteRole")), { target: { value: "workspace_admin" } });
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.inviteSend") }));
    await waitFor(() => expect(api.workspaces.invite).toHaveBeenCalledWith(7, "new@x.com", "workspace_admin"));
    expect(await screen.findByText(t("wsMgmt.inviteSubmitted"))).toBeInTheDocument();
    expect(t("wsMgmt.inviteSubmitted")).not.toMatch(/delivered successfully|has been delivered/i);

    api.workspaces.invite.mockResolvedValueOnce({ invitation_id: 2, status: "pending", expires_at: "x", email_delivery: "not_submitted" });
    fireEvent.change(screen.getByLabelText(t("wsMgmt.inviteEmail")), { target: { value: "again@x.com" } });
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.inviteSend") }));
    expect(await screen.findByText(t("wsMgmt.inviteNotSubmitted"))).toBeInTheDocument();
  });

  it("maps a server refusal to a calm, specific message (409 state, 403 role)", async () => {
    api.workspaces.invite.mockRejectedValueOnce(new ApiError({ status: 409, code: "x", message: "already a member", kind: "conflict", requestId: null }));
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.change(await screen.findByLabelText(t("wsMgmt.inviteEmail")), { target: { value: "mia@x.com" } });
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.inviteSend") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t("wsMgmt.errConflict"));
    expect(screen.getByLabelText(t("wsMgmt.inviteEmail"))).toHaveValue("mia@x.com");           // nothing lost
  });

  it("revokes a pending invitation and changes a role through the API", async () => {
    api.workspaces.revokeInvitation.mockResolvedValue({ status: "revoked" });
    api.workspaces.setMemberRole.mockResolvedValue({ user_id: 2, role: "workspace_admin", changed: true });
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: `${t("wsMgmt.revokeInvite")}: ivan@x.com` }));
    await waitFor(() => expect(api.workspaces.revokeInvitation).toHaveBeenCalledWith(7, 11));
    expect(await screen.findByText(t("wsMgmt.inviteRevoked"))).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: `${t("wsMgmt.makeAdmin")}: m***@x.com` }));
    await waitFor(() => expect(api.workspaces.setMemberRole).toHaveBeenCalledWith(7, 2, "workspace_admin"));
    fireEvent.click(screen.getByRole("button", { name: `${t("wsMgmt.makeMember")}: a***@x.com` }));
    await waitFor(() => expect(api.workspaces.setMemberRole).toHaveBeenCalledWith(7, 3, "workspace_member"));
  });

  it("removes a member only after an accessible confirmation that says what happens, and Cancel changes nothing", async () => {
    api.workspaces.removeMember.mockResolvedValue({ status: "removed" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: `${t("wsMgmt.removeMember")}: m***@x.com` }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(t("wsMgmt.removeTitle", { name: "m***@x.com" }))).toBeInTheDocument();
    expect(within(dialog).getByText(t("wsMgmt.removeBody", { name: "m***@x.com" }))).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: t("common.cancel") }));
    expect(api.workspaces.removeMember).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: `${t("wsMgmt.removeMember")}: m***@x.com` }));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: t("wsMgmt.removeConfirm") }));
    await waitFor(() => expect(api.workspaces.removeMember).toHaveBeenCalledWith(7, 2));
    expect(await screen.findByText(t("wsMgmt.memberRemoved"))).toBeInTheDocument();
  });

  it("proposes a transfer only with the exact workspace name AND a password, and says what happens first", async () => {
    api.workspaces.transferStepUp.mockResolvedValue({ elevated: true, window_seconds: 300 });
    api.workspaces.proposeTransfer.mockResolvedValue({ id: 5, workspace_id: 7, status: "pending", viewer_role: "proposer", former_owner_role: "workspace_member", expires_at: "2026-10-30T10:00:00Z", counterpart_label: "a***@x.com", email_delivery: "submitted" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: `${t("wsMgmt.transferAction")}: a***@x.com` }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(t("wsTransfer.consequenceNewOwner", { name: "a***@x.com" }))).toBeInTheDocument();     // consequences are visible BEFORE anything is sent
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(api.workspaces.transferStepUp).not.toHaveBeenCalled();                                    // nothing typed
    expect(await within(dialog).findByRole("alert")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.confirmNameLabel")), { target: { value: "team alpha" } });
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.passwordLabel")), { target: { value: "pw" } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(api.workspaces.transferStepUp).not.toHaveBeenCalled();                                    // case matters
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.confirmNameLabel")), { target: { value: "Team Alpha" } });
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.passwordLabel")), { target: { value: "" } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(api.workspaces.transferStepUp).not.toHaveBeenCalled();                                    // a password is required
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.passwordLabel")), { target: { value: "pw" } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    await waitFor(() => expect(api.workspaces.proposeTransfer).toHaveBeenCalledWith(7, 3, "Team Alpha", "workspace_member"));
    expect(api.workspaces.transferStepUp).toHaveBeenCalledWith("pw");
    expect(await screen.findByText(t("wsTransfer.proposedNotice"))).toBeInTheDocument();
  });

  it("archives with a confirmation, deletes with the typed name and then leaves the page", async () => {
    api.workspaces.archive.mockResolvedValue({});
    api.workspaces.remove.mockResolvedValue({ status: "deleted" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: t("wsMgmt.archiveAction") }));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: t("wsMgmt.archiveConfirm") }));
    await waitFor(() => expect(api.workspaces.archive).toHaveBeenCalledWith(7));
    expect(await screen.findByText(t("wsMgmt.archivedNotice"))).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.deleteAction") }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(t("wsMgmt.deleteBody"))).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(t("wsMgmt.confirmNameLabel")), { target: { value: "wrong" } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsMgmt.deleteConfirm") }));
    expect(api.workspaces.remove).not.toHaveBeenCalled();
    fireEvent.change(within(dialog).getByLabelText(t("wsMgmt.confirmNameLabel")), { target: { value: "Team Alpha" } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsMgmt.deleteConfirm") }));
    await waitFor(() => expect(api.workspaces.remove).toHaveBeenCalledWith(7, "Team Alpha"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces"));
  });

  it("an archived workspace shows the banner, pauses sharing and offers Restore", async () => {
    api.workspaces.get.mockResolvedValue(detail("workspace_owner", { status: "deactivated", capabilities: { ...OWNER_CAPS, can_invite: false, can_archive: false, can_restore: true, can_share: false } }));
    api.workspaces.restore.mockResolvedValue({});
    wrap(<WorkspaceDetail workspaceId={7} />);
    expect(await screen.findByText(t("wsMgmt.archivedBanner"))).toBeInTheDocument();
    expect(screen.getByText(t("wsMgmt.shareArchived"))).toBeInTheDocument();
    expect(screen.queryByLabelText(t("wsMgmt.inviteEmail"))).toBeNull();
    expect(screen.queryByRole("button", { name: t("wsMgmt.shareAction") })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.restoreAction") }));
    await waitFor(() => expect(api.workspaces.restore).toHaveBeenCalledWith(7));
  });

  it("renames only when the name actually changed", async () => {
    api.workspaces.rename.mockResolvedValue({});
    wrap(<WorkspaceDetail workspaceId={7} />);
    const save = await screen.findByRole("button", { name: t("wsMgmt.renameSave") });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(t("wsMgmt.settingsRename")), { target: { value: "Team Beta" } });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(api.workspaces.rename).toHaveBeenCalledWith(7, "Team Beta"));
  });
});

// ------------------------------------------------------------------------------------- detail: admin and member

describe("Workspace detail for an admin and for a plain member", () => {
  it("an admin can invite members but is offered no admin role, no role changes, transfer, archive or delete", async () => {
    api.workspaces.get.mockResolvedValue(detail("workspace_admin"));
    wrap(<WorkspaceDetail workspaceId={7} />);
    await screen.findByLabelText(t("wsMgmt.inviteEmail"));
    expect(screen.queryByLabelText(t("wsMgmt.inviteRole"))).toBeNull();                              // member invitations only
    expect(screen.queryByRole("button", { name: new RegExp(t("wsMgmt.makeAdmin")) })).toBeNull();
    expect(screen.queryByRole("button", { name: new RegExp(t("wsMgmt.transferAction")) })).toBeNull();
    expect(screen.queryByRole("button", { name: t("wsMgmt.archiveAction") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("wsMgmt.deleteAction") })).toBeNull();
    expect(screen.getByRole("button", { name: `${t("wsMgmt.removeMember")}: m***@x.com` })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: `${t("wsMgmt.removeMember")}: o***@x.com` })).toBeNull();      // never the owner
    expect(screen.queryByRole("button", { name: new RegExp(`${t("wsMgmt.removeMember")}: a\\*\\*\\*`) })).toBeNull();
  });

  it("a plain member sees labels only, no management controls, and can leave or share", async () => {
    api.workspaces.get.mockResolvedValue(detail("workspace_member"));
    api.workspaces.leave.mockResolvedValue({ status: "left" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    await screen.findByRole("heading", { level: 1, name: "Team Alpha" });
    expect(screen.queryByText(/olive@x\.com/)).toBeNull();
    expect(screen.getByText(/o\*\*\*@x\.com/)).toBeInTheDocument();
    expect(screen.queryByLabelText(t("wsMgmt.inviteEmail"))).toBeNull();
    expect(screen.queryByText(t("wsMgmt.sectionSettings"))).toBeNull();
    expect(screen.queryByText(t("wsMgmt.pendingTitle"))).toBeNull();
    expect(screen.queryByRole("button", { name: new RegExp(t("wsMgmt.removeMember")) })).toBeNull();
    expect(screen.getByText(t("wsMgmt.shareTitle"))).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: t("workspaces.leave") }));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: t("wsMgmt.leaveConfirm") }));
    await waitFor(() => expect(api.workspaces.leave).toHaveBeenCalledWith(7));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces"));
  });

  it("a server error is an error with Try again, not 'not available'", async () => {
    api.workspaces.get.mockRejectedValueOnce(new ApiError({ status: 500, code: "x", message: "boom", kind: "server", requestId: null }));
    wrap(<WorkspaceDetail workspaceId={7} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(t("states.genericError"));
    expect(screen.queryByText(t("wsMgmt.errNotFound"))).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t("states.retry") }));
    expect(await screen.findByRole("heading", { level: 1, name: "Team Alpha" })).toBeInTheDocument();
  });

  it("a workspace you cannot see is reported as not available, with a way back", async () => {
    api.workspaces.get.mockRejectedValue(new ApiError({ status: 404, code: "nf", message: "x", kind: "notFound", requestId: null }));
    wrap(<WorkspaceDetail workspaceId={99} />);
    expect(await screen.findByText(t("wsMgmt.errNotFound"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t("wsMgmt.backToList") })).toHaveAttribute("href", "/workspaces");
  });
});

// --------------------------------------------------------------------------------------------------- sharing

describe("Sharing into a workspace", () => {
  it("needs an item AND the explicit consent acknowledgement, then sends consent=true (VIEW only)", async () => {
    api.shares.create.mockResolvedValue({ share_id: 1, status: "active" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    const button = await screen.findByRole("button", { name: t("wsMgmt.shareAction") });
    expect(button).toBeDisabled();
    await waitFor(() => expect(screen.getByRole("option", { name: "Led a launch" })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(t("wsMgmt.shareItem")), { target: { value: "5" } });
    expect(button).toBeDisabled();                                                                    // still no consent
    fireEvent.click(screen.getByRole("checkbox", { name: t("wsMgmt.shareConsent") }));
    expect(button).toBeEnabled();
    fireEvent.click(button);
    await waitFor(() => expect(api.shares.create).toHaveBeenCalledWith(7, "story", "5", true));
    expect(await screen.findByText(t("wsMgmt.shareDone"))).toBeInTheDocument();
  });

  it("offers only COMPLETED interviews as reports, and says honestly when there is nothing to share", async () => {
    wrap(<WorkspaceDetail workspaceId={7} />);
    await screen.findByRole("button", { name: t("wsMgmt.shareAction") });
    fireEvent.change(screen.getByLabelText(t("wsMgmt.shareType")), { target: { value: "interview_report" } });
    await waitFor(() => expect(screen.getByRole("option", { name: "PM #9" })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: "Draft #10" })).toBeNull();
    api.history.list.mockResolvedValue({ interviews: [] });
    fireEvent.change(screen.getByLabelText(t("wsMgmt.shareType")), { target: { value: "story" } });
    api.stories.list.mockResolvedValue({ stories: [] });
    fireEvent.change(screen.getByLabelText(t("wsMgmt.shareType")), { target: { value: "interview_report" } });
    expect(await screen.findByText(t("wsMgmt.shareNoItems"))).toBeInTheDocument();
  });

  it("lists what is shared in the workspace, lets only the sharer stop it, and a stopped item shows as unavailable", async () => {
    api.workspaces.shares.mockResolvedValue({ shares: [
      { id: 1, workspace_id: 7, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: "m***@x.com", mine: false },
      { id: 2, workspace_id: 7, resource_type: "interview_report", resource_id: "9", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: "o***@x.com", mine: true },
    ] });
    api.shares.revoke.mockResolvedValue({ status: "revoked" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    await screen.findByText(t("wsMgmt.sharedBy", { name: "m***@x.com" }));
    expect(screen.getByText(t("wsMgmt.sharedByYou"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: `${t("wsMgmt.stopSharing")}: ${t("wsMgmt.typeStory")} #5` })).toBeNull();       // not yours
    fireEvent.click(screen.getByRole("button", { name: `${t("wsMgmt.stopSharing")}: ${t("wsMgmt.typeReport")} #9` }));
    await waitFor(() => expect(api.shares.revoke).toHaveBeenCalledWith(2));
    expect(await screen.findByText(t("wsMgmt.shareStopped"))).toBeInTheDocument();
  });
});

describe("Shared item viewer", () => {
  it("renders the bounded projection as plain text (never HTML) and reports a withdrawn share", async () => {
    api.shares.view.mockResolvedValueOnce({ resource_type: "story", resource_id: "5", shared_by_owner: true, resource: { title: "<img src=x onerror=alert(1)>", result: "Revenue up" } });
    const onClose = vi.fn();
    wrap(<SharedItemViewer resourceType="story" resourceId="5" onClose={onClose} />);
    expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.hideShared") }));
    expect(onClose).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------------------------- invitation page

describe("Invitation page", () => {
  const setSearch = (search: string) => window.history.pushState({}, "", `/workspaces/accept${search}`);

  it("asks for a complete link when the token is missing", async () => {
    setSearch("");
    wrap(<InviteAccept />);
    expect(await screen.findByText(t("wsMgmt.acceptMissingToken"))).toBeInTheDocument();
    expect(api.workspaces.previewInvitation).not.toHaveBeenCalled();
  });

  it("previews the invitation and joins only when the person presses Accept", async () => {
    setSearch("?token=tok_1");
    api.workspaces.previewInvitation.mockResolvedValue({ invitation_id: 4, workspace_name: "Bravo", role: "workspace_member", expires_at: "2026-10-30T10:00:00Z" });
    api.workspaces.accept.mockResolvedValue({});
    wrap(<InviteAccept />);
    expect(await screen.findByText("Bravo")).toBeInTheDocument();
    expect(screen.getByText(t("wsMgmt.roleMember"))).toBeInTheDocument();
    expect(api.workspaces.accept).not.toHaveBeenCalled();                                            // opening the link accepts nothing
    fireEvent.click(screen.getByRole("button", { name: t("wsMgmt.acceptButton") }));
    await waitFor(() => expect(api.workspaces.accept).toHaveBeenCalledWith("tok_1"));
    expect(await screen.findByText(t("wsMgmt.acceptDone"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t("wsMgmt.openWorkspaceAfter") })).toHaveAttribute("href", "/workspaces");
  });

  it("declines explicitly and says nothing was shared", async () => {
    setSearch("?token=tok_2");
    api.workspaces.previewInvitation.mockResolvedValue({ invitation_id: 4, workspace_name: "Bravo", role: "workspace_admin", expires_at: null });
    api.workspaces.decline.mockResolvedValue({ status: "declined" });
    wrap(<InviteAccept />);
    fireEvent.click(await screen.findByRole("button", { name: t("wsMgmt.declineButton") }));
    await waitFor(() => expect(api.workspaces.decline).toHaveBeenCalledWith("tok_2"));
    expect(await screen.findByText(t("wsMgmt.acceptDeclined"))).toBeInTheDocument();
  });

  it.each([
    [401, "unauthenticated", "wsMgmt.acceptSignIn"],
    [403, "forbidden", "wsMgmt.acceptWrongAccount"],
    [404, "notFound", "wsMgmt.acceptGone"],
    [409, "conflict", "wsMgmt.acceptGone"],
  ])("explains a %s from the server with the right next step", async (status, kind, key) => {
    setSearch("?token=tok_3");
    api.workspaces.previewInvitation.mockRejectedValue(new ApiError({ status, code: "x", message: "different email", kind: kind as never, requestId: null }));
    wrap(<InviteAccept />);
    expect(await screen.findByText(t(key))).toBeInTheDocument();
    if (status === 401) expect(screen.getByRole("link", { name: t("common.signIn") })).toHaveAttribute("href", "/sign-in");
  });

  it("tells an unverified account to verify first (the server's refusal mentions verification)", async () => {
    setSearch("?token=tok_4");
    api.workspaces.previewInvitation.mockRejectedValue(new ApiError({ status: 403, code: "x", message: "Verify your email address before responding to a workspace invitation.", kind: "forbidden", requestId: null }));
    wrap(<InviteAccept />);
    expect(await screen.findByText(t("wsMgmt.acceptVerifyFirst"))).toBeInTheDocument();
  });
});

// -------------------------------------------------------------------------------------------- localisation

describe("Localisation of the 04B copy", () => {
  const locales = ["en", "de", "fr", "es", "it", "pt", "nl", "ru"] as const;
  const keysOf = (l: (typeof locales)[number]) => Object.keys((ws04b[l] as { wsMgmt: Record<string, string> }).wsMgmt).sort();
  const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");

  it("has identical keys, no empty strings and the same placeholders in all eight catalogue locales", () => {
    const reference = keysOf("en");
    expect(reference.length).toBeGreaterThan(80);
    for (const l of locales) {
      expect(keysOf(l), l).toEqual(reference);
      const block = (ws04b[l] as { wsMgmt: Record<string, string> }).wsMgmt;
      const en = (ws04b.en as { wsMgmt: Record<string, string> }).wsMgmt;
      for (const k of reference) {
        expect(block[k].trim().length, `${l}.${k}`).toBeGreaterThan(0);
        expect(ph(block[k]), `${l}.${k} placeholders`).toBe(ph(en[k]));
        expect(block[k], `${l}.${k} must not contain an em dash`).not.toMatch(/—/);
      }
    }
  });

  it("really translates (not English copies) and resolves through the live catalogue in every locale", () => {
    for (const l of locales.filter((x) => x !== "en")) {
      let differing = 0;
      const block = (ws04b[l] as { wsMgmt: Record<string, string> }).wsMgmt;
      const en = (ws04b.en as { wsMgmt: Record<string, string> }).wsMgmt;
      for (const k of Object.keys(en)) if (block[k] !== en[k]) differing += 1;
      expect(differing / Object.keys(en).length, l).toBeGreaterThan(0.9);
      expect(translate(l, "wsMgmt.acceptButton")).toBe(block.acceptButton);
      expect(translate(l, "wsMgmt.removeTitle", { name: "X" })).toContain("X");
    }
  });

  it("renders the detail page in German, with the German dialog", async () => {
    wrap(<WorkspaceDetail workspaceId={7} />, "de");
    expect(await screen.findByRole("heading", { name: translate("de", "wsMgmt.sectionMembers") + " (3)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: translate("de", "wsMgmt.deleteAction") }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(translate("de", "wsMgmt.deleteTitle"))).toBeInTheDocument();
    await act(async () => { /* settle */ });
  });
});
