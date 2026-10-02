import { readFileSync, readdirSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.3 Admin support UI. Permissions are server-resolved; async content is awaited with findBy*/waitFor.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/support" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const tickets = vi.fn();
const ticket = vi.fn();
const assignees = vi.fn();
const assign = vi.fn();
const setStatus = vi.fn();
const setPriority = vi.fn();
const sendReply = vi.fn();
const sendNote = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    supportTickets: (...a: unknown[]) => tickets(...a), supportTicket: (...a: unknown[]) => ticket(...a),
    supportAssignees: (...a: unknown[]) => assignees(...a), supportAssign: (...a: unknown[]) => assign(...a),
    supportStatus: (...a: unknown[]) => setStatus(...a), supportPriority: (...a: unknown[]) => setPriority(...a),
    supportReply: (...a: unknown[]) => sendReply(...a), supportNote: (...a: unknown[]) => sendNote(...a),
  } },
}));

import { SupportQueueView } from "@/components/admin/SupportQueueView";
import { SupportTicketAdminView } from "@/components/admin/SupportTicketAdminView";

const ALL = ["platform.support.read", "platform.support.reply", "platform.support.manage", "platform.support.note"];
const ROW = { id: 5, public_id: "b".repeat(32), owner_user_id: 9, owner_email: "jane@example.com", category: "billing", priority: "normal",
  status: "new", subject: "Charged twice", assigned_user_id: null, assignee_email: null, message_count: 1,
  created_at: "2026-10-01T10:00:00", updated_at: "2026-10-02T10:00:00" };
const DETAIL = (over = {}) => ({
  ticket: { ...ROW, initial_request_id: "req-1", source_route: "/pricing", source_environment: "test", resolved_at: null, closed_at: null,
    allowed_statuses: ["triaged", "in_progress", "closed"] },
  messages: [{ id: 1, author_kind: "candidate", author_user_id: 9, body: "<b>please help</b>", request_id: "req-1", created_at: null }],
  internal_notes: [{ id: 2, author_user_id: 3, body: "Looks like a duplicate charge", request_id: null, created_at: null }],
  account: { user_id: 9, email: "jane@example.com", display_name: null, status: "active", platform_role: "user", tier: "basic",
    onboarding_completed: true, interface_locale: "en", email_verified: false, created_at: null, updated_at: null, workspace_count: 0, active_session_count: 1 },
  priorities: ["low", "normal", "high", "urgent"], statuses: [], ...over,
});

beforeEach(() => {
  mockPerms = ALL;
  tickets.mockResolvedValue({ items: [ROW], total: 60, page: 1, page_size: 25 });
  ticket.mockResolvedValue(DETAIL());
  assignees.mockResolvedValue([{ user_id: 3, email: "op@example.com", platform_role: "support_operator" }]);
  for (const m of [assign, setStatus, setPriority, sendReply, sendNote]) m.mockResolvedValue({});
});
afterEach(() => vi.clearAllMocks());

describe("Support queue", () => {
  it("lists tickets with links, labelled filters and server-side pagination", async () => {
    const user = userEvent.setup();
    render(<SupportQueueView />);
    const link = await screen.findByRole("link", { name: /Charged twice/ });
    expect(link).toHaveAttribute("href", `/admin/support/${ROW.public_id}`);
    expect(screen.getByText("Page 1 of 3 (60 total)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(tickets).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("applies the filters server-side and resets to page 1", async () => {
    const user = userEvent.setup();
    render(<SupportQueueView />);
    await screen.findByRole("link", { name: /Charged twice/ });
    await user.type(screen.getByLabelText("Reference, email or account id"), "jane");
    await user.selectOptions(screen.getByLabelText("Status"), "new");
    await user.selectOptions(screen.getByLabelText("Priority"), "urgent");
    await user.selectOptions(screen.getByLabelText("Assignee"), "unassigned");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(tickets).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "jane", status: "new", priority: "urgent", assignee: "unassigned", page: 1 })));
    expect(screen.getByText(/not message text/)).toBeInTheDocument();
  });

  it("shows an empty state, and without support.read renders no queue and fetches nothing", async () => {
    tickets.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 25 });
    const { unmount } = render(<SupportQueueView />);
    expect(await screen.findByText("No tickets match.")).toBeInTheDocument();
    unmount();
    mockPerms = ["platform.users.read"];
    tickets.mockClear();
    render(<SupportQueueView />);
    expect(await screen.findByText(/does not include access/)).toBeInTheDocument();
    expect(tickets).not.toHaveBeenCalled();
  });
});

