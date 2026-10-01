import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

// P10B-W9.4 - Home Opportunity entry (Pilot PF-10 discoverability).

const list = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { opportunities: { list: (...a: unknown[]) => list(...a) } } }));

let mockStatus: "authenticated" | "unauthenticated" = "authenticated";
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ status: mockStatus }),
}));

import { OpportunityEntry } from "@/components/home/OpportunityEntry";

beforeEach(() => {
  mockStatus = "authenticated";
  list.mockReset();
});
afterEach(() => vi.clearAllMocks());

// D1 - first-use: concept explained + a create-first CTA, with a view secondary.
it("D1: explains the Opportunity concept and offers a create-first CTA (zero opportunities)", async () => {
  list.mockResolvedValue({ opportunities: [] });
  render(<OpportunityEntry />);
  // Concept copy (plain language), targetable for Tutorial v2.
  expect(screen.getByRole("heading", { name: /prepare for a specific job/i })).toBeInTheDocument();
  expect(screen.getByText(/keeps everything for one job in one place/i)).toBeInTheDocument();
  // Primary CTA -> existing create flow (deep-link into the inline create form).
  const create = await screen.findByRole("link", { name: /create an opportunity/i });
  expect(create).toHaveAttribute("href", "/opportunities?create=1");
  // Secondary view path.
  expect(screen.getByRole("link", { name: /view your opportunities/i })).toHaveAttribute("href", "/opportunities");
});

// D2 - CTA navigation targets the REAL existing routes (no invented route).
it("D2: the create CTA deep-links into the existing /opportunities create flow", async () => {
  list.mockResolvedValue({ opportunities: [] });
  render(<OpportunityEntry />);
  const create = await screen.findByRole("link", { name: /create an opportunity/i });
  expect(create.getAttribute("href")).toBe("/opportunities?create=1");
});

// D3 - returning: do NOT say "create your first"; primary becomes "View your opportunities".
it("D3: with existing opportunities, primary action is View (not 'create your first')", async () => {
  list.mockResolvedValue({ opportunities: [{ id: 1 }, { id: 2 }] });
  render(<OpportunityEntry />);
  const view = await screen.findByRole("link", { name: /view your opportunities/i });
  expect(view).toHaveAttribute("href", "/opportunities");
  // Secondary "Create another" still available, and never "your first".
  expect(screen.getByRole("link", { name: /create another/i })).toHaveAttribute("href", "/opportunities?create=1");
  expect(screen.queryByText(/your first/i)).not.toBeInTheDocument();
});

// Safety: a failing opportunities read must not break Home (defaults to create-first).
it("falls back to the create CTA if the opportunities read fails", async () => {
  list.mockRejectedValue(new Error("boom"));
  render(<OpportunityEntry />);
  const create = await screen.findByRole("link", { name: /create an opportunity/i });
  expect(create).toHaveAttribute("href", "/opportunities?create=1");
});

// Not authenticated: no owner-scoped call is made.
it("makes no opportunities call when the identity is not resolved", async () => {
  mockStatus = "unauthenticated";
  render(<OpportunityEntry />);
  await waitFor(() => expect(screen.getByRole("heading", { name: /prepare for a specific job/i })).toBeInTheDocument());
  expect(list).not.toHaveBeenCalled();
});
