import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const list = vi.fn();
const get = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    history: { list: (...a: unknown[]) => list(...a), get: (...a: unknown[]) => get(...a) },
    reports: {
      exportMarkdownUrl: (id: number) => `/api/v1/reports/${id}/export.md`,
      exportJsonUrl: (id: number) => `/api/v1/reports/${id}/export.json`,
    },
  },
}));

import { HistoryClient } from "@/components/interview/HistoryClient";
import { HistoryDetailClient } from "@/components/interview/HistoryDetailClient";

afterEach(() => vi.clearAllMocks());

describe("History — list rows are viewable", () => {
  it("shows metadata and links each session to its detail page", async () => {
    list.mockResolvedValue({
      interviews: [
        { id: 36, target_role: "Backend Software Engineer", status: "completed", questions: 3, created_at: "2026-09-21T09:28:28" },
      ],
    });
    render(<HistoryClient />);

    const link = await screen.findByRole("link", { name: /Backend Software Engineer/ });
    expect(link).toHaveAttribute("href", "/history/36");
    expect(screen.getByText(/3 question\(s\)/)).toBeInTheDocument();
  });
});

describe("History — detail view", () => {
  it("renders the saved performance review for a session", async () => {
    get.mockResolvedValue({
      interview: {
        id: 36,
        configuration: { target_role: "Backend Software Engineer" },
        status: "completed",
        created_at: "2026-09-21T09:28:28",
        questions: [],
        report: {
          report: {
            overall_readiness_score: 82,
            performance_summary: "Solid, evidence-based answers.",
            strongest_competencies: ["REST API design"],
          },
          usage: null,
          cost_usd: null,
        },
      },
    });
    render(<HistoryDetailClient reportId="36" />);

    expect(await screen.findByText("Performance review")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("Solid, evidence-based answers.")).toBeInTheDocument();
    expect(screen.getByText("REST API design")).toBeInTheDocument();
  });

  it("shows a safe not-found state for a foreign/unknown id (404), never another user's data", async () => {
    get.mockRejectedValue(Object.assign(new Error("nope"), { status: 404, userMessage: "Not found." }));
    render(<HistoryDetailClient reportId="999" />);
    expect(await screen.findByText("Session not found")).toBeInTheDocument();
  });
});
