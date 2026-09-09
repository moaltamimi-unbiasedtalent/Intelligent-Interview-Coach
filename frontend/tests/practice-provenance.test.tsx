import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

let search = "";
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/lib/api/client", () => ({
  api: { interviews: { options: () => Promise.resolve({ deep_dive_modes: [] }) } },
}));

const state = {
  state: "AWAITING_ANSWER", target_role: "Senior PM", questions_planned: 5, question_number: 1,
  current_question: { question_id: 1, question: "Tell me about a project.", question_type: "behavioural", competency: "x", difficulty: "moderate" },
  deep_dive: null, error: null, error_recoverable: false,
};
vi.mock("@/components/interview/useInterview", () => ({
  useInterview: () => ({ state, busy: null, loadError: null, conflict: false, actionError: null,
                         submitAnswer: vi.fn(), recover: vi.fn() }),
}));

import { PracticeClient } from "@/components/interview/PracticeClient";

afterEach(() => { search = ""; vi.clearAllMocks(); });

describe("Practice prefill provenance", () => {
  it("shows a 'prepared in Coach' note when launched from the Coach handoff", async () => {
    search = "session=sess_1&from=coach";
    render(<PracticeClient sessionId="sess_1" />);
    expect(await screen.findByTestId("coach-provenance")).toHaveTextContent("Prepared with Mo");
  });

  it("shows NO provenance for a standalone Practice session (no fabrication)", async () => {
    search = "session=sess_1";
    render(<PracticeClient sessionId="sess_1" />);
    expect(await screen.findByText("Tell me about a project.")).toBeInTheDocument();
    expect(screen.queryByTestId("coach-provenance")).not.toBeInTheDocument();
  });

  it("standalone setup (no session) shows no provenance", () => {
    search = "";
    render(<PracticeClient sessionId={undefined} />);
    expect(screen.queryByTestId("coach-provenance")).not.toBeInTheDocument();
  });
});
