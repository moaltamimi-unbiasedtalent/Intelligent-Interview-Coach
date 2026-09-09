import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JourneyChrome, PreparationChecklist } from "@/components/agent/JourneyChrome";
import type { PreparationJourney } from "@/lib/api/types";

function journey(over: Partial<PreparationJourney> = {}): PreparationJourney {
  return {
    understand: { status: "complete", role_known: true, requirements_known: true, evidence_used: false },
    prepare: { status: "in_progress", gaps_known: true, plan_known: false, questions_known: false },
    practise: { status: "not_started", handoff_approved: false },
    ...over,
  };
}

describe("JourneyChrome", () => {
  it("renders the three stages with text state (not colour-only)", () => {
    render(<JourneyChrome journey={journey()} />);
    const nav = screen.getByRole("navigation", { name: "Preparation journey" });
    expect(within(nav).getByText("Understand")).toBeInTheDocument();
    expect(within(nav).getByText("Prepare")).toBeInTheDocument();
    expect(within(nav).getByText("Practise")).toBeInTheDocument();
    // Accessible state text exists for each stage.
    expect(within(nav).getByText(/Understand: complete/)).toBeInTheDocument();
  });

  it("marks the in-progress stage as the current step", () => {
    render(<JourneyChrome journey={journey()} />);
    const current = document.querySelector('[aria-current="step"]');
    expect(current).not.toBeNull();
    expect(current).toHaveTextContent("Prepare");
  });

  it("renders nothing without a journey", () => {
    const { container } = render(<JourneyChrome journey={undefined} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("PreparationChecklist", () => {
  it("shows completed and to-do steps from real state", () => {
    render(<PreparationChecklist journey={journey({
      understand: { status: "complete", role_known: true, requirements_known: true, evidence_used: false },
      prepare: { status: "in_progress", gaps_known: true, plan_known: false, questions_known: false },
    })} />);
    const section = screen.getByRole("region", { name: "Preparation progress" });
    // JD + gaps done; plan + questions to do.
    expect(within(section).getByText("Understand the opportunity")).toBeInTheDocument();
    expect(within(section).getByText("Compare your experience")).toBeInTheDocument();
    expect(within(section).getByText("Build preparation priorities")).toBeInTheDocument();
    expect(within(section).getByText("Create practice questions")).toBeInTheDocument();
  });

  it("is hidden when no preparation step has produced state", () => {
    const { container } = render(<PreparationChecklist journey={journey({
      understand: { status: "in_progress", role_known: true, requirements_known: false, evidence_used: false },
      prepare: { status: "not_started", gaps_known: false, plan_known: false, questions_known: false },
    })} />);
    expect(container.firstChild).toBeNull();
  });
});

// --- handoff provenance via the Coach workspace ------------------------------

const start = vi.fn();
const getRun = vi.fn();
const resume = vi.fn();
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    agent: { start: (...a: unknown[]) => start(...a), getRun: (...a: unknown[]) => getRun(...a),
             resume: (...a: unknown[]) => resume(...a), continue: vi.fn() },
    interviews: { create: vi.fn(), options: vi.fn() },
    memory: { list: vi.fn(), update: vi.fn(), remove: vi.fn(), preview: vi.fn() },
  },
}));

import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";

function handoffRun(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_1", status: "awaiting_human_input", awaiting_human_input: true, response: "",
    tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false,
    memory_count: 0, memory_loaded: [], handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 3, turn_step_count: 3, conversation: [{ role: "user", content: "Prep" }],
    preparation_context: null, cache_hits: 0, cache_misses: 0,
    pending_action: { action_id: "h1", type: "approve_practice_handoff", message: "Ready?", options: [], data: { target_role: "Senior PM" } },
    ...over,
  };
}

beforeEach(() => resume.mockResolvedValue(handoffRun({ status: "completed", awaiting_human_input: false, pending_action: null })));
afterEach(() => vi.clearAllMocks());

async function renderHandoff(summary: Record<string, unknown> | null) {
  start.mockResolvedValue(handoffRun({ handoff_summary: summary }));
  render(<AgentPrepareWorkspace />);
  await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
  await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
  expect(await screen.findByText("Practise this role")).toBeInTheDocument();
}

describe("Practice handoff provenance card", () => {
  it("shows role, focus and question provenance from the summary", async () => {
    await renderHandoff({
      target_role: { value: "Senior PM", source: "confirmed_role" },
      focus_areas: [{ value: "Stakeholder comms", source: "gap_analysis" }],
      question_count: 8, question_source: "question_generator",
    });
    expect(screen.getByText("Senior PM")).toBeInTheDocument();
    expect(screen.getByText(/confirmed in Coach/)).toBeInTheDocument();
    expect(screen.getByText(/from your gap analysis/)).toBeInTheDocument();
    expect(screen.getByText("Stakeholder comms")).toBeInTheDocument();
    expect(screen.getByText(/8 practice questions/)).toBeInTheDocument();
  });

  it("omits missing fields (no fabrication)", async () => {
    await renderHandoff({ target_role: { value: "Senior PM", source: "job_analysis" } });
    expect(screen.getByText(/from your job description/)).toBeInTheDocument();
    expect(screen.queryByText(/practice questions/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Priority areas/)).not.toBeInTheDocument();
  });

  it("approves the handoff", async () => {
    await renderHandoff({ target_role: { value: "Senior PM", source: "confirmed_role" } });
    await userEvent.click(screen.getByRole("button", { name: "Start practice" }));
    expect(resume).toHaveBeenCalledWith("run_1", { action_id: "h1", decision: "approve" });
  });
});
