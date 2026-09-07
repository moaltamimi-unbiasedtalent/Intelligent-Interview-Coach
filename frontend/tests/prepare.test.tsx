import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrepareResponsive } from "@/components/preparation/PrepareResponsive";

describe("Prepare responsive workspace", () => {
  it("offers a mobile Coach / Preparation context control", () => {
    render(
      <PrepareResponsive
        coach={<p>coach panel</p>}
        context={<p>context panel</p>}
      />,
    );
    // The mobile tab set exposes both a Coach and a Preparation control.
    expect(screen.getByRole("tab", { name: "Coach" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Preparation" })).toBeInTheDocument();
  });
});