describe("Support ticket detail", () => {
  it("shows ticket, safe requester metadata, visible messages and clearly separate internal notes - no private-content sections", async () => {
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    expect(await screen.findByRole("heading", { name: "Ticket" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Customer-visible messages" })).toHaveTextContent("<b>please help</b>");
    const notes = screen.getByRole("list", { name: "Internal notes" });
    expect(notes).toHaveTextContent("Looks like a duplicate charge");
    expect(screen.getByRole("heading", { name: "Internal notes (never visible to the candidate)" })).toBeInTheDocument();
    expect(screen.getByText("Internal note", { exact: false, selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/does not promise a response time/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/curriculum vitae|interview answer text|memory summary|token/i);
    expect(document.querySelector("b")).toBeNull();           // HTML shown as text, not markup
  });

  it("a read-only role (support.read only) sees no controls", async () => {
    mockPerms = ["platform.support.read"];
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    await screen.findByRole("heading", { name: "Ticket" });
    for (const label of ["Move to", "Priority", "Assignee"]) expect(screen.queryByLabelText(label)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Reply \(the candidate/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Internal note (staff only)")).not.toBeInTheDocument();
  });

  it("changes status through a confirmation that defaults to Cancel, then calls the API once", async () => {
    const user = userEvent.setup();
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    await user.selectOptions(await screen.findByLabelText("Move to"), "triaged");
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Change status" }));
    await waitFor(() => expect(setStatus).toHaveBeenCalledWith(ROW.public_id, "triaged"));
    expect(setStatus).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Status changed to triaged.")).toBeInTheDocument();
  });

  it("changes priority and warns that no response time is implied", async () => {
    const user = userEvent.setup();
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    await user.selectOptions(await screen.findByLabelText("Priority"), "urgent");
    expect(within(screen.getByRole("alertdialog")).getByText(/promises nothing/)).toBeInTheDocument();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Change priority" }));
    await waitFor(() => expect(setPriority).toHaveBeenCalledWith(ROW.public_id, "urgent"));
  });

  it("assigns from the eligible-operator list and can unassign", async () => {
    const user = userEvent.setup();
    ticket.mockResolvedValue(DETAIL({ ticket: { ...DETAIL().ticket, assigned_user_id: 3, assignee_email: "op@example.com" } }));
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    const select = await screen.findByLabelText("Assignee");
    await user.click(select);
    await screen.findByRole("option", { name: "op@example.com" });
    await user.selectOptions(select, "3");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(ROW.public_id, 3));
    await user.selectOptions(select, "none");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(assign).toHaveBeenLastCalledWith(ROW.public_id, null));
  });

  it("sends a customer-visible reply and saves a separate internal note", async () => {
    const user = userEvent.setup();
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    await user.type(await screen.findByLabelText(/Reply \(the candidate/), "We refunded the duplicate.");
    await user.click(screen.getByRole("button", { name: "Send reply to candidate" }));
    await waitFor(() => expect(sendReply).toHaveBeenCalledWith(ROW.public_id, "We refunded the duplicate."));
    expect(await screen.findByText(/candidate sees it/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Internal note (staff only)"), "Checked billing logs");
    await user.click(screen.getByRole("button", { name: "Save internal note" }));
    await waitFor(() => expect(sendNote).toHaveBeenCalledWith(ROW.public_id, "Checked billing logs"));
    expect(sendReply).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/never shown to the candidate/)).toBeInTheDocument();
  });

  it("a failed reply shows an alert, keeps the text and is not retried", async () => {
    const user = userEvent.setup();
    sendReply.mockRejectedValue(new Error("This ticket is closed."));
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    const box = await screen.findByLabelText(/Reply \(the candidate/);
    await user.type(box, "hello");
    await user.click(screen.getByRole("button", { name: "Send reply to candidate" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This ticket is closed.");
    expect(box).toHaveValue("hello");
    expect(sendReply).toHaveBeenCalledTimes(1);
  });

  it("an assigned ticket whose assignee has no email still shows as assigned, not Unassigned", async () => {
    ticket.mockResolvedValue(DETAIL({ ticket: { ...DETAIL().ticket, assigned_user_id: 12, assignee_email: null } }));
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    expect(await screen.findByText("Account 12")).toBeInTheDocument();
    expect(screen.queryByText("Unassigned")).not.toBeInTheDocument();
  });

  it("a closed ticket offers no status, priority, assignee or reply controls", async () => {
    ticket.mockResolvedValue(DETAIL({ ticket: { ...DETAIL().ticket, status: "closed", allowed_statuses: [] } }));
    render(<SupportTicketAdminView reference={ROW.public_id} />);
    await screen.findByRole("heading", { name: "Ticket" });
    expect(screen.queryByLabelText("Move to")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Reply \(the candidate/)).not.toBeInTheDocument();
  });
});

describe("authorisation is by permission", () => {
  it("support admin components contain no role-name checks, no storage and no raw next/link", () => {
    for (const f of readdirSync("components/admin").filter((n) => /Support/.test(n))) {
      const src = readFileSync(`components/admin/${f}`, "utf8");
      expect(src, f).not.toMatch(/platform_role\s*===|===\s*"platform_admin"|localStorage|sessionStorage/);
      expect(src, f).not.toContain('from "next/link"');
    }
  });
});
