import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/AppShell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/prepare",
}));

describe("AppShell", () => {
  it("renders children and the product branding", () => {
    render(<AppShell>
      <p>Hello content</p>
    </AppShell>);
    expect(screen.getByText("Hello content")).toBeInTheDocument();
    // Branding appears (wordmark).
    expect(screen.getAllByText("Intelligent Interview Coach").length).toBeGreaterThan(0);
  });

  it("exposes the four primary navigation destinations", () => {
    render(<AppShell><span /></AppShell>);
    // Primary nav renders in both desktop header and mobile bar; assert each label.
    for (const label of ["Prepare", "Practice", "Progress", "History"]) {
      expect(screen.getAllByRole("link", { name: label }).length).toBeGreaterThan(0);
    }
  });

  it("marks the active route with aria-current", () => {
    render(<AppShell><span /></AppShell>);
    const current = screen.getAllByRole("link", { name: "Prepare" });
    expect(current.some((el) => el.getAttribute("aria-current") === "page")).toBe(true);
  });

  it("provides a skip link to content", () => {
    render(<AppShell><span /></AppShell>);
    expect(screen.getByText("Skip to content")).toHaveAttribute("href", "#main");
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main");
    // sanity: content region is a landmark
    within(main);
  });
});
