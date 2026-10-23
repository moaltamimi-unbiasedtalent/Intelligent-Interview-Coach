import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 03C bulk Admin user actions (provisional allow-list): select, explicit preview, mandatory reason, result with applied/skipped/failed, response-shape guards.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/users" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const users = vi.fn();
const preview = vi.fn();
const execute = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    users: (...a: unknown[]) => users(...a),
    bulkUserPreview: (...a: unknown[]) => preview(...a),
    bulkUserExecute: (...a: unknown[]) => execute(...a),
  } },
}));

import { UsersView } from "@/components/admin/UsersView";
import { isBulkUserPreview, isBulkUserResult } from "@/lib/admin/bulkGuard";

const REV = "0123456789abcdef";
const U = (id: number) => ({ user_id: id, email: `u${id}@example.com`, display_name: null, status: "active", platform_role: "user", tier: "basic",
  onboarding_completed: true, interface_locale: "en", email_verified: false, created_at: null, updated_at: null, workspace_count: 0, active_session_count: 1, last_activity: "7d" });
const PREVIEW = (over = {}) => ({ action: "force-signout", requested: 2, unique: 2, eligible: 1, excluded: 1,
  excluded_by_reason: { self: 0, higher_authority: 0, last_active_platform_admin: 0, not_found: 0, no_live_sessions: 1 }, max_batch: 100, preview_revision: REV, ...over });
const RESULT = (over = {}) => ({ action: "force-signout", batch_id: "b".repeat(16), status: "partial", requested: 2, unique: 2, applied: 1, skipped: 0,
  skipped_by_reason: {}, failed: 1, failed_by_reason: { apply_error: 1 }, replayed: false, ...over });

beforeEach(() => {
  mockPerms = ["platform.users.read", "platform.users.sessions.revoke", "platform.users.manage"];
  users.mockResolvedValue({ items: [U(1), U(2)], total: 2, page: 1, page_size: 25 });
  preview.mockResolvedValue(PREVIEW());
  execute.mockResolvedValue(RESULT());
});
afterEach(() => vi.clearAllMocks());

async function pick(user: ReturnType<typeof userEvent.setup>, ...ids: number[]) {
  await screen.findByRole("link", { name: "u1@example.com" });
  for (const id of ids) await user.click(screen.getByLabelText(`Select account ${id}`));
}

describe("selection and permissions", () => {
  it("shows no checkboxes and no bulk panel to a read-only role", async () => {
    mockPerms = ["platform.users.read"];
    render(<UsersView />);
    await screen.findByRole("link", { name: "u1@example.com" });
    expect(screen.queryByLabelText(/Select account/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Bulk actions/)).not.toBeInTheDocument();
  });

  it("offers only the actions the role holds the permission for", async () => {
    const user = userEvent.setup();
    mockPerms = ["platform.users.read", "platform.users.sessions.revoke"];
    render(<UsersView />);
    await pick(user, 1);
    const select = screen.getByLabelText("Action");
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["Choose an action", "Force sign-out"]);
  });

  it("the panel appears only once something is selected and never offers deactivation, deletion, role or plan changes", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await screen.findByRole("link", { name: "u1@example.com" });
    expect(screen.queryByText(/Bulk actions/)).not.toBeInTheDocument();
    await user.click(screen.getByLabelText(`Select account 1`));
    expect(screen.getByRole("heading", { name: /Bulk actions/ })).toBeInTheDocument();
    const options = within(screen.getByLabelText("Action")).getAllByRole("option").map((o) => o.textContent ?? "");
    expect(options.join(" ")).not.toMatch(/deactivate|delet|role|plan/i);
  });

  it("select-all selects the page and Clear selection empties it", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await screen.findByRole("link", { name: "u1@example.com" });
    await user.click(screen.getByLabelText("Select all accounts on this page"));
    expect(screen.getByText(/^2 selected/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(screen.queryByText(/Bulk actions/)).not.toBeInTheDocument();
  });
});

