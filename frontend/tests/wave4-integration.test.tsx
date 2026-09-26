import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// P10B Wave 4 — Prepare/Practice integration: the standalone Practice setup carries the
// conversation language + governed document/evidence context into the create request, and
// selecting/uploading never auto-submits.

const listDocuments = vi.fn();
const createInterview = vi.fn();
const options = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: {
    documents: { list: (...a: unknown[]) => listDocuments(...a) },
    interviews: {
      create: (...a: unknown[]) => createInterview(...a),
      options: (...a: unknown[]) => options(...a),
    },
  },
}));

vi.mock("@/lib/api/errors", () => ({ ApiError: class extends Error {} }));

// German account preference → the setup should default the interview language to German.
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { conversation_language: "de" }, status: "authenticated" }),
}));

import { InterviewSessionSetup } from "@/components/interview/InterviewSessionSetup";
import { DocumentPicker } from "@/components/documents/DocumentPicker";

afterEach(() => vi.clearAllMocks());

describe("Wave 4 — Practice setup carries language + governed context", () => {
  it("defaults the interview language from the account and sends the full config", async () => {
    options.mockResolvedValue({ career_levels: ["senior"], interview_types: [], difficulty_levels: [] });
    listDocuments.mockResolvedValue({
      documents: [{ id: 9, category: "job_description", title: "nurse-jd.txt", status: "ready", current_version: 1 }],
    });
    createInterview.mockResolvedValue({ session_id: "s1" });
    const onCreated = vi.fn();

    render(<InterviewSessionSetup onCreated={onCreated} />);

    await userEvent.type(screen.getByPlaceholderText(/Senior Product Manager/i), "Registered Nurse");
    await userEvent.type(screen.getByPlaceholderText(/fintech/i), "healthcare");
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Career level" })).toBeInTheDocument());

    // Select the existing JD document (governed picker) — this must NOT submit anything.
    const jdSelect = await screen.findByRole("combobox", { name: "Select a saved job description" });
    await userEvent.selectOptions(jdSelect, "9");
    expect(createInterview).not.toHaveBeenCalled();

    // Opt into approved evidence.
    await userEvent.click(screen.getByRole("checkbox", { name: /approved CV evidence/i }));

    await userEvent.click(screen.getByRole("button", { name: "Start interview" }));

    await waitFor(() => expect(createInterview).toHaveBeenCalledTimes(1));
    const payload = createInterview.mock.calls[0][0].configuration;
    expect(payload.conversation_language).toBe("de");           // defaulted from the account
    expect(payload.job_description_document_id).toBe(9);         // selected JD document id
    expect(payload.use_candidate_evidence).toBe(true);          // approved-evidence opt-in
    expect(payload.target_role).toBe("Registered Nurse");
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("s1"));
  });
});

describe("Wave 4 — DocumentPicker reuses the governed system", () => {
  it("lists only the given category and emits the selected id without submitting", async () => {
    listDocuments.mockResolvedValue({
      documents: [
        { id: 1, category: "job_description", title: "jd.txt", status: "ready", current_version: 1 },
        { id: 2, category: "cv", title: "cv.txt", status: "ready", current_version: 1 },
      ],
    });
    const onChange = vi.fn();
    render(<DocumentPicker category="job_description" value={null} onChange={onChange} label="JD" />);
    const select = await screen.findByRole("combobox", { name: "JD" });
    // Only the job_description document is offered (not the CV).
    expect(screen.getByRole("option", { name: "jd.txt" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "cv.txt" })).not.toBeInTheDocument();
    await userEvent.selectOptions(select, "1");
    expect(onChange).toHaveBeenCalledWith(1);
  });
});
