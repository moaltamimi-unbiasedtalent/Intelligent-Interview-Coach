import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CapabilitiesResponse } from "@/lib/api/types";

const state = { value: false };
vi.mock("@/lib/useCapabilities", () => ({
  useCapabilities: () => {
    const capabilities: CapabilitiesResponse = {
      career_intelligence: true,
      interview_practice: true,
      knowledge_base: true,
      evaluation: true,
      live_interview_enabled: state.value,
      agentic_rag: false,
      agent_memory: false,
      human_in_the_loop: false,
      agent_coach_enabled: false,
    };
    return { capabilities, loading: false, offline: false };
  },
}));

import { PracticeClient } from "@/components/interview/PracticeClient";

describe("Practice", () => {
  it("offers Type and Record and does not offer Live when the capability is false", () => {
    state.value = false;
    render(<PracticeClient />);
    expect(screen.getByRole("button", { name: /type/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /record/i })).toBeInTheDocument();
    expect(screen.queryByText(/Live conversation practice/i)).not.toBeInTheDocument();
  });

  it("mentions Live only when the backend capability is true", () => {
    state.value = true;
    render(<PracticeClient />);
    expect(screen.getByText(/Live conversation practice/i)).toBeInTheDocument();
  });

  it("never claims camera use", () => {
    state.value = false;
    render(<PracticeClient />);
    expect(screen.getByText(/No camera/i)).toBeInTheDocument();
  });
});
