import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "@/components/coach/Markdown";

describe("Markdown", () => {
  it("renders **bold** as <strong>, not literal asterisks", () => {
    const { container } = render(<Markdown text="Show **senior-level ownership** here." />);
    const strong = container.querySelector("strong");
    expect(strong?.textContent).toBe("senior-level ownership");
    expect(container.textContent).not.toContain("**");
  });

  it("renders unordered lists as <ul><li>", () => {
    const { container } = render(<Markdown text={"Prepare:\n- Story bank\n- Metrics"} />);
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("Story bank");
  });

  it("renders ordered lists as <ol><li> without the literal numbers", () => {
    const { container } = render(<Markdown text={"1. Job description\n2. Your background"} />);
    const items = container.querySelectorAll("ol li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("Job description");
    expect(container.textContent).not.toContain("1.");
  });

  it("renders headings without the leading hashes, with heading semantics", () => {
    render(<Markdown text={"## Behavioral round"} />);
    const heading = screen.getByText("Behavioral round");
    expect(heading.textContent).not.toContain("#");
    // Accessible heading semantics without injecting real <h1>–<h6> into the outline.
    expect(heading).toHaveAttribute("role", "heading");
    expect(heading).toHaveAttribute("aria-level", "4");
  });

  it("renders inline `code`", () => {
    const { container } = render(<Markdown text="Use the `STAR` structure." />);
    expect(container.querySelector("code")?.textContent).toBe("STAR");
  });

  it("leaves unmatched delimiters as literal text", () => {
    const { container } = render(<Markdown text="A lone * and ** stay literal." />);
    expect(container.textContent).toBe("A lone * and ** stay literal.");
    expect(container.querySelector("strong")).toBeNull();
  });

  it("separates blank-line-delimited paragraphs", () => {
    const { container } = render(<Markdown text={"First para.\n\nSecond para."} />);
    expect(container.querySelectorAll("p")).toHaveLength(2);
  });
});
