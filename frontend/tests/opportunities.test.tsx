import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// P10B Wave 6 - Opportunities UI: list/empty states + the create wizard (role required, 4 steps).

const list = vi.fn();
const create = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { opportunities: { list: (...a: unknown[]) => list(...a), create: (...a: unknown[]) => create(...a) } },
}));
vi.mock("@/components/documents/DocumentPicker", () => ({ DocumentPicker: () => null }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), prefetch: vi.fn() }),
  // W9.4: OpportunitiesClient reads ?create=1 to deep-link into the inline create flow.
  useSearchParams: () => new URLSearchParams(""),
}));

import { OpportunitiesClient } from "@/components/opportunities/OpportunitiesClient";
import { OpportunityStatusBadge } from "@/components/opportunities/OpportunityStatusBadge";

afterEach(() => vi.clearAllMocks());

describe("Wave 6 - Opportunities list", () => {
  it("shows the empty state when there are no opportunities", async () => {
    list.mockResolvedValue({ opportunities: [] });
    render(<OpportunitiesClient />);
    expect(await screen.findByText(/Start with an opportunity/i)).toBeInTheDocument();
  });

  it("renders opportunities with a status label (never colour alone)", async () => {
    list.mockResolvedValue({
      opportunities: [
        { id: 1, title: "Senior PM - Acme - Berlin", target_role: "Senior PM", company_name: "Acme",
          company_location: "Berlin", status: "interviewing" },
      ],
    });
    render(<OpportunitiesClient />);
    expect(await screen.findByText("Senior PM - Acme - Berlin")).toBeInTheDocument();
    expect(screen.getByText("Interviewing")).toBeInTheDocument();
  });
});

describe("Wave 6 - OpportunityStatusBadge", () => {
  it("labels each bounded status", () => {
    const { rerender } = render(<OpportunityStatusBadge status="offer" />);
    expect(screen.getByText("Offer")).toBeInTheDocument();
    rerender(<OpportunityStatusBadge status="archived" />);
    expect(screen.getByText("Archived")).toBeInTheDocument();
  });
});

describe("Wave 6 - Create wizard", () => {
  it("requires a role, walks the steps, and creates", async () => {
    create.mockResolvedValue({ id: 7 });
    const onCreated = vi.fn();
    const { OpportunityCreate } = await import("@/components/opportunities/OpportunityCreate");
    render(<OpportunityCreate onCancel={vi.fn()} onCreated={onCreated} />);

    // Step 1 (Role): Continue is disabled until a role is entered.
    const next = screen.getByRole("button", { name: "Continue" });
    expect(next).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText(/Senior Product Manager/i), "Senior PM");
    expect(next).toBeEnabled();

    // Step 2 (Company)
    await userEvent.click(next);
    await userEvent.type(screen.getByPlaceholderText(/Acme GmbH/i), "Acme");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Step 3 (JD) -> Continue to Review
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Step 4 (Review) -> Create
    await userEvent.click(screen.getByRole("button", { name: /Create opportunity/i }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0][0]).toMatchObject({ target_role: "Senior PM", company_name: "Acme" });
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(7));
  });
});
