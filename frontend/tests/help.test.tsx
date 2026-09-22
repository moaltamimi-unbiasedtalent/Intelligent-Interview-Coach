import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { HelpCenter } from "@/components/help/HelpCenter";

describe("Help Center", () => {
  it("covers every required section", () => {
    render(<HelpCenter />);
    for (const s of [
      "Getting started", "Prepare", "Practice", "Progress", "History",
      "Sources", "Memory & approvals", "Privacy & safety", "Troubleshooting",
      "Reviewer & technical guide",
    ]) {
      expect(screen.getByRole("heading", { name: s })).toBeInTheDocument();
    }
  });

  it("offers a replayable guided tour", () => {
    render(<HelpCenter />);
    expect(screen.getByRole("button", { name: "Take the tour" })).toBeInTheDocument();
  });

  it("filters topics with local search (no LLM, no network)", async () => {
    render(<HelpCenter />);
    await userEvent.type(screen.getByLabelText("Search help"), "inventing");
    // The "why evidence may be unavailable" article mentions not inventing a citation.
    expect(screen.getByText(/says so rather than inventing a citation/i)).toBeInTheDocument();
    // Unrelated sections are filtered out.
    expect(screen.queryByRole("heading", { name: "Troubleshooting" })).not.toBeInTheDocument();
  });

  it("anchors sections for contextual deep-links", () => {
    const { container } = render(<HelpCenter />);
    for (const id of ["getting-started", "prepare", "practice", "progress", "history", "sources", "memory", "privacy", "troubleshooting", "reviewer"]) {
      expect(container.querySelector(`#${id}`)).toBeTruthy();
    }
  });
});
