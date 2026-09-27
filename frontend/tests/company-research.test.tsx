import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// P10B Wave 5 - Company Intelligence UI: claim-kind separation (FACT / REVIEW / AI suggestion),
// provenance, honest not-integrated review providers, and the request lifecycle states.

const research = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { company: { research: (b: unknown) => research(b) } } }));
// The JD picker fetches documents on mount; stub it out to keep the test focused + offline.
vi.mock("@/components/documents/DocumentPicker", () => ({ DocumentPicker: () => null }));

import { ApiError } from "@/lib/api/errors";
import type { CompanyIntelligenceReport } from "@/lib/api/types";
import { CompanyReport } from "@/components/company/CompanyReport";
import { CompanyResearchClient } from "@/components/company/CompanyResearchClient";

afterEach(() => vi.clearAllMocks());

function sample(over: Partial<CompanyIntelligenceReport> = {}): CompanyIntelligenceReport {
  return {
    status: "ready",
    identity: { company_name: "Acme", confidence: "confirmed", website: "https://acme.example",
                domain: "acme.example", location: "Berlin", country: "DE", note: null },
    snapshot: { description: "Acme builds software.", website: "https://acme.example",
                retrieved_at: "2026-01-15T09:00:00Z", industry: null },
    business_market: [{ kind: "fact", text: "Acme builds software products.", source_ids: ["s1"] }],
    recent_developments: [],
    culture: [{ kind: "fact", text: "Values: integrity and sustainability.", source_ids: ["s1"] }],
    review_signals: [],
    role_relevance: [{ kind: "model_inference", text: "Connect Acme to the Engineer role.", source_ids: ["s1"] }],
    interview_preparation: {
      topics: [{ kind: "model_inference", text: "Understand: Acme builds software products.", source_ids: ["s1"] }],
      questions_to_ask: [{ kind: "model_inference", text: "What are the team priorities?", source_ids: [] }],
      clarify: [],
    },
    sources: [{ id: "s1", title: "Acme - About", url: "https://acme.example/about",
                source_type: "company_official_web", provider: "company_web",
                retrieved_at: "2026-01-15T09:00:00Z", effective_date: null, self_reported: true }],
    provider_statuses: [
      { key: "company_web", label: "Official company website", state: "configured", detail: null, external_url: "https://acme.example" },
      { key: "glassdoor", label: "Glassdoor reviews", state: "not_integrated", detail: null, external_url: "https://www.google.com/search?q=Acme+Glassdoor" },
    ],
    limitations: ["reviews_not_integrated", "market_data_unvalidated"],
    warnings: [],
    retrieved_at: "2026-01-15T09:00:00Z",
    cache_hit: false,
    jd_linked: false,
    ...over,
  };
}

describe("Wave 5 - CompanyReport", () => {
  it("renders FACT, REVIEW-provider and MODEL_INFERENCE distinctly with provenance", () => {
    render(<CompanyReport report={sample()} />);
    // Claim kinds are labelled (never blurred): at least one Fact and one AI suggestion tag.
    expect(screen.getAllByText("Fact").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AI suggestion").length).toBeGreaterThan(0);
    // Provenance: the source appears as a link.
    const src = screen.getAllByRole("link", { name: "Acme - About" });
    expect(src[0]).toHaveAttribute("href", "https://acme.example/about");
    // Reviews are not fabricated: the not-integrated notice + a link-only Glassdoor entry.
    expect(screen.getByText(/does not copy review content/i)).toBeInTheDocument();
    const gd = screen.getByRole("link", { name: /Glassdoor reviews/i });
    expect(gd).toHaveAttribute("href", "https://www.google.com/search?q=Acme+Glassdoor");
    expect(gd).toHaveAttribute("rel", expect.stringContaining("nofollow"));
    // The interview-intelligence disclaimer is present.
    expect(screen.getByText(/not an employer rating/i)).toBeInTheDocument();
  });
});

describe("Wave 5 - CompanyResearchClient", () => {
  it("submits a query and renders the report", async () => {
    research.mockResolvedValue(sample());
    render(<CompanyResearchClient />);
    await userEvent.type(screen.getByPlaceholderText(/Acme GmbH/i), "Acme");
    await userEvent.click(screen.getByRole("button", { name: /Research company/i }));
    await waitFor(() => expect(research).toHaveBeenCalledTimes(1));
    expect(research.mock.calls[0][0]).toMatchObject({ company_name: "Acme" });
    expect(await screen.findByText("Company snapshot")).toBeInTheDocument();
  });

  it("shows the clarification state when identity is unconfirmed", async () => {
    research.mockResolvedValue(sample({
      status: "needs_clarification",
      identity: { company_name: "Acme", confidence: "needs_clarification", website: null,
                  domain: null, location: "Berlin", country: null, note: null },
      business_market: [], culture: [], role_relevance: [], sources: [],
      interview_preparation: { topics: [], questions_to_ask: [], clarify: [] },
    }));
    render(<CompanyResearchClient />);
    await userEvent.type(screen.getByPlaceholderText(/Acme GmbH/i), "Acme");
    await userEvent.click(screen.getByRole("button", { name: /Research company/i }));
    expect(await screen.findByText(/Which company exactly/i)).toBeInTheDocument();
  });

  it("shows a safe error and does not render a report on failure", async () => {
    research.mockRejectedValue(new ApiError({
      kind: "server", status: 503, code: "http_error",
      message: "This feature is temporarily paused by the operator. Please try again later.",
      requestId: "req_1",
    }));
    render(<CompanyResearchClient />);
    await userEvent.type(screen.getByPlaceholderText(/Acme GmbH/i), "Acme");
    await userEvent.click(screen.getByRole("button", { name: /Research company/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily paused/i);
    expect(screen.queryByText("Company snapshot")).not.toBeInTheDocument();
  });
});
