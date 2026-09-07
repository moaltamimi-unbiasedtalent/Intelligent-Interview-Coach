import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeToggle", () => {
  it("applies the dark token set by setting data-theme on the document", async () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("button", { name: /dark theme/i });
    await userEvent.click(btn);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    // Toggling back returns to light.
    await userEvent.click(screen.getByRole("button", { name: /light theme/i }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
