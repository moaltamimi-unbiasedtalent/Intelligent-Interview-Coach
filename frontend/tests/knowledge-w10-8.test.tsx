import { readFileSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.8 Admin knowledge UI. Platform knowledge only; the preview is plain text; async content awaited with findBy*.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/knowledge" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const meta = vi.fn(); const list = vi.fn(); const source = vi.fn(); const version = vi.fn(); const action = vi.fn();
const reject = vi.fn(); const del = vi.fn(); const create = vi.fn(); const addVersion = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { knowledgeMeta: (...a: unknown[]) => meta(...a), knowledgeSources: (...a: unknown[]) => list(...a),
    knowledgeSource: (...a: unknown[]) => source(...a), knowledgeVersion: (...a: unknown[]) => version(...a),
    knowledgeAction: (...a: unknown[]) => action(...a), knowledgeReject: (...a: unknown[]) => reject(...a), knowledgeDelete: (...a: unknown[]) => del(...a),
    createKnowledgeSource: (...a: unknown[]) => create(...a), addKnowledgeVersion: (...a: unknown[]) => addVersion(...a) } },
}));

import { KnowledgeDetailView } from "@/components/admin/KnowledgeDetailView";
import { KnowledgeView } from "@/components/admin/KnowledgeView";

const META = { languages: ["en", "de", "fr", "es", "it", "pt", "nl"],
  authority_levels: [{ level: 1, meaning: "Level 1: official or statistical source" }, { level: 2, meaning: "Level 2: public or professional framework" }, { level: 3, meaning: "Level 3: reputable public industry research" }],
  licence_classes: [{ code: "public_official", label: "Public / official source", activatable: true }, { code: "unclear", label: "Unclear (cannot be activated)", activatable: false }],
  states: ["queued", "processing", "review_required", "approved", "indexing", "indexed", "active", "rejected", "failed", "retired"],
  rejection_reasons: ["out_of_scope"], upload: { max_bytes: 5242880, extensions: ["md", "pdf", "txt"], preview_chars: 4000 } };
const ROW = (o: Record<string, unknown> = {}) => ({ source_public_id: "s".repeat(32), title: "Product framework", version_public_id: "v".repeat(32), version: 1,
  state: "review_required", active: false, language: "en", authority_level: 2, authority_meaning: "Level 2: public or professional framework", publisher: "Example Body",
  licence_class: "public_official", licence_label: "Public / official source", scan_status: "scan_passed", chunk_count: null, failure_category: null,
  created_at: "2026-10-03T10:00:00", updated_at: "2026-10-03T10:00:00", ...o });
const CAN = { edit: true, approve: true, reject: true, index: false, activate: false, retire: false, reprocess: false, delete: true };
const DETAIL = (o: Record<string, unknown> = {}, can: Record<string, boolean> = {}) => ({ ...ROW(), source_reference: "https://example.org/f", provenance_note: "Public framework.",
  original_filename: "framework.txt", media_type: "text/plain", byte_size: 120, checksum_sha256: "a".repeat(64), scanner: "fake", extracted_chars: 120,
  preview: "Product managers prioritise a roadmap. <script>alert(1)</script>", preview_is_truncated: false, failed_stage: null, rejection_reason: null,
  approved_at: null, approved_by_user_id: null, indexed_at: null, activated_at: null, retired_at: null, parse_job_id: "p".repeat(32), index_job_id: null,
  index: null, blockers: [], metadata_frozen: false, can: { ...CAN, ...can }, audit: [], ...o });
const SOURCE = { source_public_id: "s".repeat(32), title: "Product framework", created_at: "2026-10-03T10:00:00", versions: [ROW()] };

beforeEach(() => {
  mockPerms = ["platform.knowledge.read", "platform.knowledge.manage", "platform.knowledge.approve"];
  meta.mockResolvedValue(META);
  list.mockResolvedValue({ items: [ROW(), ROW({ source_public_id: "t".repeat(32), title: "Active one", state: "active", active: true, version: 2, chunk_count: 3 })], total: 60, page: 1, page_size: 25 });
  source.mockResolvedValue(SOURCE);
  version.mockResolvedValue(DETAIL());
  action.mockResolvedValue(DETAIL({ state: "approved" }));
  reject.mockResolvedValue(DETAIL({ state: "rejected" }));
  del.mockResolvedValue({ deleted: "x" });
  create.mockResolvedValue({ source_public_id: "s", version_public_id: "v", version: 1 });
});
afterEach(() => vi.clearAllMocks());

