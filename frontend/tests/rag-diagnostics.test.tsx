import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const diagnostics = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { knowledge: { diagnostics: (...a: unknown[]) => diagnostics(...a) } },
}));

import { RagDiagnosticsClient } from "@/components/review/RagDiagnosticsClient";

afterEach(() => vi.clearAllMocks());

describe("Knowledge & RAG diagnostics", () => {
  it("shows runtime counts, offline retrieval quality and known gaps", async () => {
    diagnostics.mockResolvedValue({
      runtime: {
        occupations: 8035, aliases: 23579, skills: 111455, tasks: 22383,
        knowledge_areas: 6968, work_activities: 20141, compensation: 1913,
        labour_market: 2398, competencies: 2275, credentials: 5, sources: 31,
        runtime_pipeline_version: "7C.1", normalized_pipeline_version: "7B.1", built_at: "2026-09-12T06:50:02Z",
      },
      retrieval_evaluation: {
        cases: 81, passed: 74, pass_rate: 0.9136, evidence_coverage_rate: 0.8857,
        citation_completeness_rate: 1.0, geography_correctness_rate: 1.0,
        unknown_role_safety_rate: 1.0, unsupported_geography_safety_rate: 1.0,
        no_fabricated_citation_rate: 1.0, safety_pass_rate: 1.0,
      },
      known_gaps: ["German occupation-specific compensation is aggregate."],
    });
    render(<RagDiagnosticsClient />);

    expect(await screen.findByText("Knowledge runtime")).toBeInTheDocument();
    expect(screen.getByText("8,035")).toBeInTheDocument(); // occupations, formatted
    expect(screen.getByText("Offline retrieval evaluation")).toBeInTheDocument();
    expect(screen.getByText("74/81")).toBeInTheDocument(); // retrieval cases
    expect(screen.getByText("91%")).toBeInTheDocument(); // pass rate
    expect(screen.getByText(/German occupation-specific compensation/)).toBeInTheDocument();
    // No sensitive internals leak.
    const { container } = render(<RagDiagnosticsClient />);
    expect(container.textContent).not.toMatch(/embedding|api[_-]?key|sk-or-/i);
  });
});
