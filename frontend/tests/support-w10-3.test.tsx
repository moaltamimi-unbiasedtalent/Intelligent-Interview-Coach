import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";
import en103 from "@/lib/i18n/messages/w103/en";

// P10B-W10.3 candidate support. API mocked; nothing live. Async content is awaited with findBy*/waitFor.

let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  useSearchParams: () => new URLSearchParams(search),
  usePathname: () => "/support",
}));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("next/image", () => ({ default: (p: any) => <img alt={p.alt} /> }));

const create = vi.fn();
const list = vi.fn();
const get = vi.fn();
const reply = vi.fn();
vi.mock("@/lib/api/client", async (orig) => {
  const actual = await orig<typeof import("@/lib/api/client")>();
  return { ...actual, api: { support: { create: (...a: unknown[]) => create(...a), list: (...a: unknown[]) => list(...a), get: (...a: unknown[]) => get(...a), reply: (...a: unknown[]) => reply(...a) } } };
});

import { HelpPageContent } from "@/components/help/HelpPageContent";
import { SupportHome } from "@/components/support/SupportHome";
import { SupportTicketView } from "@/components/support/SupportTicketView";

const t = (k: string, v?: Record<string, string | number>) => translate("en", k, v);
const wrap = (ui: React.ReactElement) => render(<I18nProvider initialLocale="en">{ui}</I18nProvider>);

const ITEM = { public_id: "a".repeat(32), category: "technical", status: "waiting_for_customer", subject: "Cannot upload", created_at: "2026-10-01T10:00:00", updated_at: "2026-10-02T10:00:00" };
const DETAIL = (over = {}) => ({ ...ITEM, can_reply: true, messages: [
  { id: 1, author_kind: "candidate", body: "It fails every time.", created_at: "2026-10-01T10:00:00" },
  { id: 2, author_kind: "support", body: "Please try again after clearing the file.", created_at: "2026-10-02T10:00:00" },
], ...over });

beforeEach(() => {
  search = "";
  list.mockResolvedValue({ items: [ITEM], total: 1, page: 1, page_size: 20 });
  create.mockResolvedValue(ITEM);
  get.mockResolvedValue(DETAIL());
  reply.mockResolvedValue(DETAIL());
});
afterEach(() => vi.clearAllMocks());

async function fill(user: ReturnType<typeof userEvent.setup>, over: { cat?: string; subject?: string; message?: string } = {}) {
  await user.selectOptions(screen.getByLabelText(t("support.categoryLabel")), over.cat ?? "technical");
  await user.type(screen.getByLabelText(t("support.subjectLabel")), over.subject ?? "Cannot upload");
  await user.type(screen.getByLabelText(t("support.messageLabel")), over.message ?? "It fails every time.");
}