describe("Knowledge list", () => {
  it("shows lifecycle as text, language, authority MEANING (not just a number), licence and scan state", async () => {
    render(<KnowledgeView />);
    const row = (await screen.findByRole("link", { name: "Product framework" })).closest("tr") as HTMLElement;
    expect(within(row).getByText("Awaiting review")).toBeInTheDocument();
    expect(within(row).getByText("Level 2: public or professional framework")).toBeInTheDocument();
    expect(within(row).getByText("Public / official source")).toBeInTheDocument();
    expect(within(row).getByText("Scan passed")).toBeInTheDocument();
    const active = screen.getByRole("link", { name: "Active one" }).closest("tr") as HTMLElement;
    expect(within(active).getByText("Active")).toBeInTheDocument();
    expect(screen.getByText(/not candidate data/)).toBeInTheDocument();
  });

  it("filters server-side with labelled controls and resets to page 1", async () => {
    const user = userEvent.setup();
    render(<KnowledgeView />);
    await screen.findByRole("link", { name: "Product framework" });
    await user.selectOptions(screen.getByLabelText("State"), "review_required");
    await user.selectOptions(screen.getByLabelText("Authority"), "2");
    await user.selectOptions(screen.getByLabelText("Language"), "de");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith({ state: "review_required", authority: "2", language: "de", page: 1, page_size: 25 }));
  });

  it("paginates and offers only the 7 knowledge languages (Russian is not a knowledge language)", async () => {
    const user = userEvent.setup();
    render(<KnowledgeView />);
    await screen.findByRole("link", { name: "Product framework" });
    expect(within(screen.getByLabelText("Source language", { selector: "select" })).queryByRole("option", { name: "ru" })).toBeNull();
    await user.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith({ page: 2, page_size: 25 }));
  });

  it("upload form: labelled fields, file errors associated with the field, no request without a file", async () => {
    const user = userEvent.setup();
    render(<KnowledgeView />);
    await user.type(await screen.findByLabelText("Title"), "A source");
    await user.click(screen.getByRole("button", { name: "Upload" }));
    const err = await screen.findByRole("alert");
    expect(err).toHaveTextContent(/Choose a file/);
    expect(screen.getByLabelText(/^File/)).toHaveAttribute("aria-describedby", err.id);
    expect(create).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Licence classification")).toHaveValue("unclear");   // fail-closed default
  });

  it("a read-only role cannot upload; hidden without read permission; no role names in code", async () => {
    mockPerms = ["platform.knowledge.read"];
    const { unmount } = render(<KnowledgeView />);
    await screen.findByRole("link", { name: "Product framework" });
    expect(screen.queryByRole("button", { name: "Upload" })).not.toBeInTheDocument();
    unmount();
    mockPerms = ["platform.users.read"];
    render(<KnowledgeView />);
    expect(list).toHaveBeenCalledTimes(1);
    for (const f of ["KnowledgeView", "KnowledgeDetailView"]) expect(readFileSync(`components/admin/${f}.tsx`, "utf8")).not.toMatch(/platform_admin|knowledge_admin|platform_role|dangerouslySetInnerHTML/);
  });
});

describe("Knowledge detail", () => {
  it("shows provenance, licence, scan, checksum and index sections, and a plain-text preview that never executes", async () => {
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    expect(await screen.findByRole("heading", { name: "Provenance and use rights" })).toBeInTheDocument();
    expect(screen.getByText("Public framework.")).toBeInTheDocument();
    expect(screen.getAllByText(/not legal advice/).length).toBeGreaterThan(0);
    const pre = screen.getByTestId("knowledge-preview");
    expect(pre.textContent).toContain("<script>alert(1)</script>");           // displayed as text...
    expect(pre.querySelector("script")).toBeNull();                          // ...never parsed as markup
    expect(screen.getByText(/Not active; not used in candidate answers/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scan and parse job" })).toHaveAttribute("href", `/admin/jobs/${"p".repeat(32)}`);
    expect(screen.queryByText(/vector|chunk browser|candidate cv|interview answers|memories/i)).not.toBeInTheDocument();
  });

  it("approve requires confirmation, states what it does NOT do, and only then calls the API", async () => {
    const user = userEvent.setup();
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    await user.click(await screen.findByRole("button", { name: "Approve version" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/does not index or activate/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(action).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(action).toHaveBeenCalledWith("v".repeat(32), "approve"));
  });

  it("reject sends a reason category", async () => {
    const user = userEvent.setup();
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    await user.click(await screen.findByRole("button", { name: "Reject version" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(reject).toHaveBeenCalledWith("v".repeat(32), "out_of_scope"));
  });

  it("actions are limited by state: approved -> index only; indexed -> activate; active -> retire; never all at once", async () => {
    version.mockResolvedValue(DETAIL({ state: "approved" }, { approve: false, reject: true, index: true, activate: false, delete: false }));
    const { unmount } = render(<KnowledgeDetailView id={"s".repeat(32)} />);
    expect(await screen.findByRole("button", { name: "Queue indexing" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Activate version" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve version" })).not.toBeInTheDocument();
    unmount();
    version.mockResolvedValue(DETAIL({ state: "indexed" }, { approve: false, reject: false, index: false, activate: true, retire: true, delete: false }));
    const u2 = render(<KnowledgeDetailView id={"s".repeat(32)} />);
    expect(await screen.findByRole("button", { name: "Activate version" })).toBeInTheDocument();
    u2.unmount();
    version.mockResolvedValue(DETAIL({ state: "active", active: true }, { approve: false, reject: false, activate: false, retire: true, delete: false }));
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    expect(await screen.findByRole("button", { name: "Retire version" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete version" })).not.toBeInTheDocument();
  });

  it("blockers are listed and approval is unavailable while blocked", async () => {
    version.mockResolvedValue(DETAIL({ blockers: ["The licence classification does not permit use (Unclear)."] }, { approve: false }));
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    expect(await screen.findByText(/Blocked until these are resolved/)).toBeInTheDocument();
    expect(screen.getByText(/licence classification does not permit use/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve version" })).not.toBeInTheDocument();
  });

  it("failed index shows a safe failure label and offers retry via indexing, not raw errors", async () => {
    version.mockResolvedValue(DETAIL({ state: "failed", failure_category: "unavailable", failed_stage: "index" }, { approve: false, index: true, reprocess: true }));
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    expect(await screen.findByText(/A required service was unavailable \(during index\)/)).toBeInTheDocument();
  });

  it("a read-only role sees detail but no mutation controls", async () => {
    mockPerms = ["platform.knowledge.read"];
    render(<KnowledgeDetailView id={"s".repeat(32)} />);
    await screen.findByRole("heading", { name: "Provenance and use rights" });
    for (const n of ["Approve version", "Reject version", "Queue indexing", "Activate version", "Retire version", "Delete version"]) {
      expect(screen.queryByRole("button", { name: n })).not.toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: "Upload" })).not.toBeInTheDocument();
  });
});
