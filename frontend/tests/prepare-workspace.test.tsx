import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const chat = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/client", () => ({
  api: {
    career: {
      chat: (...a: unknown[]) => chat(...a),
      jobAnalysis: vi.fn(),
      gapAnalysis: vi.fn(),
      preparationPlan: vi.fn(),
      questions: vi.fn(),
    },
    interviews: { create: vi.fn(), get: vi.fn() },
  },
}));

import { PrepareWorkspace } from "@/components/preparation/PrepareWorkspace";

const grounded = {
  answer: "Focus on executive communication and commercial ownership.",
  citations: [],
  sources: [{ title: "O*NET Product manager", source_url: "https://onet" }],
  tools: [],
  input_flagged: false,
  has_evidence: true,
  preparation_available: true,
};

afterEach(() => vi.clearAllMocks());

describe("Prepare workspace", () => {
  it("submits a typed request and renders the grounded response + sources", async () => {
    chat.mockResolvedValue(grounded);
    render(<PrepareWorkspace />);
    await userEvent.type(
      screen.getByLabelText("Ask the coach"),
      "What should I focus on?",
    );
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(chat).toHaveBeenCalledWith(
      expect.objectContaining({ question: "What should I focus on?" }),
      expect.objectContaining({ signal: expect.anything() }),
    );
    expect(await screen.findByText(/executive communication/i)).toBeInTheDocument();
    // Citations/sources render (candidate-facing "Career evidence").
    expect(screen.getByText(/Career evidence: 1 source/i)).toBeInTheDocument();
  });

  it("renders the insufficient-evidence state without fabricating an answer", async () => {
    chat.mockResolvedValue({ ...grounded, has_evidence: false, sources: [] });
    render(<PrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("Ask the coach"), "obscure question");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(
      await screen.findByText(/don’t have enough reliable evidence/i),
    ).toBeInTheDocument();
  });

  it("shows no fabricated readiness score and no chain-of-thought", async () => {
    chat.mockResolvedValue(grounded);
    const { container } = render(<PrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("Ask the coach"), "hi");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText(/executive communication/i);
    const text = container.textContent || "";
    expect(text).not.toMatch(/\b\d{1,3}\s*%/); // no fake percentage readiness
    expect(text.toLowerCase()).not.toContain("thinking");
    expect(text.toLowerCase()).not.toContain("chain-of-thought");
    expect(text.toLowerCase()).not.toContain("reasoning");
  });

  it("Start practice is disabled until a target role exists", () => {
    render(<PrepareWorkspace />);
    expect(
      screen.getByRole("button", { name: /Start interview practice/i }),
    ).toBeDisabled();
  });

  it("uses safe observable activity text while waiting (never 'thinking')", async () => {
    let resolve: (v: unknown) => void = () => {};
    chat.mockImplementation(() => new Promise((r) => (resolve = r)));
    render(<PrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("Ask the coach"), "hi");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(screen.getByText(/Checking career evidence/i)).toBeInTheDocument();
    resolve(grounded);
    await waitFor(() => expect(screen.queryByText(/Checking career evidence/i)).not.toBeInTheDocument());
  });
});