describe("preview, confirm, result", () => {
  it("previews counts only, requires a reason of 3 to 200 characters, sends the revision and an Idempotency-Key, then shows applied, skipped and failed", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await pick(user, 1, 2);
    await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    expect(preview).toHaveBeenCalledWith("force-signout", [1, 2]);
    expect(await screen.findByText("Preview: 1 of 2 accounts would be changed, 1 excluded.")).toBeInTheDocument();
    expect(screen.getByText(/1 accounts with no live session/)).toBeInTheDocument();
    expect(execute).not.toHaveBeenCalled();                 // a preview never applies anything
    await user.click(screen.getByRole("button", { name: "Apply to 1 accounts" }));
    const dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Apply" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("A reason is required.");
    await user.type(within(dialog).getByLabelText(/Reason/), "ab");
    await user.click(within(dialog).getByRole("button", { name: "Apply" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("3 to 200 characters");
    expect(execute).not.toHaveBeenCalled();
    await user.type(within(dialog).getByLabelText(/Reason/), "c");
    await user.click(within(dialog).getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(execute).toHaveBeenCalledTimes(1));
    const [action, body, key] = execute.mock.calls[0];
    expect(action).toBe("force-signout");
    expect(body).toEqual({ account_ids: [1, 2], preview_revision: REV, reason: "abc" });
    expect(String(key)).toMatch(/^bulk-[A-Za-z0-9_-]{8,}/);
    expect(await screen.findByText("Partly applied: some accounts were not changed.")).toBeInTheDocument();
    expect(screen.getByText("Applied 1, skipped 0, failed 1.")).toBeInTheDocument();
    expect(screen.getByText(/Failed: 1 accounts the server could not change/)).toBeInTheDocument();
  });

  it("a server refusal (stale preview) is shown in the dialog and not retried", async () => {
    const user = userEvent.setup();
    execute.mockRejectedValue(new Error("The selection changed since the preview. Preview again before applying."));
    render(<UsersView />);
    await pick(user, 1, 2);
    await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    await user.click(await screen.findByRole("button", { name: "Apply to 1 accounts" }));
    await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "operator review");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Apply" }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/changed since the preview/);
    expect(execute).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Applied/)).not.toBeInTheDocument();
  });

  it("changing the selection invalidates the preview", async () => {
    const user = userEvent.setup();
    render(<UsersView />);
    await pick(user, 1);
    await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    await screen.findByText(/Preview: /);
    await user.click(screen.getByLabelText("Select account 2"));
    expect(screen.queryByText(/Preview: /)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Apply to/ })).not.toBeInTheDocument();
  });

  it("an all-excluded preview cannot be applied", async () => {
    const user = userEvent.setup();
    preview.mockResolvedValue(PREVIEW({ eligible: 0, excluded: 2, excluded_by_reason: { self: 1, no_live_sessions: 1 } }));
    render(<UsersView />);
    await pick(user, 1, 2);
    await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    expect(await screen.findByRole("button", { name: "Apply to 0 accounts" })).toBeDisabled();
  });

  it("a complete result and a replayed result are labelled truthfully", async () => {
    const user = userEvent.setup();
    execute.mockResolvedValue(RESULT({ status: "complete", applied: 2, failed: 0, failed_by_reason: {}, replayed: true }));
    render(<UsersView />);
    await pick(user, 1, 2);
    await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
    await user.click(screen.getByRole("button", { name: "Preview effect" }));
    await user.click(await screen.findByRole("button", { name: "Apply to 1 accounts" }));
    await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "operator review");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Apply" }));
    expect(await screen.findByText(/Completed: every account was changed\./)).toBeInTheDocument();
    expect(screen.getByText(/earlier identical request/)).toBeInTheDocument();
  });
});

describe("malformed 200 responses are the explicit error state", () => {
  it.each([{}, { action: "force-signout" }, null, [], PREVIEW({ preview_revision: "not hex!" }), PREVIEW({ eligible: 5 }), PREVIEW({ excluded_by_reason: { self: "x" } })])(
    "a malformed preview %# shows an error and no Apply control", async (bad) => {
      const user = userEvent.setup();
      preview.mockResolvedValue(bad);
      render(<UsersView />);
      await pick(user, 1);
      await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
      await user.click(screen.getByRole("button", { name: "Preview effect" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/unexpected response/);
      expect(screen.queryByRole("button", { name: /Apply to/ })).not.toBeInTheDocument();
    });

  it.each([{}, { status: "complete" }, null, RESULT({ status: "weird" }), RESULT({ applied: 9 }), RESULT({ replayed: "no" })])(
    "a malformed execute response %# is an error inside the dialog, never a success panel", async (bad) => {
      const user = userEvent.setup();
      execute.mockResolvedValue(bad);
      render(<UsersView />);
      await pick(user, 1, 2);
      await user.selectOptions(screen.getByLabelText("Action"), "force-signout");
      await user.click(screen.getByRole("button", { name: "Preview effect" }));
      await user.click(await screen.findByRole("button", { name: "Apply to 1 accounts" }));
      await user.type(within(screen.getByRole("alertdialog")).getByLabelText(/Reason/), "operator review");
      await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Apply" }));
      expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/unexpected response/);
      expect(screen.queryByText(/Applied \d/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Completed|Partly applied|Nothing was changed/)).not.toBeInTheDocument();
    });
});

describe("type guards", () => {
  it("accept the documented shapes and reject drift", () => {
    expect(isBulkUserPreview(PREVIEW())).toBe(true);
    expect(isBulkUserResult(RESULT())).toBe(true);
    expect(isBulkUserPreview({ ...PREVIEW(), action: "deactivate" })).toBe(false);
    expect(isBulkUserResult({ ...RESULT(), action: "deactivate" })).toBe(false);
    expect(isBulkUserResult({ ...RESULT(), skipped_by_reason: [] })).toBe(false);
    expect(isBulkUserResult({ ...RESULT(), batch_id: "" })).toBe(false);
  });
});
