import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const sources = vi.fn();
const snapshot = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    knowledge: {
      sources: (...a: unknown[]) => sources(...a),
      snapshot: (...a: unknown[]) => snapshot(...a),
    },
  },
}));

import { SourcesClient } from "@/components/preparation/SourcesClient";

afterEach(() => vi.clearAllMocks());

describe("Sources — safe links & provenance", () => {
  it("links a source with a public https URL, opening safely in a new tab", async () => {
    snapshot.mockResolvedValue(null);
    sources.mockResolvedValue({
      sources: [
        { source_id: "onet", title: "O*NET Database", group: "occupations", source_type: "occupation_taxonomy", source_url: "https://www.onetcenter.org/", provider: "official", country: "US", reference_year: null },
      ],
    });
    render(<SourcesClient />);

    const link = await screen.findByRole("link", { name: "O*NET Database" });
    expect(link).toHaveAttribute("href", "https://www.onetcenter.org/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("keeps a governed source inspectable but NOT linked when it has no public URL", async () => {
    snapshot.mockResolvedValue(null);
    sources.mockResolvedValue({
      sources: [
        { source_id: "internal_kb", title: "Governed dataset", group: "narrative", source_type: "internal", source_url: null, provider: "official", country: null, reference_year: 2025 },
      ],
    });
    render(<SourcesClient />);

    expect(await screen.findByText("Governed dataset")).toBeInTheDocument();
    // No fabricated link.
    expect(screen.queryByRole("link", { name: "Governed dataset" })).not.toBeInTheDocument();
    // Still inspectable: provenance + a transparent note.
    expect(screen.getByText(/Governed source · no public record link/)).toBeInTheDocument();
    expect(screen.getByText(/official/)).toBeInTheDocument();
  });
});
