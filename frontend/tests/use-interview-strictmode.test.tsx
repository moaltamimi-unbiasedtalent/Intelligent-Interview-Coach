import { StrictMode } from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { InterviewStateResponse } from "@/lib/api/types";

// Phase 5.3 regression (Golden Demo Live Rehearsal #3, P1).
//
// React StrictMode (enabled in dev via next.config `reactStrictMode: true`) runs an
// effect mount → cleanup → mount again. `useInterview` must restore its `mounted` ref
// to true on the second mount; otherwise the cleanup's `mounted.current = false`
// persists, the successful session GET is discarded by `if (!mounted.current) return`,
// and Practice stays on its loading skeleton until a manual browser reload.
//
// This renders the REAL PracticeClient under <StrictMode>, which genuinely double-
// invokes effects in this environment (render() double-invokes; renderHook does not).
// The test fails against the pre-fix hook and passes with the fix.

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
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    interviews: iv,
    feedback: { get: () => Promise.resolve(null), submit: vi.fn(), remove: vi.fn() },
  },
}));

import { PracticeClient } from "@/components/interview/PracticeClient";

const STATE: InterviewStateResponse = {
  session_id: "sess-1",
  state: "AWAITING_ANSWER",
  question_number: 1,
  questions_planned: 6,
  current_question: {
    question_id: 1, question: "Tell me about a difficult prioritisation decision.",
    question_type: "behavioural", competency: "judgement", difficulty: "moderate",
  },
  report_available: false,
  last_evaluation: null,
  target_role: "Senior Product Manager",
  deep_dive: null,
  error: null,
  error_recoverable: false,
  cumulative_cost_usd: 0,
};

afterEach(() => vi.clearAllMocks());

describe("Practice load under React StrictMode", () => {
  it("renders Q1 after the StrictMode mount→cleanup→mount cycle (no reload)", async () => {
    iv.get.mockResolvedValue(STATE);
    iv.options.mockResolvedValue({ deep_dive_modes: [] });

    render(
      <StrictMode>
        <PracticeClient sessionId="sess-1" />
      </StrictMode>,
    );

    // The session GET resolves AFTER StrictMode's simulated remount; the restored
    // `mounted` flag must let its result through and replace the loading skeleton.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /difficult prioritisation decision/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Preparing your interview/i)).not.toBeInTheDocument();
  });

  it("does not apply a session response that resolves after a genuine unmount", async () => {
    let resolve!: (s: InterviewStateResponse) => void;
    iv.get.mockReturnValue(new Promise<InterviewStateResponse>((r) => { resolve = r; }));
    iv.options.mockResolvedValue({ deep_dive_modes: [] });

    const { unmount } = render(<PracticeClient sessionId="sess-1" />);
    // Still loading; nothing fetched yet.
    expect(screen.getByText(/Preparing your interview/i)).toBeInTheDocument();

    unmount(); // genuine unmount → mounted.current stays false
    await act(async () => { resolve(STATE); await Promise.resolve(); });

    // The stale-response guard held: no question leaked into the (unmounted) tree.
    expect(screen.queryByText(/difficult prioritisation decision/i)).not.toBeInTheDocument();
  });
});
