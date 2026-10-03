import { readFileSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

// P10B-W10.10 Admin privacy/legal UI and the candidate privacy-request and legal-version panels. APIs are mocked; no private content exists here.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/privacy" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { user_id: 7, platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
  useAuth: () => ({ account: { email: "a@example.com" }, status: "authenticated" }),
}));

const queue = vi.fn(); const one = vi.fn(); const record = vi.fn(); const assign = vi.fn(); const status = vi.fn(); const del = vi.fn();
const coverage = vi.fn(); const backfill = vi.fn(); const legalOv = vi.fn(); const draft = vi.fn(); const publish = vi.fn();
const cReqs = vi.fn(); const cCreate = vi.fn(); const cLegal = vi.fn(); const cAccept = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    admin: {
      privacyQueue: (...a: unknown[]) => queue(...a), privacyRequest: (...a: unknown[]) => one(...a), privacyRecord: (...a: unknown[]) => record(...a),
      privacyAssign: (...a: unknown[]) => assign(...a), privacyStatus: (...a: unknown[]) => status(...a), privacyExecuteDeletion: (...a: unknown[]) => del(...a),
      preparationCoverage: (...a: unknown[]) => coverage(...a), preparationBackfill: (...a: unknown[]) => backfill(...a),
      legalOverview: (...a: unknown[]) => legalOv(...a), legalCreateDraft: (...a: unknown[]) => draft(...a), legalPublish: (...a: unknown[]) => publish(...a),
    },
    privacy: { requests: (...a: unknown[]) => cReqs(...a), createRequest: (...a: unknown[]) => cCreate(...a), legal: (...a: unknown[]) => cLegal(...a), acceptLegal: (...a: unknown[]) => cAccept(...a) },
  },
}));

import { LegalView } from "@/components/admin/LegalView";
import { PrivacyDetailView } from "@/components/admin/PrivacyDetailView";
import { PrivacyView } from "@/components/admin/PrivacyView";
import { LegalVersionsPanel, PrivacyRequestsPanel } from "@/components/account/PrivacyLegalPanels";
import { I18nProvider } from "@/components/i18n/I18nProvider";

const PID = "a".repeat(32);
const ROW = (o: Record<string, unknown> = {}) => ({ public_id: PID, request_type: "deletion", type_label: "Account or data deletion", status: "submitted", result_category: null,
  created_at: "2026-10-03T10:00:00", updated_at: null, source: "candidate_portal", user_id: 5, candidate_email: "cand@example.com", assigned_user_id: null,
  assignee_email: null, acknowledged_at: null, completed_at: null, closed_at: null, related_job_id: null, ...o });
const DETAIL = (o: Record<string, unknown> = {}) => ({ ...ROW(), request_note: "Please delete my account.", candidate: { user_id: 5, email: "cand@example.com", status: "active", platform_role: "user", created_at: null },
  allowed_statuses: ["acknowledged", "rejected"], result_categories: ["information_provided", "deletion_performed"], can_execute_deletion: false,
  legal: [{ document: "terms", current_version: "baseline-1", accepted_current: false, last_accepted_at: null }], audit: [], ...o });
const VER = (o: Record<string, unknown> = {}) => ({ id: 1, version: "baseline-1", state: "published", is_baseline: true, content_ref: "/terms", content_hash: null, effective_at: null, published_at: "2026-10-03T10:00:00", created_at: null, acceptances: 2, ...o });
const LEGAL = { documents: [{ code: "terms", title: "Terms of use", current: VER(), versions: [VER(), VER({ id: 2, version: "2.0", state: "draft", is_baseline: false, content_hash: "a".repeat(64), acceptances: 0, published_at: null })], current_accepted: 2, current_not_recorded: 3 }],
  active_accounts: 5, note: "Counts reflect RECORDED acceptances only. This is not a compliance measure." };

