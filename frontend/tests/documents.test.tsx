import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const docsList = vi.fn();
const docsGet = vi.fn();
const docsUpload = vi.fn();
const docsReview = vi.fn();
const docsRemove = vi.fn();
const storiesList = vi.fn();
const storiesDraft = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: {
      documents: {
        list: (...a: unknown[]) => docsList(...a),
        get: (...a: unknown[]) => docsGet(...a),
        upload: (...a: unknown[]) => docsUpload(...a),
        reviewClaim: (...a: unknown[]) => docsReview(...a),
        remove: (...a: unknown[]) => docsRemove(...a),
        downloadUrl: (id: number) => `/api/v1/documents/${id}/download`,
      },
      stories: {
        list: (...a: unknown[]) => storiesList(...a),
        draft: (...a: unknown[]) => storiesDraft(...a),
        remove: vi.fn(),
      },
    },
    ApiError: actual.ApiError,
  };
});

import { DocumentsClient } from "@/components/documents/DocumentsClient";

const DOC = {
  id: 1, category: "cv", title: "cv.txt", status: "review_required", current_version: 1,
  created_at: null,
  versions: [{ version: 1, original_filename: "cv.txt", mime_type: "text/plain", size_bytes: 10, page_count: null, extraction_origin: "native", status: "ready", failure_reason: null, language_hint: null }],
  claims: [
    { id: 11, document_id: 1, version_id: 1, claim_type: "skill", text: "Python", edited_text: null, display_text: "Python", source_page: null, source_section: "block 2", review_state: "pending" },
    { id: 12, document_id: 1, version_id: 1, claim_type: "achievement", text: "Cut latency 40%", edited_text: null, display_text: "Cut latency 40%", source_page: null, source_section: "block 3", review_state: "pending" },
  ],
};

afterEach(() => vi.clearAllMocks());

describe("DocumentsClient", () => {
  it("lists documents and shows the empty story bank", async () => {
    docsList.mockResolvedValue({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "review_required", current_version: 1, updated_at: null }] });
    storiesList.mockResolvedValue({ stories: [] });
    render(<DocumentsClient />);
    await waitFor(() => expect(screen.getByText("cv.txt")).toBeInTheDocument());
    expect(screen.getByText(/No stories yet/)).toBeInTheDocument();
  });

  it("uploads a file", async () => {
    docsList.mockResolvedValue({ documents: [] });
    storiesList.mockResolvedValue({ stories: [] });
    docsUpload.mockResolvedValue(DOC);
    render(<DocumentsClient />);
    await waitFor(() => expect(screen.getByText(/haven’t uploaded/)).toBeInTheDocument());
    const file = new File(["hi"], "cv.txt", { type: "text/plain" });
    await userEvent.upload(screen.getByLabelText("Upload document"), file);
    await waitFor(() => expect(docsUpload).toHaveBeenCalled());
  });

  it("reviews a claim (accept) and drafts a story from selected evidence", async () => {
    docsList.mockResolvedValue({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "review_required", current_version: 1, updated_at: null }] });
    storiesList.mockResolvedValue({ stories: [] });
    docsGet.mockResolvedValue(DOC);
    docsReview.mockResolvedValue({ ...DOC.claims[0], review_state: "accepted" });
    storiesDraft.mockResolvedValue({ id: 5, title: "cv.txt", status: "source_backed", evidence_state: "verified", competencies: [], evidence_claim_ids: [11] });
    render(<DocumentsClient />);
    await userEvent.click(await screen.findByText("cv.txt"));
    await waitFor(() => expect(screen.getByText("Review extracted evidence")).toBeInTheDocument());
    // Provenance shown
    expect(screen.getByText(/block 2/)).toBeInTheDocument();
    // Accept the first claim
    await userEvent.click(screen.getAllByRole("button", { name: "Accept" })[0]);
    expect(docsReview).toHaveBeenCalledWith(1, 11, "accept", undefined);
    // Select a claim and draft a story
    await userEvent.click(screen.getByLabelText("Python"));
    await userEvent.click(screen.getByRole("button", { name: /Draft a story/ }));
    await waitFor(() => expect(storiesDraft).toHaveBeenCalledWith("cv.txt", [11]));
  });

  it("shows a source-revoked story state", async () => {
    docsList.mockResolvedValue({ documents: [] });
    storiesList.mockResolvedValue({ stories: [{ id: 9, title: "Old win", status: "source_backed", evidence_state: "source_revoked", competencies: [], evidence_claim_ids: [] }] });
    render(<DocumentsClient />);
    await waitFor(() => expect(screen.getByText("Old win")).toBeInTheDocument());
    expect(screen.getByText("Supporting source removed")).toBeInTheDocument();
  });
});

/**
 * Pilot 2 P2-04: candidate provenance wording for claim review and the Story Bank. "Reviewed by you" never means third-party verification, and
 * the backend state "verified" (a source-backed story that still has a live supporting claim) is shown as "Supporting evidence available".
 */
