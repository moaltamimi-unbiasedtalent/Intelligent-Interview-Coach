import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";

/** Pilot 2 P2-01: Workspaces must offer an obvious route to the canonical sharing-management surface (Data & Privacy). API mocked. */

const wsList = vi.fn();
const sharesMine = vi.fn();
const sharesWithMe = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    workspaces: { list: (...a: unknown[]) => wsList(...a) },
    shares: { mine: (...a: unknown[]) => sharesMine(...a), withMe: (...a: unknown[]) => sharesWithMe(...a), revoke: vi.fn() },
  },
}));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));

import { WorkspacesPanel } from "@/components/workspaces/WorkspacesPanel";
import { I18nProvider } from "@/components/i18n/I18nProvider";

const t = (k: string) => translate("en", k);

beforeEach(() => {
  wsList.mockResolvedValue({ workspaces: [], invited: [] });
  sharesMine.mockResolvedValue({ shares: [{ id: 1, owner_user_id: 1, workspace_id: 5, resource_type: "story", resource_id: "9", permission: "view", status: "active", created_at: null, revoked_at: null }] });
  sharesWithMe.mockResolvedValue({ shares: [] });
});
afterEach(() => vi.clearAllMocks());

describe("Workspaces -> manage sharing & access", () => {
  it("links the 'Shared by you' section to /account/data#sharing with an accessible name", async () => {
    render(<I18nProvider initialLocale="en"><WorkspacesPanel /></I18nProvider>);
    const link = await screen.findByRole("link", { name: t("workspaces.manageSharingLink") });
    expect(link).toHaveAttribute("href", "/account/data#sharing");
    const heading = screen.getByRole("heading", { name: t("workspaces.sharedByMe") });
    expect(heading.parentElement).toContainElement(link);         // the link sits with the shares it manages
  });

  it("shows the route even when nothing is shared yet, in German as well", async () => {
    sharesMine.mockResolvedValue({ shares: [] });
    const { unmount } = render(<I18nProvider initialLocale="en"><WorkspacesPanel /></I18nProvider>);
    await waitFor(() => expect(screen.getByRole("link", { name: t("workspaces.manageSharingLink") })).toHaveAttribute("href", "/account/data#sharing"));
    unmount();
    render(<I18nProvider initialLocale="de"><WorkspacesPanel /></I18nProvider>);
    const de = translate("de", "workspaces.manageSharingLink");
    expect(await screen.findByRole("link", { name: de })).toHaveAttribute("href", "/account/data#sharing");
    expect(de).not.toBe(t("workspaces.manageSharingLink"));
  });
});