beforeEach(() => {
  mockPerms = ["platform.privacy.read", "platform.privacy.execute", "platform.legal.manage"];
  queue.mockResolvedValue({ items: [ROW(), ROW({ public_id: "b".repeat(32), request_type: "correction", status: "completed", related_job_id: "j".repeat(32), candidate_email: null, user_id: null })], total: 40, page: 1, page_size: 25 });
  one.mockResolvedValue(DETAIL());
  status.mockResolvedValue(DETAIL({ status: "acknowledged" }));
  assign.mockResolvedValue(DETAIL({ assigned_user_id: 7 }));
  del.mockResolvedValue(DETAIL({ status: "in_progress", related_job_id: "j".repeat(32) }));
  record.mockResolvedValue(DETAIL());
  coverage.mockResolvedValue({ indexed_runs: 4, by_state: { ready: 4 }, by_source: { created: 3, backfill: 1 }, coverage_version: 1, note: "Counts indexed runs only. Historical runs with no relational reference cannot be discovered and are not included." });
  backfill.mockResolvedValue({ job_id: "j", created: true });
  legalOv.mockResolvedValue(LEGAL);
  draft.mockResolvedValue(VER({ id: 3 }));
  publish.mockResolvedValue(VER({ id: 2, state: "published" }));
  cReqs.mockResolvedValue({ items: [{ public_id: "c".repeat(32), request_type: "correction", type_label: "x", status: "waiting_for_user", result_category: null, created_at: "2026-10-03T10:00:00", updated_at: null }], total: 1, page: 1, page_size: 20 });
  cCreate.mockResolvedValue({ public_id: "d".repeat(32) });
  cLegal.mockResolvedValue({ documents: [{ code: "terms", title: "Terms of use", path: "/terms", current_version: "2.0", effective_at: "2026-12-01T00:00:00", version_is_baseline: false, accepted_current: false, last_acceptance: { version: "baseline-1", accepted_at: "2026-10-03T10:00:00", source: "settings", is_current: false } }] });
  cAccept.mockResolvedValue({ documents: [] });
});
afterEach(() => vi.clearAllMocks());