describe("Contact Support entry and form", () => {
  it("Help offers a Contact Support link to /support", async () => {
    wrap(<HelpPageContent />);
    expect(await screen.findByRole("link", { name: t("support.contactCta") })).toHaveAttribute("href", "/support");
  });

  it("has one h1, labelled fields, and honest notices (no email promise, no response-time promise)", async () => {
    wrap(<SupportHome />);
    expect(await screen.findByRole("heading", { level: 1, name: t("support.title") })).toBeInTheDocument();
    for (const k of ["categoryLabel", "subjectLabel", "messageLabel", "requestIdLabel"]) {
      expect(screen.getByLabelText(t(`support.${k}`))).toBeInTheDocument();
    }
    expect(screen.getByText(new RegExp(t("support.noticeNoPromise")))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/24\/7|within \d+ hours|\bSLA\b|guarantee/i);
  });

  it("validates required fields with associated errors, moves focus, and sends nothing", async () => {
    const user = userEvent.setup();
    wrap(<SupportHome />);
    await screen.findByRole("heading", { level: 1 });
    await user.click(screen.getByRole("button", { name: t("support.submit") }));
    const cat = screen.getByLabelText(t("support.categoryLabel"));
    expect(cat).toHaveAttribute("aria-invalid", "true");
    expect(cat).toHaveAccessibleDescription(t("support.errCategory"));
    expect(screen.getByLabelText(t("support.subjectLabel"))).toHaveAccessibleDescription(t("support.errRequired"));
    await waitFor(() => expect(cat).toHaveFocus());
    expect(create).not.toHaveBeenCalled();
  });

  it("enforces the 200 and 5000 character limits client-side too", async () => {
    const user = userEvent.setup();
    wrap(<SupportHome />);
    await screen.findByRole("heading", { level: 1 });
    await user.selectOptions(screen.getByLabelText(t("support.categoryLabel")), "other");
    await user.click(screen.getByLabelText(t("support.subjectLabel")));
    await user.paste("x".repeat(201));
    await user.click(screen.getByLabelText(t("support.messageLabel")));
    await user.paste("y".repeat(5001));
    await user.click(screen.getByRole("button", { name: t("support.submit") }));
    expect(screen.getByLabelText(t("support.subjectLabel"))).toHaveAccessibleDescription(t("support.errSubjectLong"));
    expect(screen.getByLabelText(t("support.messageLabel"))).toHaveAccessibleDescription(new RegExp(t("support.errMessageLong")));
    expect(create).not.toHaveBeenCalled();
  });

  it("creates a ticket, announces the reference, reloads the list and sends only the pathname of `from`", async () => {
    search = "from=%2Fdocuments%3Ftoken%3Dsecret%23x&ref=req-9";
    const user = userEvent.setup();
    wrap(<SupportHome />);
    await screen.findByRole("heading", { level: 1 });
    await fill(user);
    await user.click(screen.getByRole("button", { name: t("support.submit") }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create).toHaveBeenCalledWith({ category: "technical", subject: "Cannot upload", message: "It fails every time.", request_id: "req-9", source_route: "/documents" });
    expect(await screen.findByText(new RegExp(`Reference: ${ITEM.public_id}`))).toBeInTheDocument();
    expect(list.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByLabelText(t("support.subjectLabel"))).toHaveValue("");
  });

  it("a failed send keeps the text, shows an alert and is not retried automatically", async () => {
    create.mockRejectedValue(new Error("down"));
    const user = userEvent.setup();
    wrap(<SupportHome />);
    await screen.findByRole("heading", { level: 1 });
    await fill(user);
    await user.click(screen.getByRole("button", { name: t("support.submit") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t("support.errSubmit"));
    expect(screen.getByLabelText(t("support.messageLabel"))).toHaveValue("It fails every time.");
    expect(create).toHaveBeenCalledTimes(1);
  });
});

describe("Ticket list", () => {
  it("shows own tickets with status text and links to the detail page", async () => {
    wrap(<SupportHome />);
    const link = await screen.findByRole("link", { name: ITEM.subject });
    expect(link).toHaveAttribute("href", `/support/${ITEM.public_id}`);
    const row = link.closest("tr") as HTMLElement;
    expect(within(row).getByText(t("support.status_waiting_for_customer"))).toBeInTheDocument();
    expect(within(row).getByText(t("support.cat_technical"))).toBeInTheDocument();
  });

  it("shows an empty state, and an error state with a retry that refetches", async () => {
    list.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 });
    const { unmount } = wrap(<SupportHome />);
    expect(await screen.findByText(t("support.listEmpty"))).toBeInTheDocument();
    unmount();
    list.mockRejectedValueOnce(new Error("x"));
    const user = userEvent.setup();
    wrap(<SupportHome />);
    await user.click(await screen.findByRole("button", { name: t("support.retry") }));
    expect(await screen.findByRole("link", { name: ITEM.subject })).toBeInTheDocument();
  });

  it("paginates", async () => {
    list.mockResolvedValue({ items: [ITEM], total: 45, page: 1, page_size: 20 });
    const user = userEvent.setup();
    wrap(<SupportHome />);
    await screen.findByRole("link", { name: ITEM.subject });
    await user.click(screen.getByRole("button", { name: t("support.next") }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(2));
  });
});

describe("Ticket detail", () => {
  it("shows the reference, status and thread; support replies are labelled; no internal data", async () => {
    wrap(<SupportTicketView publicId={ITEM.public_id} />);
    expect(await screen.findByRole("heading", { level: 1, name: ITEM.subject })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ITEM.public_id))).toBeInTheDocument();
    const thread = screen.getByRole("list", { name: t("support.conversation") });
    expect(within(thread).getByText(t("support.team"), { exact: false })).toBeInTheDocument();
    expect(within(thread).getByText("Please try again after clearing the file.")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/internal note|priority|assignee/i);
  });

  it("renders HTML and script-like content as text, never as markup", async () => {
    const html = '<img src=x onerror="alert(1)"><script>alert(2)</script><b>bold</b>';
    get.mockResolvedValue(DETAIL({ subject: "<i>subj</i>", messages: [{ id: 1, author_kind: "candidate", body: html, created_at: null }] }));
    const { container } = wrap(<SupportTicketView publicId={ITEM.public_id} />);
    expect(await screen.findByText(html)).toBeInTheDocument();
    expect(container.querySelector("img, script, b, i")).toBeNull();
  });

  it("replies, shows the updated thread and clears the box; a failure keeps the text and is not retried", async () => {
    const user = userEvent.setup();
    wrap(<SupportTicketView publicId={ITEM.public_id} />);
    const box = await screen.findByLabelText(t("support.replyLabel"));
    reply.mockResolvedValueOnce(DETAIL({ messages: [...DETAIL().messages, { id: 3, author_kind: "candidate", body: "More details", created_at: null }] }));
    await user.type(box, "More details");
    await user.click(screen.getByRole("button", { name: t("support.replySend") }));
    expect(await screen.findByText("More details", { selector: "p.whitespace-pre-wrap" })).toBeInTheDocument();
    expect(reply).toHaveBeenCalledWith(ITEM.public_id, "More details");
    expect(box).toHaveValue("");
    reply.mockRejectedValue(new Error("down"));
    await user.type(box, "again");
    await user.click(screen.getByRole("button", { name: t("support.replySend") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t("support.errReply"));
    expect(box).toHaveValue("again");
    expect(reply).toHaveBeenCalledTimes(2);
  });

  it("a closed ticket explains it and offers no reply form", async () => {
    get.mockResolvedValue(DETAIL({ status: "closed", can_reply: false }));
    wrap(<SupportTicketView publicId={ITEM.public_id} />);
    expect(await screen.findByText(t("support.replyClosed"))).toBeInTheDocument();
    expect(screen.queryByLabelText(t("support.replyLabel"))).not.toBeInTheDocument();
  });

  it("a missing or foreign ticket shows a safe not-found, and a load error offers retry", async () => {
    const { ApiError } = await import("@/lib/api/client");
    get.mockRejectedValueOnce(new ApiError({ kind: "notFound", status: 404, code: "x", message: "x", requestId: null, retryAfterMs: null }));
    const { unmount } = wrap(<SupportTicketView publicId="nope" />);
    expect(await screen.findByText(t("support.notFound"))).toBeInTheDocument();
    unmount();
    get.mockRejectedValueOnce(new Error("boom"));
    const user = userEvent.setup();
    wrap(<SupportTicketView publicId={ITEM.public_id} />);
    await user.click(await screen.findByRole("button", { name: t("support.retry") }));
    expect(await screen.findByRole("heading", { level: 1, name: ITEM.subject })).toBeInTheDocument();
  });
});

describe("candidate support copy exists in all eight locales", () => {
  const keys = Object.keys(en103.support);
  it.each(SUPPORTED_LOCALE_CODES)("%s defines every support key and the export lines, without SLA claims", (locale) => {
    for (const k of keys) {
      const v = translate(locale, `support.${k}`);
      expect(v, `${locale}.support.${k}`).not.toBe(`support.${k}`);
      expect(v.trim().length).toBeGreaterThan(0);
    }
    for (const k of ["incSupport", "excSupportNotes"]) {
      expect(translate(locale, `dataPrivacy.${k}`)).not.toBe(`dataPrivacy.${k}`);
    }
    const all = keys.map((k) => translate(locale, `support.${k}`)).join(" ");
    expect(all).not.toMatch(/24\/7|\bSLA\b/i);
    expect(all).not.toContain(BRAND_SLOGAN);
    expect(translate(locale, "support.created", { ref: "R1" })).toContain("R1");
  });
});
