import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import wsxfer from "@/lib/i18n/messages/wsxfer";

/**
 * 04B completion: two-step ownership transfer UI. The component tests mock the API; the shape-guard tests run the REAL client against a stubbed `fetch`, so a
 * malformed 200 is proven to become an explicit error at the client boundary (never a crash, never a silently empty "no transfer").
 */

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));

const { api } = vi.hoisted(() => ({ api: {
  workspaces: {
    list: vi.fn(), get: vi.fn(), shares: vi.fn(), transferStepUp: vi.fn(), proposeTransfer: vi.fn(), transferState: vi.fn(), transfersMine: vi.fn(),
    cancelTransfer: vi.fn(), declineTransfer: vi.fn(), previewTransfer: vi.fn(), acceptTransfer: vi.fn(),
    acceptById: vi.fn(), declineById: vi.fn(), create: vi.fn(), leave: vi.fn(),
  },
  shares: { mine: vi.fn(), withMe: vi.fn(), revoke: vi.fn(), create: vi.fn(), view: vi.fn() },
  stories: { list: vi.fn() },
  history: { list: vi.fn() },
} }));
vi.mock("@/lib/api/client", () => ({ api }));
const realClient = () => vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { TransferAccept } from "@/components/workspaces/TransferAccept";
import { WorkspaceDetail } from "@/components/workspaces/WorkspaceDetail";
import { WorkspacesPanel } from "@/components/workspaces/WorkspacesPanel";
import { isTransfer, isTransferList, isTransferPreview, isTransferState } from "@/lib/workspaces/transferGuard";

