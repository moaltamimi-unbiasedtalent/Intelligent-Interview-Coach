import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Ask4Mo brand identity on the Home experience (§24): primary brand, descriptor,
// slogan and the "Ask Mo" CTA. HomeEntry needs a router; mock next/navigation.

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import HomePage from "@/app/page";
import { Brand } from "@/components/layout/Brand";

describe("Ask4Mo brand — Home", () => {
  it("shows Ask4Mo as the primary brand", () => {
    render(<HomePage />);
    expect(screen.getAllByText("Ask4Mo").length).toBeGreaterThan(0);
  });

  it("shows Intelligent Interview Coach as the descriptor", () => {
    render(<HomePage />);
    expect(screen.getByText("Intelligent Interview Coach")).toBeInTheDocument();
  });

  it("shows the slogan 'Ask More. Be More.'", () => {
    render(<HomePage />);
    expect(screen.getByText("Ask More. Be More.")).toBeInTheDocument();
  });

  it("uses 'Ask Mo' as the primary CTA", () => {
    render(<HomePage />);
    expect(screen.getByRole("button", { name: "Ask Mo" })).toBeInTheDocument();
  });

  it("references Mo in the supporting copy", () => {
    render(<HomePage />);
    expect(screen.getByText(/Tell Mo what you/i)).toBeInTheDocument();
  });
});

describe("Ask4Mo brand — header wordmark", () => {
  it("is an accessible home link named 'Ask4Mo — home'", () => {
    render(<Brand />);
    const link = screen.getByRole("link", { name: "Ask4Mo — home" });
    expect(link).toHaveAttribute("href", "/");
    expect(link).toHaveTextContent("Ask4Mo");
  });
});
