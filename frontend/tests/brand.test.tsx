import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Ask4Mo brand identity on the authenticated Home experience (§24): descriptor, slogan and
// the "Ask Mo" CTA. Post-P8 the candidate home lives at /app; HomeEntry needs a router.

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import AppHomePage from "@/app/app/page";
import { Brand } from "@/components/layout/Brand";

describe("Ask4Mo brand — authenticated Home (/app)", () => {
  it("shows Intelligent Interview Coach as the descriptor", () => {
    render(<AppHomePage />);
    expect(screen.getByText("Intelligent Interview Coach")).toBeInTheDocument();
  });

  it("shows the slogan 'Ask More. Be More.'", () => {
    render(<AppHomePage />);
    expect(screen.getByText("Ask More. Be More.")).toBeInTheDocument();
  });

  it("uses 'Ask Mo' as the primary CTA", () => {
    render(<AppHomePage />);
    expect(screen.getByRole("button", { name: "Ask Mo" })).toBeInTheDocument();
  });

  it("references Mo in the supporting copy", () => {
    render(<AppHomePage />);
    expect(screen.getByText(/Tell Mo what you/i)).toBeInTheDocument();
  });
});

describe("Ask4Mo brand — header wordmark", () => {
  it("is an accessible link to the app home named 'Ask4Mo — home'", () => {
    render(<Brand />);
    const link = screen.getByRole("link", { name: "Ask4Mo — home" });
    // P8: inside the product the wordmark links to the authenticated home (/app).
    expect(link).toHaveAttribute("href", "/app");
    expect(link).toHaveTextContent("Ask4Mo");
  });
});
