import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const latest = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { evaluation: { latest: (...a: unknown[]) => latest(...a) } },
}));

import { EvaluationClient } from "@/components/review/EvaluationClient";

afterEach(() => vi.clearAllMocks());

describe("Review & Diagnostics — Evaluation", () => {
  it("shows stored offline metrics read-only when a run is available", async () => {
    latest.mockResolvedValue({
      available: true,
      metrics: { faithfulness: 0.4051, context_precision: 0.554 },
      run_config: { timestamp: "20260902_090140", status: "COMPLETE", case_count: 35, evaluator_model: "openai/gpt-4o-mini" },
    });
    render(<EvaluationClient />);

    expect(await screen.findByText("faithfulness")).toBeInTheDocument();
    expect(screen.getByText("0.405")).toBeInTheDocument();
    expect(screen.getByText("20260902_090140")).toBeInTheDocument();
    // Truthful separation: offline benchmark metrics, never live candidate analytics.
    expect(screen.getByText(/never triggers a paid evaluation/i)).toBeInTheDocument();
    expect(screen.getByText(/not live candidate analytics/i)).toBeInTheDocument();
  });

  it("shows an informative empty state when no run is stored", async () => {
    latest.mockResolvedValue({ available: false, metrics: null, run_config: null });
    render(<EvaluationClient />);
    expect(await screen.findByText("No stored evaluation run yet")).toBeInTheDocument();
  });
});
