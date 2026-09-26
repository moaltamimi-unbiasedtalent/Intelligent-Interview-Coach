import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// P10B Wave 3 — document reliability: reusable upload seam with client-side pre-validation,
// the localized failure taxonomy in the inventory, and the reprocess (retry) action.

const listDocuments = vi.fn();
const getDocument = vi.fn();
const uploadDocument = vi.fn();
const reprocessDocument = vi.fn();
const listStories = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: {
      documents: {
        list: (...a: unknown[]) => listDocuments(...a),
        get: (...a: unknown[]) => getDocument(...a),
        upload: (...a: unknown[]) => uploadDocument(...a),
        reprocess: (...a: unknown[]) => reprocessDocument(...a),
        remove: vi.fn(),
        downloadUrl: (id: number) => `/api/v1/documents/${id}/download`,
      },
      stories: { list: (...a: unknown[]) => listStories(...a) },
    },
  };
});

import { DocumentUpload } from "@/components/documents/DocumentUpload";
import { DocumentsClient } from "@/components/documents/DocumentsClient";

afterEach(() => vi.clearAllMocks());

function file(name: string, opts?: { size?: number }): File {
  const f = new File(["x"], name, { type: "application/octet-stream" });
  if (opts?.size !== undefined) Object.defineProperty(f, "size", { value: opts.size });
  return f;
}

describe("DocumentUpload — client pre-validation (one governed seam)", () => {
  it("rejects an unsupported type locally without calling the API", async () => {
    render(<DocumentUpload />);
    const input = screen.getByLabelText("Upload document");
    // Bypass the browser's own accept filter so we exercise our JS pre-validation.
    await userEvent.upload(input, file("malware.exe"), { applyAccept: false });
    expect(await screen.findByText(/Unsupported file type/i)).toBeInTheDocument();
    expect(uploadDocument).not.toHaveBeenCalled();
  });

  it("rejects an oversized file locally without calling the API", async () => {
    render(<DocumentUpload />);
    const input = screen.getByLabelText("Upload document");
    await userEvent.upload(input, file("big.pdf", { size: 11 * 1024 * 1024 }));
    expect(await screen.findByText(/larger than 10 MB/i)).toBeInTheDocument();
    expect(uploadDocument).not.toHaveBeenCalled();
  });

  it("shows accepted formats, size, privacy and the OCR note up front", () => {
    render(<DocumentUpload />);
    expect(screen.getByText(/Accepted: PDF, DOCX, TXT, PNG or JPEG/i)).toBeInTheDocument();
    expect(screen.getByText(/never used to judge identity/i)).toBeInTheDocument();
    expect(screen.getByText(/need OCR to read their text/i)).toBeInTheDocument();
  });
});

describe("Documents inventory — failure taxonomy + retry", () => {
  it("explains a scanned/OCR-unavailable failure and offers Retry (reprocess)", async () => {
    listDocuments.mockResolvedValue({
      documents: [{
        id: 7, category: "cv", title: "scan.pdf", status: "failed",
        current_version: 1, updated_at: "2026-09-26T00:00:00Z", failure_kind: "ocr_unavailable",
      }],
    });
    listStories.mockResolvedValue({ stories: [] });
    getDocument.mockResolvedValue({
      id: 7, category: "cv", title: "scan.pdf", status: "failed", current_version: 1,
      versions: [{ version: 1, original_filename: "scan.pdf", mime_type: "application/pdf", size_bytes: 10, status: "failed", failure_kind: "ocr_unavailable", failure_reason: "Scanned-document OCR is not available in this environment." }],
      claims: [],
    });
    reprocessDocument.mockResolvedValue({ id: 7, status: "review_required", current_version: 1, versions: [], claims: [] });

    render(<DocumentsClient />);
    // The failed document is listed (there are desktop + mobile renderings; take the first).
    const nameButtons = await screen.findAllByRole("button", { name: "scan.pdf" });
    await userEvent.click(nameButtons[0]);
    // The localized, actionable OCR message is shown — not a generic "couldn't read the file".
    expect(await screen.findAllByText(/needs OCR, which/i)).not.toHaveLength(0);
    // A Retry action is offered and calls reprocess.
    const retry = screen.getAllByRole("button", { name: "Retry processing" })[0];
    await userEvent.click(retry);
    await waitFor(() => expect(reprocessDocument).toHaveBeenCalledWith(7));
  });

  it("renders a healthy document row with its type and status", async () => {
    listDocuments.mockResolvedValue({
      documents: [{ id: 1, category: "job_description", title: "jd.txt", status: "ready", current_version: 2, updated_at: "2026-09-26T00:00:00Z" }],
    });
    listStories.mockResolvedValue({ stories: [] });
    render(<DocumentsClient />);
    expect(await screen.findAllByText("jd.txt")).not.toHaveLength(0);
    // Category label localized (desktop table + mobile card both render it).
    expect(screen.getAllByText("Job description").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
  });
});
