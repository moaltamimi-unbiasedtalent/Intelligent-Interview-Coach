import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PrepareResponsive } from "@/components/preparation/PrepareResponsive";

function setMobile(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => vi.restoreAllMocks());

describe("Prepare responsive workspace", () => {
  it("mobile shows a Coach / Preparation tab control (rendered once)", () => {
    setMobile(true);
    render(<PrepareResponsive coach={<p>coach panel</p>} context={<p>context panel</p>} />);
    expect(screen.getByRole("tab", { name: "Mo" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Preparation" })).toBeInTheDocument();
  });

  it("desktop shows both panels side by side without duplicating them", () => {
    setMobile(false);
    render(<PrepareResponsive coach={<p>coach panel</p>} context={<p>context panel</p>} />);
    // Each panel appears exactly once (no duplicate DOM / duplicate ids).
    expect(screen.getAllByText("coach panel")).toHaveLength(1);
    expect(screen.getAllByText("context panel")).toHaveLength(1);
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
