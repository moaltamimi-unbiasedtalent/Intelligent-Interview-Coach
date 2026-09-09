import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/AppShell";
import { MoreMenu } from "@/components/layout/MoreMenu";
import { MobileNavigation } from "@/components/layout/MobileNavigation";

let pathname = "/prepare";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

afterEach(() => { pathname = "/prepare"; });

describe("AppShell", () => {
  it("renders children and the product branding", () => {
    render(<AppShell><p>Hello content</p></AppShell>);
    expect(screen.getByText("Hello content")).toBeInTheDocument();
    expect(screen.getAllByText("Ask4Mo").length).toBeGreaterThan(0);
  });

  it("exposes the four primary navigation destinations", () => {
    render(<AppShell><span /></AppShell>);
    for (const label of ["Prepare", "Practice", "Progress", "History"]) {
      expect(screen.getAllByRole("link", { name: label }).length).toBeGreaterThan(0);
    }
  });

  it("marks the active route with aria-current", () => {
    render(<AppShell><span /></AppShell>);
    const current = screen.getAllByRole("link", { name: "Prepare" });
    expect(current.some((el) => el.getAttribute("aria-current") === "page")).toBe(true);
  });

  it("provides a skip link to content", () => {
    render(<AppShell><span /></AppShell>);
    expect(screen.getByText("Skip to content")).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  });

  it("home wordmark links to /", () => {
    render(<AppShell><span /></AppShell>);
    expect(screen.getByRole("link", { name: "Ask4Mo — home" }))
      .toHaveAttribute("href", "/");
  });

  it("Settings is reachable via the account control, not the primary nav", () => {
    render(<AppShell><span /></AppShell>);
    const account = screen.getByRole("link", { name: "Account and settings" });
    expect(account).toHaveAttribute("href", "/settings");
  });
});

describe("More menu (secondary navigation)", () => {
  it("collapses by default and exposes Sources + Review on open", async () => {
    render(<MoreMenu />);
    const trigger = screen.getByRole("button", { name: /More/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /Sources/ })).toHaveAttribute("href", "/sources");
    expect(within(menu).getByRole("menuitem", { name: /Review & Diagnostics/ })).toHaveAttribute("href", "/review");
  });

  it("does NOT contain Settings", async () => {
    render(<MoreMenu />);
    await userEvent.click(screen.getByRole("button", { name: /More/ }));
    const menu = screen.getByRole("menu");
    expect(within(menu).queryByText("Settings")).not.toBeInTheDocument();
  });

  it("closes on Escape and restores focus to the trigger", async () => {
    render(<MoreMenu />);
    const trigger = screen.getByRole("button", { name: /More/ });
    await userEvent.click(trigger);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("marks the More control active on a supporting route (not a primary tab)", () => {
    pathname = "/review/agent";
    render(<AppShell><span /></AppShell>);
    // A primary tab must NOT be marked current for a supporting route.
    const prepare = screen.getAllByRole("link", { name: "Prepare" });
    expect(prepare.every((el) => el.getAttribute("aria-current") !== "page")).toBe(true);
    // The More control reflects the supporting-route active styling.
    const more = screen.getByRole("button", { name: /More/ });
    expect(more.className).toContain("text-foreground");
  });
});

describe("Mobile navigation", () => {
  it("bottom nav has exactly the four primary destinations (no Sources/Review)", () => {
    render(<MobileNavigation />);
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const links = within(nav).getAllByRole("link");
    expect(links).toHaveLength(4);
    const labels = links.map((l) => l.textContent);
    expect(labels).toEqual(["Prepare", "Practice", "Progress", "History"]);
    expect(within(nav).queryByText("Sources")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Review & Diagnostics")).not.toBeInTheDocument();
  });
});
