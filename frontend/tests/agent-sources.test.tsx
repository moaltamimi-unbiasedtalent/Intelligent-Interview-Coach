import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentSources } from "@/components/agent/AgentSources";
import type { AgentSource } from "@/lib/api/types";

// Candidate-facing citation UX (§7/§8): show only safe provenance (title, link, type,
// geography, year); never a fake Sources section when there is no evidence.

const SOURCE: AgentSource = {
  title: "O*NET Database — Registered Nurses — Skills",
  source_url: "https://www.onetonline.org/link/summary/29-1141.00",
  evidence_type: "role",
  geography: "US",
  reference_year: 2024,
} as AgentSource;

describe("AgentSources (candidate citation UX)", () => {
  it("renders a linked source with safe provenance only", () => {
    render(<AgentSources sources={[SOURCE]} />);
    expect(screen.getByText(/Career evidence: 1 source/i)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /O\*NET Database — Registered Nurses — Skills/ });
    expect(link).toHaveAttribute("href", SOURCE.source_url!);
    // Safe metadata is shown…
    expect(screen.getByText(/role · US · 2024/)).toBeInTheDocument();
  });

  it("renders NOTHING when there are no sources (no fake Sources section)", () => {
    const { container } = render(<AgentSources sources={[]} />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/Career evidence/i)).not.toBeInTheDocument();
  });

  it("shows a plain title (no link) when no public URL exists", () => {
    render(<AgentSources sources={[{ title: "ESCO occupation profile", evidence_type: "role" } as AgentSource]} />);
    expect(screen.getByText("ESCO occupation profile")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
