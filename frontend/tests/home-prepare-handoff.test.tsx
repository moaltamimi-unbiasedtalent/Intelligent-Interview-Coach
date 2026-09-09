import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Home → Prepare handoff consumption: the draft is auto-started once, an existing run
// wins, a failed start keeps the goal, and the deterministic fallback auto-submits.

const start = vi.fn();
const getRun = vi.fn();
const chat = vi.fn();
const push = vi.fn();
const replace = vi.fn();
let searchRun: string | null = null;

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(searchRun ? `run=${searchRun}` : ""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    agent: {
      start: (...a: unknown[]) => start(...a),
      getRun: (...a: unknown[]) => getRun(...a),
      resume: vi.fn(),
      continue: vi.fn(),
    },
    career: { chat: (...a: unknown[]) => chat(...a) },
    interviews: { create: vi.fn(), options: vi.fn() },
  },
}));

import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";
import { PrepareWorkspace } from "@/components/preparation/PrepareWorkspace";
import type { PrepareDraft } from "@/lib/prepareDraft";

function runResponse(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_1", status: "completed", response: "Here is your guidance.",
    tools_used: [], retrieval_used: false, sources: [], citations: [],
    memory_used: false, memory_count: 0, awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 1, turn_step_count: 1,
    conversation: [{ role: "user", content: "x" }, { role: "assistant", content: "Here is your guidance." }],
    preparation_context: null, resolved_occupation: null, resolved_geography: null,
    ...over,
  };
}

const START_DRAFT: PrepareDraft = {
  source: "home", action: "start", goal: "Executive HR Director role at a fashion company",
};

beforeEach(() => { searchRun = null; });
afterEach(() => vi.clearAllMocks());

describe("Home → Prepare (Agent Coach)", () => {
  it("auto-starts the transferred goal exactly once (no manual re-entry)", async () => {
    start.mockResolvedValue(runResponse());
    const { rerender } = render(<AgentPrepareWorkspace initialDraft={START_DRAFT} />);
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    expect(start.mock.calls[0][0]).toMatchObject({ goal: START_DRAFT.goal });
    // Rerenders must not create another run (§9/§25).
    rerender(<AgentPrepareWorkspace initialDraft={START_DRAFT} />);
    rerender(<AgentPrepareWorkspace initialDraft={START_DRAFT} />);
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("does not put candidate text in the URL", async () => {
    start.mockResolvedValue(runResponse());
    render(<AgentPrepareWorkspace initialDraft={START_DRAFT} />);
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    // The only navigation is replace to a safe ?run= id — never the goal text.
    for (const call of replace.mock.calls) {
      expect(String(call[0])).not.toContain("fashion");
      expect(String(call[0])).not.toContain("Executive");
    }
  });

  it("an existing ?run= wins over a stale Home draft (§21/§26)", async () => {
    searchRun = "abc123";
    getRun.mockResolvedValue(runResponse({ run_id: "abc123" }));
    render(<AgentPrepareWorkspace initialDraft={START_DRAFT} />);
    await waitFor(() => expect(getRun).toHaveBeenCalledWith("abc123", expect.anything()));
    expect(start).not.toHaveBeenCalled();
  });

  it("keeps the goal populated when the start fails (retry without retyping §27)", async () => {
    start.mockRejectedValue(Object.assign(new Error("boom"), { userMessage: "Something went wrong." }));
    render(<AgentPrepareWorkspace initialDraft={START_DRAFT} />);
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    const box = await screen.findByLabelText("What interview are you preparing for?");
    expect((box as HTMLTextAreaElement).value).toBe(START_DRAFT.goal);
  });

  it("the JD shortcut opens and focuses the job-description field (§15/§29)", () => {
    render(<AgentPrepareWorkspace initialDraft={{ source: "home", action: "job_description" }} />);
    const jd = screen.getByLabelText("Job description (optional)");
    expect(jd).toBeInTheDocument();
    expect(document.activeElement).toBe(jd);
    expect(start).not.toHaveBeenCalled();
  });

  it("the background shortcut opens and focuses the background field (§16/§30)", () => {
    render(<AgentPrepareWorkspace initialDraft={{ source: "home", action: "candidate_background" }} />);
    const bg = screen.getByLabelText("Your background (optional)");
    expect(bg).toBeInTheDocument();
    expect(document.activeElement).toBe(bg);
  });
});

describe("Home → Prepare (deterministic fallback §14)", () => {
  it("auto-submits the transferred goal to the career coach", async () => {
    chat.mockResolvedValue({ answer: "ok", sources: [], citations: [] });
    render(<PrepareWorkspace initialDraft={START_DRAFT} />);
    await waitFor(() => expect(chat).toHaveBeenCalledTimes(1));
    expect(chat.mock.calls[0][0]).toMatchObject({ question: START_DRAFT.goal });
  });

  it("a shortcut opens the context section and focuses JD without a chat call", () => {
    render(<PrepareWorkspace initialDraft={{ source: "home", action: "job_description" }} />);
    const jd = document.getElementById("ctx-jd");
    expect(jd).toBeInTheDocument();
    expect(document.activeElement).toBe(jd);
    expect(chat).not.toHaveBeenCalled();
  });
});
