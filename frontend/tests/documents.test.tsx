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
    expect(screen.getByText("Source removed")).toBeInTheDocument();
  });
});
