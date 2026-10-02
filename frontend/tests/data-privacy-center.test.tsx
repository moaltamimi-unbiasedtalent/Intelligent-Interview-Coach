import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";

/**
 * P10B-W9.8 - Data & Privacy Center (F1-F17). API is mocked; nothing paid/live is called.
 */

const opps = vi.fn();
const oppRemove = vi.fn();
const oppArchive = vi.fn();
const docs = vi.fn();
const docRemove = vi.fn();
const mems = vi.fn();
const memRemove = vi.fn();
const hist = vi.fn();
const histRemove = vi.fn();
const sharesMine = vi.fn();
const shareRevoke = vi.fn();
const wsList = vi.fn();
const deleteAccount = vi.fn();
const replace = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: {
    opportunities: { list: (...a: unknown[]) => opps(...a), remove: (...a: unknown[]) => oppRemove(...a), archive: (...a: unknown[]) => oppArchive(...a) },
    documents: { list: (...a: unknown[]) => docs(...a), remove: (...a: unknown[]) => docRemove(...a) },
    memory: { list: (...a: unknown[]) => mems(...a), remove: (...a: unknown[]) => memRemove(...a) },
    history: { list: (...a: unknown[]) => hist(...a), remove: (...a: unknown[]) => histRemove(...a) },
    shares: { mine: (...a: unknown[]) => sharesMine(...a), revoke: (...a: unknown[]) => shareRevoke(...a) },
    workspaces: { list: (...a: unknown[]) => wsList(...a) },
    auth: { deleteAccount: (...a: unknown[]) => deleteAccount(...a) },
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ account: { email: "a@example.com" }, status: "authenticated", refresh: vi.fn().mockResolvedValue(undefined) }),
  useAuthOptional: () => ({ status: "authenticated" }),
}));

import { DataPrivacyCenter } from "@/components/account/DataPrivacyCenter";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { ApiError } from "@/lib/api/errors";

const OPPS = [
  { id: 1, title: "PM at Acme", target_role: "PM", status: "active" },
  { id: 2, title: "Old role", target_role: "X", status: "archived" },
];
const DOCS = [{ id: 10, category: "cv", title: "My CV", status: "ready", current_version: 1 }];
const MEMS = [{ id: 20, category: "strength", summary: "Clear storyteller", target_role: null }];
const INTS = [{ id: 30, target_role: "Nurse", created_at: "2026-09-01T10:00:00Z", questions: 3 }];
const SHARES = [{ id: 40, owner_user_id: 1, workspace_id: 5, resource_type: "interview_report", resource_id: "30", permission: "view", status: "active", created_at: null, revoked_at: null }];