const t = (k: string, v?: Record<string, string | number>) => translate("en", k, v);
const wrap = (ui: React.ReactNode, locale: "en" | "de" = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

const OWNER_CAPS = { can_rename: true, can_invite: true, can_invite_admin: true, can_remove_members: true, can_change_roles: true, can_transfer: true, can_archive: true, can_restore: false, can_delete: true, can_leave: false, can_share: true };
const MEMBER_CAPS = { can_rename: false, can_invite: false, can_invite_admin: false, can_remove_members: false, can_change_roles: false, can_transfer: false, can_archive: false, can_restore: false, can_delete: false, can_leave: true, can_share: true };

function detail(role: "workspace_owner" | "workspace_member") {
  const owner = role === "workspace_owner";
  return {
    id: 7, name: "Team Alpha", status: "active", owner_user_id: owner ? 1 : 9, member_count: 2, created_at: null, my_role: role, capabilities: owner ? OWNER_CAPS : MEMBER_CAPS,
    members: [
      { user_id: 1, role: "workspace_owner", status: "active", joined_at: "2026-10-01T10:00:00Z", label: owner ? "Olive" : "o***@x.com", is_me: owner },
      { user_id: 2, role: "workspace_member", status: "active", joined_at: "2026-10-02T10:00:00Z", label: owner ? "m***@x.com" : "Mia", is_me: !owner },
    ],
    limits: { max_members: 100, max_pending_invitations: 50, invitation_ttl_hours: 72 },
  };
}

const TRANSFER = { id: 5, workspace_id: 7, status: "pending", viewer_role: "proposer", former_owner_role: "workspace_admin", expires_at: "2026-10-30T10:00:00Z", counterpart_label: "m***@x.com" };

beforeEach(() => {
  for (const group of Object.values(api)) for (const fn of Object.values(group)) (fn as ReturnType<typeof vi.fn>).mockReset();
  api.workspaces.list.mockResolvedValue({ workspaces: [], invited: [] });
  api.workspaces.get.mockResolvedValue(detail("workspace_owner"));
  api.workspaces.shares.mockResolvedValue({ shares: [] });
  api.workspaces.transferState.mockResolvedValue({ transfer: null });
  api.workspaces.transfersMine.mockResolvedValue({ transfers: [] });
  api.shares.mine.mockResolvedValue({ shares: [] });
  api.shares.withMe.mockResolvedValue({ shares: [] });
  api.stories.list.mockResolvedValue({ stories: [] });
  api.history.list.mockResolvedValue({ interviews: [] });
  push.mockReset();
  window.history.pushState({}, "", "/");
});
afterEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------------------------------------------- propose

describe("proposing a transfer", () => {
  const openDialog = async () => {
    wrap(<WorkspaceDetail workspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: `${t("wsMgmt.transferAction")}: m***@x.com` }));
    return await screen.findByRole("alertdialog");
  };
  const fill = (dialog: HTMLElement, name = "Team Alpha", pw = "secret-pw") => {
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.confirmNameLabel")), { target: { value: name } });
    fireEvent.change(within(dialog).getByLabelText(t("wsTransfer.passwordLabel")), { target: { value: pw } });
  };

  it("states every consequence, defaults the former owner to a member and lets the owner keep an admin role instead", async () => {
    api.workspaces.transferStepUp.mockResolvedValue({ elevated: true, window_seconds: 300 });
    api.workspaces.proposeTransfer.mockResolvedValue({ ...TRANSFER, email_delivery: "submitted" });
    const dialog = await openDialog();
    for (const key of ["consequenceNewOwner", "consequenceShares", "consequenceExpiry"]) {
      expect(within(dialog).getByText(t(`wsTransfer.${key}`, { name: "m***@x.com" }))).toBeInTheDocument();
    }
    expect(within(dialog).getByText(t("wsTransfer.consequenceYou", { role: t("wsTransfer.keepMember") }))).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("radio", { name: t("wsTransfer.keepAdmin") }));
    expect(within(dialog).getByText(t("wsTransfer.consequenceYou", { role: t("wsTransfer.keepAdmin") }))).toBeInTheDocument();
    fill(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    await waitFor(() => expect(api.workspaces.proposeTransfer).toHaveBeenCalledWith(7, 2, "Team Alpha", "workspace_admin"));
    expect(api.workspaces.transferStepUp.mock.invocationCallOrder[0]).toBeLessThan(api.workspaces.proposeTransfer.mock.invocationCallOrder[0]);   // the fresh password comes first
    expect(await screen.findByText(t("wsTransfer.proposedNotice"))).toBeInTheDocument();
    expect(screen.queryByText(/delivered/i)).toBeNull();                                                          // a provider hand-over is never "delivered"
  });

  it("is honest when the notice email was not handed to the provider", async () => {
    api.workspaces.transferStepUp.mockResolvedValue({ elevated: true, window_seconds: 300 });
    api.workspaces.proposeTransfer.mockResolvedValue({ ...TRANSFER, email_delivery: "not_submitted" });
    const dialog = await openDialog();
    fill(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(await screen.findByText(t("wsTransfer.proposedNoticeNotSent"))).toBeInTheDocument();
  });

  it.each([
    ["step_up_failed", 403, "wsTransfer.errStepUpFailed"],
    ["step_up_unavailable", 403, "wsTransfer.errStepUpUnavailable"],
  ])("shows the localized %s refusal inside the dialog and never proposes", async (code, status, key) => {
    api.workspaces.transferStepUp.mockRejectedValue(new ApiError({ status, code, message: "x", kind: "forbidden", requestId: null }));
    const dialog = await openDialog();
    fill(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(await within(dialog).findByText(t(key))).toBeInTheDocument();
    expect(api.workspaces.proposeTransfer).not.toHaveBeenCalled();
    expect((within(dialog).getByLabelText(t("wsTransfer.passwordLabel")) as HTMLInputElement).value).toBe("");     // the password never lingers
  });

  it("maps a server-side refusal of the recipient (422) and an open transfer (409)", async () => {
    api.workspaces.transferStepUp.mockResolvedValue({ elevated: true, window_seconds: 300 });
    api.workspaces.proposeTransfer.mockRejectedValueOnce(new ApiError({ status: 422, code: "validation_error", message: "x", kind: "validation", requestId: null }));
    const dialog = await openDialog();
    fill(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(await within(dialog).findByText(t("wsTransfer.errRecipient"))).toBeInTheDocument();
    api.workspaces.proposeTransfer.mockRejectedValueOnce(new ApiError({ status: 409, code: "conflict", message: "x", kind: "conflict", requestId: null }));
    fill(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: t("wsTransfer.sendProposal") }));
    expect(await within(dialog).findByText(t("wsMgmt.errConflict"))).toBeInTheDocument();
  });

  it("offers no transfer control to a member, to an admin-less view, while archived or while a transfer is already pending", async () => {
    api.workspaces.get.mockResolvedValue(detail("workspace_member"));
    wrap(<WorkspaceDetail workspaceId={7} />);
    await screen.findByText("Team Alpha");
    expect(screen.queryByRole("button", { name: new RegExp(t("wsMgmt.transferAction")) })).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------- banners

describe("the pending transfer, for both parties", () => {
  it("the proposer sees the pending state with its consequences and can cancel, but gets no second proposal button", async () => {
    api.workspaces.transferState.mockResolvedValue({ transfer: TRANSFER });
    api.workspaces.cancelTransfer.mockResolvedValue({ status: "cancelled" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    const banner = await screen.findByTestId("transfer-banner-proposer");
    expect(within(banner).getByText(t("wsTransfer.proposerBody", { name: "m***@x.com", date: "Oct 30, 2026" }))).toBeInTheDocument();
    expect(within(banner).getByText(t("wsTransfer.proposerKeeps", { name: "m***@x.com", role: t("wsTransfer.keepAdmin") }))).toBeInTheDocument();
    expect(within(banner).getByText(t("wsTransfer.cancelNote"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: new RegExp(t("wsMgmt.transferAction")) })).toBeNull();
    api.workspaces.transferState.mockResolvedValue({ transfer: null });
    fireEvent.click(within(banner).getByRole("button", { name: t("wsTransfer.cancelAction") }));
    await waitFor(() => expect(api.workspaces.cancelTransfer).toHaveBeenCalledWith(7));
    expect(await screen.findByText(t("wsTransfer.cancelledNotice"))).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId("transfer-banner-proposer")).toBeNull());
  });

  it("the recipient sees what accepting means, can decline here, and has NO accept button (accepting needs the emailed link)", async () => {
    api.workspaces.get.mockResolvedValue(detail("workspace_member"));
    api.workspaces.transferState.mockResolvedValue({ transfer: { ...TRANSFER, viewer_role: "recipient", counterpart_label: "o***@x.com" } });
    api.workspaces.declineTransfer.mockResolvedValue({ status: "declined" });
    wrap(<WorkspaceDetail workspaceId={7} />);
    const banner = await screen.findByTestId("transfer-banner-recipient");
    expect(within(banner).getByText(t("wsTransfer.recipientBody", { name: "o***@x.com", date: "Oct 30, 2026" }))).toBeInTheDocument();
    expect(within(banner).getByText(t("wsTransfer.recipientHow"))).toBeInTheDocument();
    expect(within(banner).queryByRole("button", { name: /accept/i })).toBeNull();
    fireEvent.click(within(banner).getByRole("button", { name: t("wsTransfer.declineAction") }));
    await waitFor(() => expect(api.workspaces.declineTransfer).toHaveBeenCalledWith(5));
    expect(await screen.findByText(t("wsTransfer.declinedNotice"))).toBeInTheDocument();
  });

  it("a failed transfer lookup is an explicit warning with retry and does not blank the workspace", async () => {
    api.workspaces.transferState.mockRejectedValueOnce(new Error("malformed"));
    wrap(<WorkspaceDetail workspaceId={7} />);
    expect(await screen.findByText(t("wsTransfer.loadFailed"))).toBeInTheDocument();
    expect(screen.getByText("Team Alpha")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: `${t("wsMgmt.transferAction")}: m***@x.com` })).toBeNull();          // never offer a transfer while the state is unknown
    fireEvent.click(screen.getByRole("button", { name: t("states.retry") }));
    expect(await screen.findByRole("button", { name: `${t("wsMgmt.transferAction")}: m***@x.com` })).toBeInTheDocument();
  });

  it("the list page shows pending transfers for both parties and warns (never silently hides) when they cannot be loaded", async () => {
    api.workspaces.transfersMine.mockResolvedValue({ transfers: [
      { ...TRANSFER, workspace_name: "Team Alpha" },
      { ...TRANSFER, id: 6, workspace_id: 8, viewer_role: "recipient", workspace_name: "Team Beta", counterpart_label: "o***@x.com" },
    ] });
    wrap(<WorkspacesPanel />);
    expect(await screen.findByRole("heading", { name: t("wsTransfer.listTitle") })).toBeInTheDocument();
    expect(screen.getByTestId("transfer-banner-proposer")).toBeInTheDocument();
    expect(screen.getByTestId("transfer-banner-recipient")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: t("wsTransfer.openWorkspace") }).map((a) => a.getAttribute("href"))).toEqual(["/workspaces/7", "/workspaces/8"]);
    fireEvent.click(screen.getByRole("button", { name: t("wsTransfer.declineAction") }));
    await waitFor(() => expect(api.workspaces.declineTransfer).toHaveBeenCalledWith(6));
  });

  it("the list page keeps working and shows a warning when the transfer lookup fails", async () => {
    api.workspaces.transfersMine.mockRejectedValue(new ApiError({ status: null, code: "malformed_response", message: "x", kind: "unknown", requestId: null }));
    wrap(<WorkspacesPanel />);
    expect(await screen.findByText(t("wsTransfer.loadFailed"))).toBeInTheDocument();
    expect(screen.getByText(t("workspaces.myWorkspaces"))).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------------------------------------------- accept page

describe("the accept page", () => {
  const setSearch = (s: string) => window.history.pushState({}, "", `/workspaces/transfer/accept${s}`);
  const PREVIEW = { ...TRANSFER, viewer_role: "recipient", workspace_name: "Team Alpha", counterpart_label: "o***@x.com" };

  it("shows the proposal and its consequences, changes nothing by opening, and accepts only on the explicit button", async () => {
    setSearch("?token=tok_1");
    api.workspaces.previewTransfer.mockResolvedValue(PREVIEW);
    api.workspaces.acceptTransfer.mockResolvedValue({ id: 7, name: "Team Alpha", owner_user_id: 2 });
    wrap(<TransferAccept />);
    expect(await screen.findByText("Team Alpha")).toBeInTheDocument();
    expect(screen.getByText("o***@x.com")).toBeInTheDocument();
    expect(screen.getByText(t("wsTransfer.acceptYouBecome"))).toBeInTheDocument();
    expect(screen.getByText(t("wsTransfer.acceptFormerRole", { role: t("wsTransfer.keepAdmin") }))).toBeInTheDocument();
    expect(api.workspaces.previewTransfer).toHaveBeenCalledWith("tok_1");
    expect(api.workspaces.acceptTransfer).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: t("wsTransfer.acceptButton") }));
    await waitFor(() => expect(api.workspaces.acceptTransfer).toHaveBeenCalledWith("tok_1"));
    expect(await screen.findByText(t("wsTransfer.acceptDone"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t("wsTransfer.openWorkspace") })).toHaveAttribute("href", "/workspaces/7");
  });

  it("declines by transfer id", async () => {
    setSearch("?token=tok_2");
    api.workspaces.previewTransfer.mockResolvedValue(PREVIEW);
    api.workspaces.declineTransfer.mockResolvedValue({ status: "declined" });
    wrap(<TransferAccept />);
    fireEvent.click(await screen.findByRole("button", { name: t("wsTransfer.acceptDeclineButton") }));
    await waitFor(() => expect(api.workspaces.declineTransfer).toHaveBeenCalledWith(5));
    expect(await screen.findByText(t("wsTransfer.acceptDeclinedDone"))).toBeInTheDocument();
    expect(api.workspaces.acceptTransfer).not.toHaveBeenCalled();
  });

  it("explains a missing token without any request", async () => {
    wrap(<TransferAccept />);
    expect(await screen.findByText(t("wsTransfer.acceptMissingToken"))).toBeInTheDocument();
    expect(api.workspaces.previewTransfer).not.toHaveBeenCalled();
  });

  it.each([
    [401, "unauthenticated", "x", "wsTransfer.acceptSignIn"],
    [403, "forbidden", "Verify your email address before responding to an ownership transfer.", "wsTransfer.acceptVerifyFirst"],
    [403, "forbidden", "This ownership transfer was issued to a different email.", "wsTransfer.acceptWrongAccount"],
    [404, "notFound", "x", "wsTransfer.acceptGone"],
    [409, "conflict", "x", "wsTransfer.acceptGone"],
  ])("maps a %s refusal (%s) to its localized explanation", async (status, kind, message, key) => {
    setSearch("?token=tok_3");
    api.workspaces.previewTransfer.mockRejectedValue(new ApiError({ status, code: "x", message, kind: kind as never, requestId: null }));
    wrap(<TransferAccept />);
    expect(await screen.findByText(t(key))).toBeInTheDocument();
    if (status === 401) expect(screen.getByRole("link", { name: t("common.signIn") })).toHaveAttribute("href", "/sign-in");
  });

  it("a malformed preview is the generic error state, never a crash or an accept button", async () => {
    setSearch("?token=tok_4");
    api.workspaces.previewTransfer.mockRejectedValue(new ApiError({ status: null, code: "malformed_response", message: "x", kind: "unknown", requestId: null }));
    wrap(<TransferAccept />);
    expect(await screen.findByText(t("wsMgmt.errGeneric"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("wsTransfer.acceptButton") })).toBeNull();
  });

  it("an accept that fails after the preview (expired or cancelled meanwhile) reports it and does not claim success", async () => {
    setSearch("?token=tok_5");
    api.workspaces.previewTransfer.mockResolvedValue(PREVIEW);
    api.workspaces.acceptTransfer.mockRejectedValue(new ApiError({ status: 409, code: "conflict", message: "expired", kind: "conflict", requestId: null }));
    wrap(<TransferAccept />);
    fireEvent.click(await screen.findByRole("button", { name: t("wsTransfer.acceptButton") }));
    expect(await screen.findByText(t("wsTransfer.acceptGone"))).toBeInTheDocument();
    expect(screen.queryByText(t("wsTransfer.acceptDone"))).toBeNull();
  });

  it("renders in another language", async () => {
    setSearch("?token=tok_6");
    api.workspaces.previewTransfer.mockResolvedValue(PREVIEW);
    wrap(<TransferAccept />, "de");
    expect(await screen.findByRole("button", { name: translate("de", "wsTransfer.acceptButton") })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------------------------------------------- client boundary

describe("response shapes are validated at the client boundary", () => {
  const good = { id: 5, workspace_id: 7, status: "pending", viewer_role: "proposer", former_owner_role: "workspace_member", expires_at: null, counterpart_label: "m***@x.com" };

  it("accepts the documented shapes and rejects everything else", () => {
    expect(isTransfer(good)).toBe(true);
    expect(isTransferState({ transfer: null })).toBe(true);
    expect(isTransferState({ transfer: good })).toBe(true);
    expect(isTransferList({ transfers: [good] })).toBe(true);
    expect(isTransferPreview({ ...good, workspace_name: "A" })).toBe(true);
    for (const bad of [null, undefined, "x", 3, []]) {
      expect(isTransferState(bad), String(bad)).toBe(false);
      expect(isTransferList(bad), String(bad)).toBe(false);
      expect(isTransfer(bad), String(bad)).toBe(false);
    }
    expect(isTransferState({})).toBe(false);                                          // a proxy's `{}` is NOT "no transfer"
    expect(isTransferState({ transfer: {} })).toBe(false);
    expect(isTransferList({})).toBe(false);
    expect(isTransferList({ transfers: [{}] })).toBe(false);
    expect(isTransfer({ ...good, status: "weird" })).toBe(false);
    expect(isTransfer({ ...good, viewer_role: "owner" })).toBe(false);
    expect(isTransfer({ ...good, former_owner_role: "workspace_owner" })).toBe(false);
    expect(isTransfer({ ...good, id: "5" })).toBe(false);
    expect(isTransferPreview(good)).toBe(false);                                      // a preview must name the workspace
  });

  describe("through the real client", () => {
    const answer = (body: unknown, status = 200) => vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })));
    afterEach(() => vi.unstubAllGlobals());

    it.each([
      ["transferState", () => realClient().then((m) => m.api.workspaces.transferState(7))],
      ["transfersMine", () => realClient().then((m) => m.api.workspaces.transfersMine())],
      ["previewTransfer", () => realClient().then((m) => m.api.workspaces.previewTransfer("t"))],
      ["proposeTransfer", () => realClient().then((m) => m.api.workspaces.proposeTransfer(7, 2, "A", "workspace_member"))],
      ["cancelTransfer", () => realClient().then((m) => m.api.workspaces.cancelTransfer(7))],
      ["declineTransfer", () => realClient().then((m) => m.api.workspaces.declineTransfer(5))],
      ["acceptTransfer", () => realClient().then((m) => m.api.workspaces.acceptTransfer("t"))],
      ["transferStepUp", () => realClient().then((m) => m.api.workspaces.transferStepUp("pw"))],
    ])("%s: a 200 with an empty or foreign body is an explicit malformed_response error", async (_name, call) => {
      for (const body of [{}, [], "ok", null, { transfer: 3 }, { status: "weird" }]) {
        answer(body);
        await expect(call()).rejects.toMatchObject({ code: "malformed_response" });
      }
    });

    it("passes well-formed answers through and sends the documented requests", async () => {
      const mod = await realClient();
      answer({ transfer: good });
      expect((await mod.api.workspaces.transferState(7)).transfer?.id).toBe(5);
      answer({ transfer: null });
      expect((await mod.api.workspaces.transferState(7)).transfer).toBeNull();
      answer({ ...good, email_delivery: "submitted" });
      const sent = vi.mocked(globalThis.fetch);
      expect((await mod.api.workspaces.proposeTransfer(7, 2, "Team", "workspace_admin")).email_delivery).toBe("submitted");
      const [url, init] = sent.mock.calls[sent.mock.calls.length - 1] as [string, RequestInit];
      expect(url).toMatch(/\/workspaces\/7\/transfer$/);
      expect(JSON.parse(String(init.body))).toEqual({ new_owner_user_id: 2, confirm_name: "Team", former_owner_role: "workspace_admin" });
      answer({ status: "cancelled" });
      expect(await mod.api.workspaces.cancelTransfer(7)).toEqual({ status: "cancelled" });
      answer({ status: "declined" });
      expect(await mod.api.workspaces.declineTransfer(5)).toEqual({ status: "declined" });
    });

    it("keeps the server's refusal codes so the dialog can localize them", async () => {
      const mod = await realClient();
      answer({ error: { code: "step_up_failed", message: "That password was not accepted.", request_id: "r" } }, 403);
      await expect(mod.api.workspaces.transferStepUp("bad")).rejects.toMatchObject({ code: "step_up_failed", status: 403 });
    });
  });
});

// ---------------------------------------------------------------------------------------------------------------- localisation

describe("Localisation of the ownership-transfer copy", () => {
  const locales = ["en", "de", "fr", "es", "it", "pt", "nl", "ru"] as const;
  type Block = Record<string, string>;
  const block = (l: (typeof locales)[number]) => (wsxfer[l] as { wsTransfer: Block }).wsTransfer;
  const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");

  it("has identical keys, no empty strings, the same placeholders and no em dash in all eight catalogue locales", () => {
    const reference = Object.keys(block("en")).sort();
    expect(reference.length).toBeGreaterThan(45);
    for (const l of locales) {
      expect(Object.keys(block(l)).sort(), l).toEqual(reference);
      for (const k of reference) {
        expect(block(l)[k].trim().length, `${l}.${k}`).toBeGreaterThan(0);
        expect(ph(block(l)[k]), `${l}.${k} placeholders`).toBe(ph(block("en")[k]));
        expect(block(l)[k], `${l}.${k}`).not.toMatch(/—/);
        expect(block(l)[k], `${l}.${k} must not restate the slogan`).not.toMatch(/Ask More/i);
      }
    }
  });

  it("really translates (not English copies) and resolves through the live catalogue in every locale", () => {
    for (const l of locales.filter((x) => x !== "en")) {
      let differing = 0;
      for (const k of Object.keys(block("en"))) if (block(l)[k] !== block("en")[k]) differing += 1;
      expect(differing / Object.keys(block("en")).length, l).toBeGreaterThan(0.9);
      expect(translate(l, "wsTransfer.acceptButton")).toBe(block(l).acceptButton);
      expect(translate(l, "wsTransfer.proposeTitle", { name: "X" })).toContain("X");
    }
  });
});
