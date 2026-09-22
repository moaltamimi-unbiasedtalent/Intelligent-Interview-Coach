import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HelpPage from "@/app/help/page";

describe("Help / How Ask4Mo works", () => {
  it("explains each journey surface and the key concepts", () => {
    render(<HelpPage />);
    // Journey surfaces.
    for (const s of ["Ask Mo", "Prepare", "Practise", "Progress", "History", "Sources", "Review & Diagnostics"]) {
      expect(screen.getByText(s)).toBeInTheDocument();
    }
    // Key concepts (safety framing).
    expect(screen.getByText(/AI coach, not an autonomous decision-maker/i)).toBeInTheDocument();
    expect(screen.getByText(/Human-in-the-loop/i)).toBeInTheDocument();
    expect(screen.getByText(/Memory approval/i)).toBeInTheDocument();
    expect(screen.getByText(/Governed sources/i)).toBeInTheDocument();
  });
});