describe("P2-04 provenance wording", () => {
  const withClaims = (states: [string, string | null][]) => ({
    ...DOC,
    claims: states.map(([review_state, edited], i) => ({
      id: 21 + i, document_id: 1, version_id: 1, claim_type: "skill", text: `Claim ${i}`, edited_text: edited, display_text: edited ?? `Claim ${i}`,
      source_page: i === 0 ? 3 : null, source_section: i === 0 ? null : `block ${i}`, review_state,
    })),
  });

  it("claim review states say what the candidate did, and pending is not shown as reviewed", async () => {
    docsList.mockResolvedValue({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "review_required", current_version: 1, updated_at: null }] });
    storiesList.mockResolvedValue({ stories: [] });
    docsGet.mockResolvedValue(withClaims([["pending", null], ["accepted", null], ["edited", "Edited text"], ["rejected", null]]));
    render(<DocumentsClient />);
    await userEvent.click(await screen.findByText("cv.txt"));
    await waitFor(() => expect(screen.getByText("Review extracted evidence")).toBeInTheDocument());
    const items = screen.getAllByTestId("claim-source").map((el) => el.closest("li") as HTMLElement);
    expect(items).toHaveLength(4);
    expect(within(items[0]).getByText("Not reviewed yet")).toBeInTheDocument();
    expect(within(items[0]).queryByText("Reviewed by you")).toBeNull();
    expect(within(items[1]).getByText("Reviewed by you")).toBeInTheDocument();
    expect(within(items[2]).getByText("Corrected by you")).toBeInTheDocument();
    expect(within(items[3]).getByText("Rejected by you")).toBeInTheDocument();
    // the extraction origin stays visible: document location, labelled as extracted from the candidate's own document
    expect(within(items[0]).getByTestId("claim-source").textContent).toContain("Extracted from your document");
    expect(within(items[0]).getByTestId("claim-source").textContent).toMatch(/Page 3|page 3/i);
    // the meaning of "Reviewed by you" is explained, and it does not claim verification
    const explainer = screen.getByTestId("provenance-explainer");
    expect(explainer.textContent).toContain("does not mean a third party verified it");
    expect(document.body.textContent).not.toMatch(/\bverified by\b|independently verified|fact[- ]checked/i);
    // operational buttons keep their action wording
    expect(screen.getAllByRole("button", { name: "Accept" }).length).toBeGreaterThan(0);
  });

  it("Story Bank explains how each story was made and what its supporting evidence state means, without overclaiming", async () => {
    docsList.mockResolvedValue({ documents: [] });
    storiesList.mockResolvedValue({ stories: [
      { id: 1, title: "S1", status: "source_backed", evidence_state: "verified", competencies: [], evidence_claim_ids: [1] },
      { id: 2, title: "S2", status: "user_created", evidence_state: "none", competencies: [], evidence_claim_ids: [] },
      { id: 3, title: "S3", status: "user_corrected", evidence_state: "none", competencies: [], evidence_claim_ids: [] },
      { id: 4, title: "S4", status: "model_suggested", evidence_state: "none", competencies: [], evidence_claim_ids: [] },
      { id: 5, title: "S5", status: "source_backed", evidence_state: "source_revoked", competencies: [], evidence_claim_ids: [] },
    ] });
    render(<DocumentsClient />);
    await waitFor(() => expect(screen.getByText("S1")).toBeInTheDocument());
    const row = (title: string) => screen.getByText(title).closest("li") as HTMLElement;
    expect(within(row("S1")).getByText("Built from your evidence")).toBeInTheDocument();
    expect(within(row("S1")).getByText("Supporting evidence available")).toBeInTheDocument();
    expect(within(row("S2")).getByText("Written by you")).toBeInTheDocument();
    expect(within(row("S3")).getByText("Edited by you")).toBeInTheDocument();
    expect(within(row("S4")).getByText("AI suggested")).toBeInTheDocument();
    expect(within(row("S5")).getByText("Supporting source removed")).toBeInTheDocument();
    expect(within(row("S2")).getByText("No supporting source")).toBeInTheDocument();          // "none" implies no verification
    expect(within(row("S2")).queryByText(/support(ing)? evidence available/i)).toBeNull();
    // the misleading label is gone everywhere
    expect(document.body.textContent).not.toMatch(/Evidence verified|Source-backed/);
  });

  it("every provenance wording key exists in all eight locales with no verification claim and no dash punctuation", async () => {
    const { translate } = await import("@/lib/i18n/catalog");
    const { SUPPORTED_LOCALE_CODES } = await import("@/lib/i18n/locales");
    const keys = ["documents.pending", "documents.accepted", "documents.edited", "documents.rejected", "documents.stSourceBacked", "documents.stUserCreated",
      "documents.stUserCorrected", "documents.stModelSuggested", "documents.evVerified", "documents.evRevoked", "documents.evNone"];
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const v = translate(locale, k);
        expect(v, `${locale}.${k}`).not.toBe(k);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
      }
    }
    expect(translate("en", "documents.evVerified")).not.toMatch(/verif/i);
  });
});
