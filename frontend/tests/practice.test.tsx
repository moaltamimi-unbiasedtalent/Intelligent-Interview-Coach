import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EvaluationOut, InterviewStateResponse } from "@/lib/api/types";

// --- mocks -------------------------------------------------------------------

const { replace, push, iv } = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  iv: {
    get: vi.fn(),
    options: vi.fn(),
    create: vi.fn(),
    submitAnswer: vi.fn(),
    nextQuestion: vi.fn(),
    complete: vi.fn(),
    recover: vi.fn(),
    report: vi.fn(),
    generateReport: vi.fn(),
    deepDive: { start: vi.fn(), answer: vi.fn(), next: vi.fn(), return: vi.fn() },
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
  // Tests render <PracticeClient sessionId=...> directly; the client-side param is
  // empty so the component falls back to the SSR prop.
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    interviews: iv,
    // Feedback controls appear beside evaluations/report; no saved rating in these tests.
    feedback: { get: () => Promise.resolve(null), submit: vi.fn(), remove: vi.fn() },
  },
}));

import { PracticeClient } from "@/components/interview/PracticeClient";

const EVAL: EvaluationOut = {
  overall_score: 72, relevance: 7, structure: 7, evidence: 6, role_knowledge: 7,
  problem_solving: 7, communication: 7, credibility: 7,
  strengths: ["Clear structure"], improvement_areas: ["Add metrics"], missing_evidence: [],
  stronger_answer_structure: "STAR", improved_example_answer: "", follow_up_question: "What changed?",
};

function state(overrides: Partial<InterviewStateResponse>): InterviewStateResponse {
  return {
    session_id: "s1", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
    current_question: { question_id: 1, question: "Tell me about a project.", question_type: "behavioural",
                        competency: "teamwork", difficulty: "moderate" },
    report_available: false, last_evaluation: null, target_role: "Registered Nurse",
    deep_dive: null, error: null, error_recoverable: false, cumulative_cost_usd: 0,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  iv.options.mockResolvedValue({ career_levels: ["senior"], interview_types: ["behavioural"], deep_dive_modes: ["deepen_reasoning"] });
});
afterEach(() => vi.clearAllMocks());

// --- standalone setup (no session) -------------------------------------------

