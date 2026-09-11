import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const getRun = vi.fn();
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_1"),
}));
vi.mock("@/lib/api/client", () => ({
  api: { agent: { getRun: (...a: unknown[]) => getRun(...a) } },
}));

import { AgentInspector } from "@/components/agent/AgentInspector";

const RUN = {
  run_id: "run_1", status: "completed", response: "answer",
  tools_used: ["SearchCareerKnowledge"], retrieval_used: true,
  sources: [{ title: "ESCO — Product manager", reference_year: 2024 }],
  citations: [], memory_used: true, memory_count: 2,
  awaiting_human_input: false, pending_action: null, handoff_approved: true,
  events: [
    { event_type: "run_started" },
    { event_type: "tool_completed", tool_name: "SearchCareerKnowledge", source_count: 3 },
    { event_type: "human_input_required", message: "confirm_role" },
    { event_type: "human_input_resumed", message: "confirm_role" },
    { event_type: "run_completed" },
  ],
  tool_calls: [{ tool: "SearchCareerKnowledge", status: "ok" }],
  warnings: ["The approved preparation memory could not be saved."],
  step_count: 4, turn_step_count: 4, conversation: [],
  resolved_occupation: "Product manager", resolved_geography: "DE",
  preparation_context: null,
};

afterEach(() => vi.clearAllMocks());

describe("Agent Inspector", () => {
  it("renders safe run summary, tools, retrieval, approvals and warnings", async () => {
    getRun.mockResolvedValue(RUN);
    render(<AgentInspector />);
    expect(await screen.findByText("Run summary")).toBeInTheDocument();
    expect(screen.getByText("Product manager")).toBeInTheDocument();          // resolved occupation
    expect(screen.getByText("Execution timeline")).toBeInTheDocument();
    expect(screen.getByText("Tool completed")).toBeInTheDocument();            // friendly event label
    expect(screen.getByText("Human confirmation requested")).toBeInTheDocument();
    expect(screen.getByText(/could not be saved/)).toBeInTheDocument();        // warning
  });

  it("never renders unsafe fields even if present on the payload", async () => {
    // Even if the payload carried forbidden data, the inspector renders only known
    // safe fields — these marker values must never appear.
    getRun.mockResolvedValue({
      ...RUN, warnings: [],
      // deliberately unsafe extras the component must ignore:
      messages: [{ type: "system", content: "SYSTEM-PROMPT-MARKER" }],
      reasoning: "COT-MARKER",
      checkpoint: "RAW-CHECKPOINT-MARKER",
      job_description: "RAW-JD-MARKER",
    });
    const { container } = render(<AgentInspector />);
    expect(await screen.findByText("Run summary")).toBeInTheDocument();
    const text = container.textContent ?? "";
    expect(text).not.toContain("SYSTEM-PROMPT-MARKER");
    expect(text).not.toContain("COT-MARKER");
    expect(text).not.toContain("RAW-CHECKPOINT-MARKER");
    expect(text).not.toContain("RAW-JD-MARKER");
    // Usage/cost is honestly reported as not captured, never fabricated.
    expect(text).toContain("Not captured for this run");
  });

  it("shows the safe failure category for a failed tool call", async () => {
    getRun.mockResolvedValue({
      ...RUN,
      tools_used: [],
      tool_calls: [{ tool: "GenerateInterviewQuestions", status: "error", category: "missing_prerequisite" }],
    });
    render(<AgentInspector />);
    expect(await screen.findByText("Run summary")).toBeInTheDocument();
    expect(screen.getByText("missing prerequisite")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("counts approved memory and handoff as applied human approvals", async () => {
    // Regression (Phase 6, P2-A): approved memory/handoff emit `memory_saved` /
    // `handoff_approved`, not `human_input_resumed`. The "Applied" total must still
    // reflect both approvals rather than reporting 0.
    getRun.mockResolvedValue({
      ...RUN, warnings: [],
      events: [
        { event_type: "run_started" },
        { event_type: "human_input_required", message: "approve_memory" },
        { event_type: "memory_saved", message: "recurring_gap" },
        { event_type: "human_input_required", message: "approve_practice_handoff" },
        { event_type: "handoff_approved", message: "approve_practice_handoff" },
        { event_type: "run_completed" },
      ],
    });
    render(<AgentInspector />);
    expect(await screen.findByText("Run summary")).toBeInTheDocument();
    const applied = screen.getByText("Applied");
    expect(applied.parentElement?.textContent).toContain("2");
    const requested = screen.getByText("Requested");
    expect(requested.parentElement?.textContent).toContain("2");
  });

  it("shows a safe error for an unknown/foreign run", async () => {
    getRun.mockRejectedValue(Object.assign(new Error("nf"), { status: 404 }));
    render(<AgentInspector />);
    expect(await screen.findByText("That run was not found.")).toBeInTheDocument();
  });
});
