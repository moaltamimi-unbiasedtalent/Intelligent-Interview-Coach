import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// 04A: Practice setup sends the candidate's chosen stories ONLY with explicit consent, ids only (never story text).

const createInterview = vi.fn();
const options = vi.fn();
const listStories = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: {
    documents: { list: vi.fn().mockResolvedValue({ documents: [] }) },
    stories: { list: (...a: unknown[]) => listStories(...a), suggest: vi.fn().mockResolvedValue({ suggestions: [] }) },
    interviews: { create: (...a: unknown[]) => createInterview(...a), options: (...a: unknown[]) => options(...a) },
  },
}));
vi.mock("@/lib/api/errors", () => ({ ApiError: class extends Error {} }));
vi.mock("@/components/auth/AuthProvider", () => ({ useAuthOptional: () => ({ account: { conversation_language: "en" }, status: "authenticated" }) }));

import { InterviewSessionSetup } from "@/components/interview/InterviewSessionSetup";

afterEach(() => vi.clearAllMocks());

const S = { situation: "SECRET-STORY-TEXT", task: null, action: null, result: null, competencies: [], status: "user_created", evidence_state: "none", evidence_claim_ids: [], verification: "unverified" };

async function fillForm() {
  await userEvent.type(screen.getByPlaceholderText(/Senior Product Manager/i), "Registered Nurse");
  await userEvent.type(screen.getByPlaceholderText(/fintech/i), "healthcare");
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Career level" })).toBeInTheDocument());
}

describe("Practice setup with stories", () => {
  it("cannot start with a chosen story until the explicit consent is given, then sends ids and the consent only", async () => {
    options.mockResolvedValue({ career_levels: ["senior"], interview_types: [], difficulty_levels: [] });
    listStories.mockResolvedValue({ stories: [{ id: 5, title: "Migration lead", ...S }, { id: 6, title: "Other", ...S }] });
    createInterview.mockResolvedValue({ session_id: "s1" });
    const onCreated = vi.fn();
    render(<InterviewSessionSetup onCreated={onCreated} />);
    await fillForm();
    await userEvent.click(await screen.findByRole("checkbox", { name: /Migration lead/ }));
    const start = screen.getByRole("button", { name: "Start interview" });
    expect(start).toBeDisabled();                                                          // chosen but not consented
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand that the stories I selected/ }));
    expect(start).toBeEnabled();
    await userEvent.click(start);
    await waitFor(() => expect(createInterview).toHaveBeenCalledTimes(1));
    const cfg = createInterview.mock.calls[0][0].configuration;
    expect(cfg.story_ids).toEqual([5]);
    expect(cfg.confirm_story_use).toBe(true);
    expect(JSON.stringify(createInterview.mock.calls[0][0])).not.toContain("SECRET-STORY-TEXT");   // text never travels from the browser
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("s1"));
  });

  it("sends no story fields at all when no story is chosen", async () => {
    options.mockResolvedValue({ career_levels: ["senior"], interview_types: [], difficulty_levels: [] });
    listStories.mockResolvedValue({ stories: [{ id: 5, title: "Migration lead", ...S }] });
    createInterview.mockResolvedValue({ session_id: "s2" });
    render(<InterviewSessionSetup onCreated={vi.fn()} />);
    await fillForm();
    await screen.findByRole("checkbox", { name: /Migration lead/ });
    await userEvent.click(screen.getByRole("button", { name: "Start interview" }));
    await waitFor(() => expect(createInterview).toHaveBeenCalledTimes(1));
    const cfg = createInterview.mock.calls[0][0].configuration;
    expect("story_ids" in cfg).toBe(false);
    expect("confirm_story_use" in cfg).toBe(false);
  });
});
