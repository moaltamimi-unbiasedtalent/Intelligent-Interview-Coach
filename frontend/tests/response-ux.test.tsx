import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Disclosure } from "@/components/ui/Disclosure";
import { AgentAnswer } from "@/components/agent/AgentAnswer";
import type { ResponsePresentation } from "@/lib/api/types";

describe("Disclosure", () => {
  it("hides content until expanded and is keyboard/ARIA accessible", async () => {
    render(
      <Disclosure>
        <p>hidden detail</p>
      </Disclosure>,
    );
    const btn = screen.getByRole("button", { name: "Show more" });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("hidden detail")).not.toBeInTheDocument();

    await userEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("hidden detail")).toBeInTheDocument();
    expect(btn).toHaveAccessibleName("Show less");

    await userEvent.click(btn);
    expect(screen.queryByText("hidden detail")).not.toBeInTheDocument();
  });
});

const WITH_DETAILS: ResponsePresentation = {
  answer: "The brief answer.",
  details: "The supporting detail.",
  has_details: true,
  next_step: { label: "Start interview practice", kind: "start_practice" },
};

const NO_DETAILS: ResponsePresentation = {
  answer: "A complete short answer.",
  details: "",
  has_details: false,
  next_step: null,
};

describe("AgentAnswer", () => {
  it("brief mode shows the answer + next step, details behind Show more", async () => {
    render(<AgentAnswer presentation={WITH_DETAILS} detailed={false} />);
    expect(screen.getByText("The brief answer.")).toBeInTheDocument();
    expect(screen.getByText(/Start interview practice/)).toBeInTheDocument();
    // Details collapsed initially.
    expect(screen.queryByText("The supporting detail.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByText("The supporting detail.")).toBeInTheDocument();
  });

  it("detailed mode shows details inline (no Show more)", () => {
    render(<AgentAnswer presentation={WITH_DETAILS} detailed={true} />);
    expect(screen.getByText("The brief answer.")).toBeInTheDocument();
    expect(screen.getByText("The supporting detail.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("renders nothing extra when there are no details or next step", () => {
    render(<AgentAnswer presentation={NO_DETAILS} detailed={false} />);
    expect(screen.getByText("A complete short answer.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Next step/)).not.toBeInTheDocument();
  });
});
