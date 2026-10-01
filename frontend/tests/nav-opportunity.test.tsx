import { render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

// P10B-W9.4 - Opportunity navigation salience & accessibility (D4/D5/D6).

let mockPath = "/app";
vi.mock("next/navigation", () => ({ usePathname: () => mockPath }));

import { PRIMARY_NAV } from "@/components/layout/nav-items";
import { PrimaryNavigation } from "@/components/layout/PrimaryNavigation";
import { MobileNavigation } from "@/components/layout/MobileNavigation";

afterEach(() => vi.clearAllMocks());

// D4 - desktop: Opportunities first, accessible, not hidden; all primary routes present (D6).
it("D4/D6: Opportunities is first in primary nav and all candidate routes remain present", () => {
  expect(PRIMARY_NAV[0].href).toBe("/opportunities");
  mockPath = "/app";
  render(<PrimaryNavigation />);
  const nav = screen.getByRole("navigation", { name: "Primary" });
  for (const label of ["Opportunities", "Prepare", "Practice", "Progress", "History"]) {
    expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
  }
  // Opportunities is reachable (not visually suppressed to muted-only — it carries the legible class).
  const opp = within(nav).getByRole("link", { name: "Opportunities" });
  expect(opp).toHaveAttribute("href", "/opportunities");
  expect(opp.className).not.toContain("text-muted");
});

it("D4: Opportunities nav is marked active on /opportunities", () => {
  mockPath = "/opportunities";
  render(<PrimaryNavigation />);
  const opp = screen.getByRole("link", { name: "Opportunities" });
  expect(opp).toHaveAttribute("aria-current", "page");
});

it("D4: a child opportunity route still marks the nav active", () => {
  mockPath = "/opportunities/42";
  render(<PrimaryNavigation />);
  expect(screen.getByRole("link", { name: "Opportunities" })).toHaveAttribute("aria-current", "page");
});

// D5 - mobile: accessible name intact (full "Opportunities"), active state works, not muted-only.
it("D5: mobile Opportunities keeps the full accessible name and is not ambiguously suppressed", () => {
  mockPath = "/app";
  render(<MobileNavigation />);
  const nav = screen.getByRole("navigation", { name: "Primary" });
  const opp = within(nav).getByRole("link", { name: "Opportunities" }); // aria-label = full word
  expect(opp).toHaveAttribute("href", "/opportunities");
  expect(opp.className).not.toContain("text-muted");
  // The visible label is not clipped with an ellipsis (no `truncate`).
  expect(opp.innerHTML).not.toContain("truncate");
});

it("D5: mobile Opportunities shows an active state on /opportunities", () => {
  mockPath = "/opportunities";
  render(<MobileNavigation />);
  expect(screen.getByRole("link", { name: "Opportunities" })).toHaveAttribute("aria-current", "page");
});