describe("Practice standalone setup", () => {
  it("shows the setup form (no fake Record control) when there is no session", async () => {
    render(<PracticeClient />);
    expect(await screen.findByText("Practise an interview")).toBeInTheDocument();
    expect(screen.getByLabelText("Target role")).toBeInTheDocument();
    // The fake Record toggle is gone entirely.
    expect(screen.queryByRole("button", { name: /^record$/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Recording is available/i)).not.toBeInTheDocument();
  });

  it("creates an interview and routes to the new session", async () => {
    iv.create.mockResolvedValue(state({ session_id: "new-1" }));
    const user = userEvent.setup();
    render(<PracticeClient />);
    await user.type(await screen.findByLabelText("Target role"), "Senior PM");
    await user.type(screen.getByLabelText("Industry or sector"), "fintech");
    await user.click(screen.getByRole("button", { name: /start interview/i }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/practice?session=new-1"));
  });
});

// --- active interview lifecycle ----------------------------------------------

describe("Practice active interview", () => {
  it("renders the current question and submits a typed answer", async () => {
    iv.get.mockResolvedValue(state({}));
    iv.submitAnswer.mockResolvedValue(state({ state: "INTERVIEW_IN_PROGRESS", last_evaluation: EVAL }));
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    expect(await screen.findByRole("heading", { name: /Tell me about a project/i })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "My structured answer.");
    await user.click(screen.getByRole("button", { name: /submit answer/i }));
    await waitFor(() => expect(iv.submitAnswer).toHaveBeenCalledWith("s1", "My structured answer."));
    // Evaluation renders and stays visible.
    expect(await screen.findByText("Answer feedback")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
  });

  it("preserves the typed answer when submission fails", async () => {
    iv.get.mockResolvedValue(state({}));
    iv.submitAnswer.mockRejectedValue(Object.assign(new Error("x"), { status: 500, userMessage: "Failed." }));
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "Keep me");
    await user.click(screen.getByRole("button", { name: /submit answer/i }));
    await screen.findByText("Failed.");
    expect((box as HTMLTextAreaElement).value).toBe("Keep me");  // not cleared on failure
  });

  it("advances to the next question", async () => {
    iv.get.mockResolvedValue(state({ state: "INTERVIEW_IN_PROGRESS", last_evaluation: EVAL }));
    iv.nextQuestion.mockResolvedValue(state({ question_number: 2,
      current_question: { question_id: 2, question: "Second question?", question_type: "behavioural", competency: "x", difficulty: "moderate" } }));
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    await user.click(await screen.findByRole("button", { name: /next question/i }));
    await waitFor(() => expect(iv.nextQuestion).toHaveBeenCalledWith("s1"));
  });

  it("requires confirmation to end early", async () => {
    iv.get.mockResolvedValue(state({ state: "INTERVIEW_IN_PROGRESS", last_evaluation: EVAL }));
    iv.complete.mockResolvedValue(state({ state: "INTERVIEW_COMPLETE" }));
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    await user.click(await screen.findByRole("button", { name: /end interview/i }));
    expect(screen.getByText(/End the interview now\?/i)).toBeInTheDocument();
    expect(iv.complete).not.toHaveBeenCalled();  // not until confirmed
    await user.click(screen.getByRole("button", { name: /yes, end/i }));
    await waitFor(() => expect(iv.complete).toHaveBeenCalledWith("s1"));
  });

  it("starts a Deep Dive and answers a branch question", async () => {
    iv.get.mockResolvedValue(state({ state: "INTERVIEW_IN_PROGRESS", last_evaluation: EVAL }));
    iv.deepDive.start.mockResolvedValue(state({
      state: "BRANCH_AWAITING_ANSWER", last_evaluation: EVAL,
      deep_dive: { active: true, mode: "deepen_reasoning", depth: 1, max_depth: 2, parent_question_id: 1,
        current_branch_question: { branch_id: "b1", parent_question_id: 1, question: "Why did that work?",
          branch_mode: "deepen_reasoning", focus_area: "reasoning", difficulty: "moderate", depth: 1 },
        last_branch_evaluation: null, can_go_deeper: false } }));
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    await user.click(await screen.findByRole("button", { name: /^go deeper$/i }));
    await waitFor(() => expect(iv.deepDive.start).toHaveBeenCalledWith("s1", "deepen_reasoning"));
    expect(await screen.findByText("Why did that work?")).toBeInTheDocument();
  });

  it("generates the report when complete", async () => {
    iv.get.mockResolvedValueOnce(state({ state: "INTERVIEW_COMPLETE", current_question: null }));
    iv.generateReport.mockResolvedValue({ session_id: "s1", report: {}, saved_report_id: 1, save_failed: false });
    // After generateReport, the hook reloads → REPORT_READY.
    iv.get.mockResolvedValue(state({ state: "REPORT_READY", current_question: null, report_available: true }));
    iv.report.mockResolvedValue({ session_id: "s1", report: { overall_readiness_score: 68, performance_summary: "Solid." }, saved_report_id: 1, save_failed: false });
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    await user.click(await screen.findByRole("button", { name: /generate performance review/i }));
    await waitFor(() => expect(iv.generateReport).toHaveBeenCalledWith("s1"));
  });
});

// --- resume / errors ---------------------------------------------------------

describe("Practice resume and errors", () => {
  it("restores an in-progress interview on load (refresh)", async () => {
    iv.get.mockResolvedValue(state({ state: "AWAITING_ANSWER" }));
    render(<PracticeClient sessionId="s1" />);
    expect(await screen.findByRole("heading", { name: /Tell me about a project/i })).toBeInTheDocument();
    expect(iv.get).toHaveBeenCalledWith("s1");
  });

  it("shows a safe error for an unknown session", async () => {
    iv.get.mockRejectedValue(Object.assign(new Error("nf"), { status: 422, userMessage: "Unknown interview session." }));
    render(<PracticeClient sessionId="ghost" />);
    expect(await screen.findByText("Unknown interview session.")).toBeInTheDocument();
  });

  it("offers recovery from a recoverable error state", async () => {
    iv.get.mockResolvedValue(state({ state: "ERROR", error: "Temporary problem.", error_recoverable: true, current_question: null }));
    iv.recover.mockResolvedValue(state({ state: "AWAITING_ANSWER" }));
    const user = userEvent.setup();
    render(<PracticeClient sessionId="s1" />);
    await user.click(await screen.findByRole("button", { name: /resume interview/i }));
    await waitFor(() => expect(iv.recover).toHaveBeenCalledWith("s1"));
  });

  it("never claims camera use", async () => {
    iv.get.mockResolvedValue(state({}));
    render(<PracticeClient sessionId="s1" />);
    expect(await screen.findByText(/No camera/i)).toBeInTheDocument();
  });
});