beforeEach(() => {
  opps.mockResolvedValue({ opportunities: OPPS });
  docs.mockResolvedValue({ documents: DOCS });
  mems.mockResolvedValue({ memories: MEMS });
  hist.mockResolvedValue({ interviews: INTS });
  sharesMine.mockResolvedValue({ shares: SHARES });
  wsList.mockResolvedValue({ workspaces: [{ id: 5, name: "Team Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
});
afterEach(() => vi.clearAllMocks());

const t = (k: string, v?: Record<string, string | number>) => translate("en", k, v);

describe("Data & Privacy Center", () => {
  it("F1/F2: renders the sections and real counts from the owner-scoped lists", async () => {
    render(<DataPrivacyCenter />);
    expect(screen.getByRole("heading", { level: 1, name: t("dataPrivacy.title") })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("dp-count-opps")).toHaveTextContent("2"));
    expect(screen.getByTestId("dp-count-docs")).toHaveTextContent("1");
    expect(screen.getByTestId("dp-count-mems")).toHaveTextContent("1");
    expect(screen.getByTestId("dp-count-ints")).toHaveTextContent("1");
    expect(screen.getByTestId("dp-count-shares")).toHaveTextContent("1");
    expect(screen.getByTestId("dp-count-spaces")).toHaveTextContent("1");
    for (const id of ["overview", "export", "manage", "sharing", "retention", "legal", "account"]) {
      expect(screen.getByTestId(`dp-${id}`)).toBeInTheDocument();
    }
  });

  it("F3: export is a real download link and states what is and is not included", async () => {
    render(<DataPrivacyCenter />);
    await waitFor(() => expect(screen.getByTestId("dp-count-opps")).toHaveTextContent("2"));
    const link = screen.getByTestId("dp-export-link");
    expect(link.getAttribute("href")).toMatch(/\/auth\/account\/export$/);
    expect(link).toHaveAttribute("download");
    expect(screen.getByText(t("dataPrivacy.excFiles"))).toBeInTheDocument();
    expect(screen.getByText(t("dataPrivacy.excLegal"))).toBeInTheDocument();
  });

  it("F4/F12: document delete needs confirmation; Cancel keeps data and default focus is Cancel", async () => {
    const user = userEvent.setup();
    render(<DataPrivacyCenter />);
    await user.click(await screen.findByRole("button", { name: `${t("dataPrivacy.deleteAction")}: My CV` }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const cancel = within(dialog).getByRole("button", { name: t("common.cancel") });
    expect(cancel).toHaveFocus(); // safe default, never the destructive button
    await user.click(cancel);
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(docRemove).not.toHaveBeenCalled();
    expect(screen.getByText("My CV")).toBeInTheDocument();
  });

  it("F4/F13: confirming deletes once and updates the list without a reload", async () => {
    const user = userEvent.setup();
    docRemove.mockResolvedValue({ deleted: true });
    render(<DataPrivacyCenter />);
    await user.click(await screen.findByRole("button", { name: `${t("dataPrivacy.deleteAction")}: My CV` }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: t("dataPrivacy.confirmDelete") }));
    await waitFor(() => expect(screen.queryByText("My CV")).not.toBeInTheDocument());
    expect(docRemove).toHaveBeenCalledTimes(1);
    expect(docRemove).toHaveBeenCalledWith(10);
    expect(screen.getByTestId("dp-count-docs")).toHaveTextContent("0");
    // unrelated data remains
    expect(await screen.findByText("Clear storyteller")).toBeInTheDocument();
    expect(await screen.findByText("PM at Acme")).toBeInTheDocument();
  });

  it("F5: memory delete works and leaves interviews alone", async () => {
    const user = userEvent.setup();
    memRemove.mockResolvedValue({ deleted: true });
    render(<DataPrivacyCenter />);
    await user.click(await screen.findByRole("button", { name: `${t("dataPrivacy.deleteAction")}: Clear storyteller` }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: t("dataPrivacy.confirmDelete") }));
    await waitFor(() => expect(screen.queryByText("Clear storyteller")).not.toBeInTheDocument());
    expect(histRemove).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId("dp-count-ints")).toHaveTextContent("1"));
  });

  it("F6: Opportunity archive and delete are distinct, honestly labelled actions", async () => {
    const user = userEvent.setup();
    oppArchive.mockResolvedValue({ ...OPPS[0], status: "archived" });
    render(<DataPrivacyCenter />);
    // The section container renders synchronously; its rows arrive with the async opportunities request.
    // Wait for the loaded Archive action itself (not just the container) before asserting the full state.
    const box = within(screen.getByTestId("dp-manage-opportunities"));
    expect(box.getByText(t("dataPrivacy.oppNote"))).toBeInTheDocument();
    // already archived item has no Archive action but does show an Archived badge
    expect(await box.findAllByRole("button", { name: new RegExp(`^${t("dataPrivacy.archiveAction")}:`) })).toHaveLength(1);
    expect(box.getByText(t("dataPrivacy.archivedBadge"))).toBeInTheDocument();
    await user.click(box.getByRole("button", { name: `${t("dataPrivacy.archiveAction")}: PM at Acme` }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(t("dataPrivacy.confirmArchiveOpportunityTitle"))).toBeInTheDocument();
    // archive confirm must NOT say delete / permanently
    expect(dialog.textContent).not.toMatch(/delete|for good/i);
    await user.click(within(dialog).getByRole("button", { name: t("dataPrivacy.confirmArchive") }));
    await waitFor(() => expect(oppArchive).toHaveBeenCalledWith(1));
    expect(oppRemove).not.toHaveBeenCalled();
    expect(await screen.findAllByText(t("dataPrivacy.archivedBadge"))).toHaveLength(2);
  });

  it("F7: interview delete works", async () => {
    const user = userEvent.setup();
    histRemove.mockResolvedValue({ deleted: true });
    render(<DataPrivacyCenter />);
    await user.click(await screen.findByRole("button", { name: new RegExp(`^${t("dataPrivacy.deleteAction")}: Nurse`) }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: t("dataPrivacy.confirmDelete") }));
    await waitFor(() => expect(histRemove).toHaveBeenCalledWith(30));
    await waitFor(() => expect(screen.getByTestId("dp-count-ints")).toHaveTextContent("0"));
  });

  it("F8: sharing is visible with workspace name and revoke does not claim erasure", async () => {
    const user = userEvent.setup();
    shareRevoke.mockResolvedValue({ status: "revoked" });
    render(<DataPrivacyCenter />);
    expect(await screen.findByText(t("dataPrivacy.sharedWith", { workspace: "Team Alpha" }))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: new RegExp(`^${t("dataPrivacy.revokeAction")}:`) }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.textContent).toContain("cannot be taken back");
    await user.click(within(dialog).getByRole("button", { name: t("dataPrivacy.confirmRevoke") }));
    await waitFor(() => expect(shareRevoke).toHaveBeenCalledWith(40));
    expect(await screen.findByText(t("dataPrivacy.sharingEmpty"))).toBeInTheDocument();
  });

  it("F9/F10: retention and legal sections render without invented periods or fake acceptance history", async () => {
    render(<DataPrivacyCenter />);
    await waitFor(() => expect(screen.getByTestId("dp-count-opps")).toHaveTextContent("2"));
    const retention = screen.getByTestId("dp-retention");
    expect(retention.textContent).not.toMatch(/\b\d+\s*(day|days|month|months|year|years)\b/i);
    const legal = screen.getByTestId("dp-legal");
    expect(within(legal).getByText(t("dataPrivacy.legalNotRecorded"))).toBeInTheDocument();
    expect(within(legal).getByRole("link", { name: t("dataPrivacy.legalPrivacy") })).toHaveAttribute("href", "/privacy");
    expect(legal.textContent).not.toMatch(/accepted:\s*version/i);
  });

  it("F11/F12: account deletion is a separate zone; cancel does nothing, confirm deletes and leaves", async () => {
    const user = userEvent.setup();
    deleteAccount.mockResolvedValue({ message: "ok" });
    render(<DataPrivacyCenter />);
    await user.click(screen.getByTestId("dp-delete-account"));
    let dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: t("dataPrivacy.accountConfirmKeep") })).toHaveFocus();
    expect(within(dialog).getByRole("link", { name: t("dataPrivacy.accountConfirmExport") })).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: t("dataPrivacy.accountConfirmKeep") }));
    expect(deleteAccount).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("dp-delete-account"));
    dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: t("dataPrivacy.accountConfirmDelete") }));
    await waitFor(() => expect(deleteAccount).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/sign-in"));
  });

  it("a failed delete shows an error inside the dialog, keeps the item and does not retry", async () => {
    const user = userEvent.setup();
    docRemove.mockRejectedValue(new ApiError({ kind: "unreachable", status: null, code: "x", message: "x", requestId: null, retryAfterMs: null }));
    render(<DataPrivacyCenter />);
    await user.click(await screen.findByRole("button", { name: `${t("dataPrivacy.deleteAction")}: My CV` }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: t("dataPrivacy.confirmDelete") }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toBeInTheDocument();
    expect(docRemove).toHaveBeenCalledTimes(1);
    expect(screen.getByText("My CV")).toBeInTheDocument();
  });

  it("F14: one failing section does not blank the page", async () => {
    docs.mockRejectedValue(new ApiError({ kind: "unreachable", status: null, code: "x", message: "x", requestId: "r1", retryAfterMs: null }));
    render(<DataPrivacyCenter />);
    const box = within(await screen.findByTestId("dp-manage-documents"));
    expect(await box.findByRole("alert")).toBeInTheDocument();
    expect(box.getByRole("button", { name: t("states.retry") })).toBeInTheDocument();
    // everything else still rendered (those sections load independently of the failed one)
    expect(await screen.findByText("PM at Acme")).toBeInTheDocument();
    expect(await screen.findByText("Clear storyteller")).toBeInTheDocument();
    expect(screen.getByTestId("dp-count-docs")).toHaveTextContent("-");
  });

  it("Escape closes the dialog without acting", async () => {
    const user = userEvent.setup();
    render(<DataPrivacyCenter />);
    await user.click(await screen.findByRole("button", { name: `${t("dataPrivacy.deleteAction")}: My CV` }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(docRemove).not.toHaveBeenCalled();
  });
});

describe("Data & Privacy copy across all 8 locales", () => {
  it("F15/F16/F17: every locale has every key (no raw keys, no English leak for the title) and the slogan stays exact", async () => {
    const enKeys = Object.keys((await import("@/lib/i18n/messages/w98/en")).default.dataPrivacy);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of enKeys) {
        const v = translate(locale, `dataPrivacy.${k}`, { name: "N", workspace: "W", id: 1 });
        expect(v, `${locale}.${k}`).not.toBe(`dataPrivacy.${k}`);
        expect(v.trim().length, `${locale}.${k}`).toBeGreaterThan(0);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/); // no em/en dash
      }
      if (locale !== "en") {
        expect(translate(locale, "dataPrivacy.title")).not.toBe(translate("en", "dataPrivacy.title"));
      }
      expect(translate(locale, "common.tagline")).toBe(BRAND_SLOGAN);
    }
  });

  it("renders the page in German and Russian with real translated headings and no raw keys", async () => {
    for (const locale of ["de", "ru"] as const) {
      const { unmount } = render(
        <I18nProvider initialLocale={locale}>
          <DataPrivacyCenter />
        </I18nProvider>,
      );
      expect(screen.getByRole("heading", { level: 1, name: translate(locale, "dataPrivacy.title") })).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId("dp-count-opps")).toHaveTextContent("2"));
      expect(document.body.textContent).not.toMatch(/dataPrivacy\./);
      unmount();
    }
  });
});