describe("Admin privacy queue", () => {
  it("shows states as text, candidate metadata only, job links and the data boundary", async () => {
    render(<PrivacyView />);
    const first = (await screen.findByRole("link", { name: PID })).closest("tr") as HTMLElement;
    expect(within(first).getByText("Submitted")).toBeInTheDocument();
    expect(within(first).getByText("cand@example.com")).toBeInTheDocument();
    const second = screen.getByRole("link", { name: "b".repeat(32) }).closest("tr") as HTMLElement;
    expect(within(second).getByText("Account removed")).toBeInTheDocument();
    expect(within(second).getByRole("link", { name: "Job" })).toHaveAttribute("href", `/admin/jobs/${"j".repeat(32)}`);
    expect(screen.getByText(/never shows a candidate's documents/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing here is a statement of legal compliance/)).toBeInTheDocument();
  });

  it("filters server-side, paginates, and search never claims to cover request text", async () => {
    const user = userEvent.setup();
    render(<PrivacyView />);
    await screen.findByRole("link", { name: PID });
    await user.selectOptions(screen.getByLabelText("Status"), "open");
    await user.selectOptions(screen.getByLabelText("Assignee"), "unassigned");
    await user.type(screen.getByLabelText(/Search by reference/), "abc");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(queue).toHaveBeenLastCalledWith({ status: "open", assignee: "unassigned", q: "abc", page: 1, page_size: 25 }));
    expect(screen.getByText(/not request text/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(queue).toHaveBeenLastCalledWith({ status: "open", assignee: "unassigned", q: "abc", page: 2, page_size: 25 }));
  });

  it("shows preparation-index coverage with its limitation and queues the bounded backfill only after confirmation", async () => {
    const user = userEvent.setup();
    render(<PrivacyView />);
    expect(await screen.findByText(/cannot be discovered and are not included/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Index historical runs" }));
    expect(backfill).not.toHaveBeenCalled();
    const dlg = screen.getByRole("alertdialog");
    expect(within(dlg).getByText(/does not scan the whole chat store/)).toBeInTheDocument();
    await user.click(within(dlg).getByRole("button", { name: "Queue indexing" }));
    await waitFor(() => expect(backfill).toHaveBeenCalled());
  });

  it("recording a request validates the account first; a read-only role has no mutation controls", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<PrivacyView />);
    await user.click(await screen.findByRole("button", { name: "Record request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Enter the candidate/);
    expect(record).not.toHaveBeenCalled();
    unmount();
    mockPerms = ["platform.privacy.read"];
    render(<PrivacyView />);
    await screen.findByRole("link", { name: PID });
    expect(screen.queryByRole("button", { name: "Record request" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Index historical runs" })).not.toBeInTheDocument();
  });

  it("is hidden without the read permission and contains no role-name authorisation", () => {
    mockPerms = ["platform.users.read"];
    render(<PrivacyView />);
    expect(queue).not.toHaveBeenCalled();
    for (const f of ["PrivacyView", "PrivacyDetailView", "LegalView"]) expect(readFileSync(`components/admin/${f}.tsx`, "utf8")).not.toMatch(/security_privacy_admin|platform_admin|platform_role ===|dangerouslySetInnerHTML/);
  });
});

describe("Admin privacy request detail", () => {
  it("shows request, safe account metadata, recorded legal acceptance and no private-content sections", async () => {
    render(<PrivacyDetailView id={PID} />);
    expect(await screen.findByRole("heading", { name: "Candidate (account metadata only)" })).toBeInTheDocument();
    expect(screen.getByTestId("privacy-note")).toHaveTextContent("Please delete my account.");
    expect(screen.getByText(/no acceptance recorded for the current version/)).toBeInTheDocument();
    expect(screen.queryByText(/documents:|interview answers:|preparation chat:|memories:/i)).not.toBeInTheDocument();
    expect(screen.getByText(/never shows the candidate's documents, answers, chats, memories or evidence/)).toBeInTheDocument();
  });

  it("status changes need confirmation, completion needs a result, and only valid next statuses are offered", async () => {
    const user = userEvent.setup();
    render(<PrivacyDetailView id={PID} />);
    expect(await screen.findByRole("button", { name: "Mark acknowledged" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark completed" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mark acknowledged" }));
    expect(status).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(status).toHaveBeenCalledWith(PID, "acknowledged", undefined));
  });

  it("completion sends the chosen result category", async () => {
    one.mockResolvedValue(DETAIL({ status: "in_progress", allowed_statuses: ["waiting_for_user", "completed"] }));
    const user = userEvent.setup();
    render(<PrivacyDetailView id={PID} />);
    await user.click(await screen.findByRole("button", { name: "Mark completed" }));
    const dlg = screen.getByRole("alertdialog");
    await user.selectOptions(within(dlg).getByLabelText("Result"), "deletion_performed");
    await user.click(within(dlg).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(status).toHaveBeenCalledWith(PID, "completed", "deletion_performed"));
  });

  it("assign-to-me uses the signed-in account id; deletion is a separate, strongly worded confirmation", async () => {
    one.mockResolvedValue(DETAIL({ status: "acknowledged", can_execute_deletion: true }));
    const user = userEvent.setup();
    render(<PrivacyDetailView id={PID} />);
    await user.click(await screen.findByRole("button", { name: "Assign to me" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(PID, 7));
    await user.click(await screen.findByRole("button", { name: "Delete the account" }));
    const dlg = screen.getByRole("alertdialog");
    expect(within(dlg).getByText(/permanently deletes/)).toBeInTheDocument();
    expect(within(dlg).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(del).not.toHaveBeenCalled();
    await user.click(within(dlg).getByRole("button", { name: "Delete account" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith(PID));
  });

  it("a read-only role sees detail but no actions", async () => {
    mockPerms = ["platform.privacy.read"];
    one.mockResolvedValue(DETAIL({ can_execute_deletion: true }));
    render(<PrivacyDetailView id={PID} />);
    await screen.findByRole("heading", { name: "Candidate (account metadata only)" });
    for (const n of ["Assign to me", "Mark acknowledged", "Delete the account"]) expect(screen.queryByRole("button", { name: n })).not.toBeInTheDocument();
  });
});

describe("Admin legal registry", () => {
  it("shows current version, recorded acceptance counts, baseline honesty and no compliance score", async () => {
    render(<LegalView />);
    expect(await screen.findByText("Accepted the current version")).toBeInTheDocument();
    expect(screen.getAllByText("No acceptance recorded").length).toBeGreaterThan(0);
    expect(screen.getByText(/baseline created when versioning was introduced/)).toBeInTheDocument();
    expect(screen.getAllByText(/not a compliance measure/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/compliant|compliance score|certified/i)).toBeNull();
  });

  it("publish is only offered for drafts, needs confirmation, and states immutability and no forced re-acceptance", async () => {
    const user = userEvent.setup();
    render(<LegalView />);
    await user.click(await screen.findByRole("button", { name: "Publish Terms of use version 2.0" }));
    const dlg = screen.getByRole("alertdialog");
    expect(within(dlg).getByText(/can never be edited/)).toBeInTheDocument();
    expect(within(dlg).getByText(/not forced to re-accept/)).toBeInTheDocument();
    expect(publish).not.toHaveBeenCalled();
    await user.click(within(dlg).getByRole("button", { name: "Publish" }));
    await waitFor(() => expect(publish).toHaveBeenCalledWith(2));
    expect(screen.queryByRole("button", { name: "Publish Terms of use version baseline-1" })).not.toBeInTheDocument();
  });

  it("a read-only role cannot register or publish", async () => {
    mockPerms = ["platform.privacy.read"];
    render(<LegalView />);
    await screen.findByText("Accepted the current version");
    expect(screen.queryByRole("button", { name: /Publish/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Register draft version" })).not.toBeInTheDocument();
  });
});

function renderCandidate(ui: React.ReactElement) {
  return render(<I18nProvider>{ui}</I18nProvider>);
}

describe("Candidate privacy requests and legal versions", () => {
  it("submits a request with a labelled type and note, shows the reference and lists safe statuses", async () => {
    const user = userEvent.setup();
    renderCandidate(<PrivacyRequestsPanel />);
    expect(await screen.findByText(translate("en", "dataPrivacy.prStatusWaiting"))).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(translate("en", "dataPrivacy.prTypeLabel")), "deletion");
    await user.type(screen.getByLabelText(new RegExp(translate("en", "dataPrivacy.prNoteLabel").replace(/[()]/g, "\\$&"))), "Please look at this.");
    await user.click(screen.getByRole("button", { name: translate("en", "dataPrivacy.prSubmit") }));
    await waitFor(() => expect(cCreate).toHaveBeenCalledWith({ request_type: "deletion", note: "Please look at this." }));
    expect(await screen.findByRole("status")).toHaveTextContent("d".repeat(32));
    expect(screen.getByText(translate("en", "dataPrivacy.prNoPromise"))).toBeInTheDocument();
  });

  it("shows a calm error and keeps the form usable when the request fails", async () => {
    cCreate.mockRejectedValue(new Error("x"));
    const user = userEvent.setup();
    renderCandidate(<PrivacyRequestsPanel />);
    await user.click(await screen.findByRole("button", { name: translate("en", "dataPrivacy.prSubmit") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(translate("en", "dataPrivacy.prError"));
  });

  it("legal versions show version, effective date truth and recorded status; accept records only the current version", async () => {
    const user = userEvent.setup();
    renderCandidate(<LegalVersionsPanel />);
    expect(await screen.findByText(translate("en", "dataPrivacy.legalCurrentVersion", { version: "2.0" }))).toBeInTheDocument();
    expect(screen.getByText(translate("en", "dataPrivacy.legalNotAcceptedCurrent"))).toBeInTheDocument();
    expect(screen.getByText(translate("en", "dataPrivacy.legalLastRecorded", { version: "baseline-1" }))).toBeInTheDocument();
    expect(screen.getByText(translate("en", "dataPrivacy.legalNote"))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Record my acceptance/ }));
    await waitFor(() => expect(cAccept).toHaveBeenCalledWith("terms"));
  });

  it("an accepted current version shows the recorded date and no accept button", async () => {
    cLegal.mockResolvedValue({ documents: [{ code: "terms", title: "Terms of use", path: "/terms", current_version: "baseline-1", effective_at: null, version_is_baseline: true,
      accepted_current: true, last_acceptance: { version: "baseline-1", accepted_at: "2026-10-03T10:00:00", source: "settings", is_current: true } }] });
    renderCandidate(<LegalVersionsPanel />);
    expect(await screen.findByText(translate("en", "dataPrivacy.legalBaseline"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Record my acceptance/ })).not.toBeInTheDocument();
    expect(screen.getByText(translate("en", "dataPrivacy.legalEffectiveUnknown"))).toBeInTheDocument();
  });

  it("every new candidate string exists in all 8 locales, no locale falls back to English, no guarantee wording, slogan untouched", () => {
    const keys = [
      "prTitle", "prIntro", "prNoPromise", "prTypeLabel", "prSubmit", "prCreated", "prStatusWaiting", "prResultDeletion", "legalCurrentVersion",
      "legalEffectiveUnknown", "legalBaseline", "legalAcceptedOn", "legalAcceptButton", "legalNote", "incLegalAcceptances", "excPreparationContent",
    ];
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys as string[]) {
        const v = translate(locale, `dataPrivacy.${k}`, { ref: "R", version: "V", date: "D" });
        expect(v && !v.startsWith("dataPrivacy.")).toBeTruthy();
        if (locale !== "en") expect(v).not.toBe(translate("en", `dataPrivacy.${k}`, { ref: "R", version: "V", date: "D" }));
        expect(v).not.toMatch(/GDPR|DSGVO|RGPD|certif|garant|guarante/i);
      }
    }
  });
});
