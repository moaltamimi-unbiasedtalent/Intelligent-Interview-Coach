import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ErrorState } from "@/components/ui/States";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("") }));
vi.mock("@/lib/api/client", () => ({ api: { agent: { getRun: vi.fn() } } }));

describe("Agent Inspector (empty state)", () => {
  afterEach(() => vi.clearAllMocks());

  it("prompts for a run id and fabricates no agent metrics", async () => {
    const { AgentInspector } = await import("@/components/agent/AgentInspector");
    const { container } = render(<AgentInspector />);
    expect(screen.getByText(/Enter a run ID to inspect/i)).toBeInTheDocument();
    // No fabricated metric VALUES before a real run is loaded.
    const text = container.textContent || "";
    expect(text).not.toMatch(/\$\d/); // no fake cost
    expect(text).not.toMatch(/\d[\d,]*\s*tokens/i); // no fake token counts
    expect(text).not.toMatch(/run_[a-z0-9]/i); // no fake run id
  });
});

describe("ErrorState", () => {
  it("shows a calm safe message and keeps any reference id out of the main body", () => {
    render(
      <ErrorState
        message="That request couldn't be processed. Please try again."
        requestId="req_abc123"
      />,
    );
    expect(
      screen.getByText(/That request couldn't be processed/i),
    ).toBeInTheDocument();
    // Raw reference is tucked into an optional details disclosure, not shouted.
    const details = screen.getByText(/Technical details/i);
    expect(details.tagName.toLowerCase()).toBe("summary");
  });
});
