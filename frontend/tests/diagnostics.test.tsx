import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AgentInspectorPage from "@/app/review/agent/page";
import { ErrorState } from "@/components/ui/States";

describe("Agent Inspector (planned state)", () => {
  it("shows a planned/empty state and fabricates no agent metrics", () => {
    const { container } = render(<AgentInspectorPage />);
    expect(screen.getByText(/Agent runs will appear here/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing is fabricated/i)).toBeInTheDocument();
    // No fabricated metric VALUES on the empty diagnostic surface (a dollar cost,
    // a token count, or a run id). Descriptive words about what it *will* show are
    // fine; concrete fake numbers are not.
    const text = container.textContent || "";
    expect(text).not.toMatch(/\$\d/); // no fake cost
    expect(text).not.toMatch(/\d[\d,]*\s*tokens/i); // no fake token counts
    expect(text).not.toMatch(/run_[a-z0-9]/i); // no fake run id
    expect(text).not.toMatch(/\d+(\.\d+)?\s*s\b/); // no fake latency value
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
