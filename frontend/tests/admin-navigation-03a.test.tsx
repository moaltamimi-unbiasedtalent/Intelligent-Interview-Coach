import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixtures/admin-role-permissions.json";

// 03A (REQ-OWN-08): grouped, permission-aware Admin navigation. Permissions come from the server (account.admin_permissions); hiding is UX, the API authorises.

type Account = { platform_role: string; admin_permissions?: string[] } | null;
let mockAccount: Account = null;
let mockPath = "/admin";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => mockPath }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a>,
}));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: mockAccount, status: "authenticated" }),
  useAuth: () => ({ account: mockAccount, status: "authenticated" }),
}));

import { AdminShell } from "@/components/admin/AdminShell";
import {
  ADMIN_DESTINATIONS, ADMIN_GROUPS, breadcrumbsFor, filterDestinations, groupedDestinations, visibleDestinations,
} from "@/lib/admin/capabilities";
import { INTERNAL_NAV } from "@/components/layout/nav-items";

const personas = Object.entries(fixture.personas) as [string, { permissions: string[]; nav: string[] }][];
const ALL = fixture.personas.platform_admin.permissions;

beforeEach(() => {
  mockAccount = { platform_role: "platform_admin", admin_permissions: ALL };
  mockPath = "/admin";
});
afterEach(() => vi.clearAllMocks());

const nav = () => screen.getByRole("navigation", { name: "Admin" });
const linkTexts = () => within(nav()).getAllByRole("link").map((a) => a.textContent);

describe("grouping contract", () => {
  it("places every destination in exactly one of the six approved sections", () => {
    expect(ADMIN_GROUPS.map((g) => g.label)).toEqual([
      "Command Center", "Customers and Workspaces", "Products and Commercial", "AI and Knowledge", "Insights and Operations", "Governance and Settings",
    ]);
    const placed = ADMIN_GROUPS.flatMap((g) => g.destinationIds);
    expect(new Set(placed).size).toBe(placed.length);                                           // no duplicates
    expect([...placed].sort()).toEqual(ADMIN_DESTINATIONS.map((d) => d.id).sort());             // none missing, none unknown
    expect(ADMIN_DESTINATIONS).toHaveLength(20);
  });

  it("uses the owner-reviewed placement", () => {
    const by = Object.fromEntries(ADMIN_GROUPS.map((g) => [g.id, g.destinationIds]));
    expect(by.customers).toEqual(["users", "workspaces", "support", "privacy"]);
    expect(by.commercial).toEqual(["plans", "billing"]);
    expect(by.ai).toEqual(["ai", "knowledge", "speech", "providers", "review"]);
    expect(by.insights).toEqual(["reports", "jobs", "integrations"]);
    expect(by.governance).toEqual(["security", "audit", "legal", "configuration", "flags"]);
  });

  it("Review and Diagnostics lives under /admin and keeps its permission gate", () => {
    const review = ADMIN_DESTINATIONS.find((d) => d.id === "review")!;
    expect(review.href).toBe("/admin/review");
    expect(review.anyOf).toEqual(["platform.ai.read", "platform.knowledge.read"]);
  });

  it("the global More menu has no Review entry (only Admin)", () => {
    expect(INTERNAL_NAV.map((i) => i.href)).toEqual(["/admin"]);
  });
});

describe("visibility per role fixture", () => {
  it.each(personas)("%s: grouped view shows exactly the permitted destinations and no empty group", (_name, p) => {
    const groups = groupedDestinations(p.permissions);
    const flat = groups.flatMap((g) => g.destinations.map((d) => d.href));
    expect([...flat].sort()).toEqual([...p.nav].sort());                                         // same set as the flat, fixture-verified list
    expect(visibleDestinations(p.permissions).map((d) => d.href)).toEqual(p.nav);
    for (const g of groups) expect(g.destinations.length).toBeGreaterThan(0);                    // a group with nothing visible is hidden
    expect(groups.some((g) => g.group.id === "other")).toBe(false);
  });

  it("a candidate or unknown role gets no groups", () => {
    expect(groupedDestinations([])).toEqual([]);
    expect(fixture.unknown_role_nav).toEqual([]);
  });

  it("rendered shell shows only permitted sections and links", () => {
    mockAccount = { platform_role: "x", admin_permissions: ["platform.overview.read", "platform.users.read"] };
    render(<AdminShell><p>body</p></AdminShell>);
    const buttons = within(nav()).getAllByRole("button").map((b) => b.textContent ?? "");
    expect(buttons.some((t) => t.includes("Command Center"))).toBe(true);
    expect(buttons.some((t) => t.includes("Customers and Workspaces"))).toBe(true);
    for (const hidden of ["Products and Commercial", "AI and Knowledge", "Insights and Operations", "Governance and Settings"]) {
      expect(buttons.some((t) => t.includes(hidden))).toBe(false);
    }
    expect(linkTexts()).toEqual(["Overview", "Users"]);
  });

  it("an AI-only account sees only the AI and Knowledge section, containing Review / Diagnostics", () => {
    mockAccount = { platform_role: "x", admin_permissions: ["platform.ai.read"] };
    render(<AdminShell><p>x</p></AdminShell>);
    expect(linkTexts()).toEqual(["AI and models", "Review / Diagnostics"]);
  });

  it("the server permission alone decides: an empty permission list renders no navigation", () => {
    mockAccount = { platform_role: "platform_admin", admin_permissions: [] };
    render(<AdminShell><p>secret</p></AdminShell>);
    expect(screen.queryByRole("navigation", { name: "Admin" })).toBeNull();
    expect(screen.queryByText("secret")).toBeNull();
  });
});

describe("disclosure and keyboard behaviour", () => {
  it("sections start open, collapse and re-open with aria-expanded", async () => {
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    const section = within(nav()).getByRole("button", { name: /Customers and Workspaces/ });
    expect(section).toHaveAttribute("aria-expanded", "true");
    const list = document.getElementById(section.getAttribute("aria-controls")!)!;
    expect(list).not.toHaveAttribute("hidden");
    await user.click(section);
    expect(section).toHaveAttribute("aria-expanded", "false");
    expect(list).toHaveAttribute("hidden");
    await user.click(section);
    expect(section).toHaveAttribute("aria-expanded", "true");
  });

  it("Enter and Space on a section button toggle it", async () => {
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    const section = within(nav()).getByRole("button", { name: /Products and Commercial/ });
    section.focus();
    await user.keyboard("{Enter}");
    expect(section).toHaveAttribute("aria-expanded", "false");
    await user.keyboard(" ");
    expect(section).toHaveAttribute("aria-expanded", "true");
  });

  it("highlights only the current destination and keeps its section open on navigation", () => {
    mockPath = "/admin/billing";
    render(<AdminShell><p>x</p></AdminShell>);
    const current = within(nav()).getAllByRole("link").filter((a) => a.getAttribute("aria-current") === "page");
    expect(current.map((a) => a.textContent)).toEqual(["Billing"]);
  });

  it("a detail page highlights its parent destination; /admin/review/rag highlights Review / Diagnostics, not Overview", () => {
    mockPath = "/admin/review/rag";
    render(<AdminShell><p>x</p></AdminShell>);
    const current = within(nav()).getAllByRole("link").filter((a) => a.getAttribute("aria-current") === "page");
    expect(current.map((a) => a.textContent)).toEqual(["Review / Diagnostics"]);
  });

  it("arrow keys, Home and End move between section buttons and links; ArrowUp from the first item returns to the filter", async () => {
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    const filter = within(nav()).getByRole("searchbox", { name: "Find a section" });
    filter.focus();
    await user.keyboard("{ArrowDown}");
    const first = within(nav()).getByRole("button", { name: /Command Center/ });
    expect(first).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(within(nav()).getByRole("link", { name: "Overview" })).toHaveFocus();
    await user.keyboard("{End}");
    expect(within(nav()).getByRole("link", { name: "Feature flags" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(first).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(filter).toHaveFocus();
  });

  it("arrow navigation skips links inside a collapsed section", async () => {
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    await user.click(within(nav()).getByRole("button", { name: /Customers and Workspaces/ }));
    within(nav()).getByRole("link", { name: "Overview" }).focus();
    await user.keyboard("{ArrowDown}");
    expect(within(nav()).getByRole("button", { name: /Customers and Workspaces/ })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(within(nav()).getByRole("button", { name: /Products and Commercial/ })).toHaveFocus();   // the hidden links (Users...) are skipped
  });

  it("every control has an accessible name and the navigation is a labelled landmark", () => {
    render(<AdminShell><p>x</p></AdminShell>);
    for (const el of [...within(nav()).getAllByRole("button"), ...within(nav()).getAllByRole("link"), within(nav()).getByRole("searchbox")]) {
      expect(el).toHaveAccessibleName();
    }
  });
});

describe("quick navigation filters visible items only", () => {
  it("narrows the list, announces the count and never reveals a destination the account may not see", async () => {
    mockAccount = { platform_role: "x", admin_permissions: ["platform.overview.read", "platform.users.read", "platform.ai.read"] };
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    const filter = within(nav()).getByRole("searchbox", { name: "Find a section" });
    await user.type(filter, "billing");
    expect(within(nav()).queryAllByRole("link")).toHaveLength(0);                                // Billing exists but is not permitted: no result
    expect(within(nav()).getByRole("status")).toHaveTextContent("No section matches");
    await user.clear(filter);
    await user.type(filter, "ai");
    expect(linkTexts()).toContain("AI and models");
    expect(within(nav()).getByRole("status")).toHaveTextContent(/found/);
  });

  it("matches the section name and opens collapsed sections while filtering; Escape clears", async () => {
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    await user.click(within(nav()).getByRole("button", { name: /Governance and Settings/ }));
    const filter = within(nav()).getByRole("searchbox", { name: "Find a section" });
    await user.type(filter, "governance");
    expect(linkTexts()).toEqual(["Security", "Audit", "Legal", "Configuration", "Feature flags"]);
    await user.keyboard("{Escape}");
    expect(filter).toHaveValue("");
  });

  it("filterDestinations is a pure filter over its input", () => {
    const visible = groupedDestinations(["platform.users.read"]);
    expect(filterDestinations(visible, "").flatMap((g) => g.destinations.map((d) => d.id))).toEqual(["users"]);
    expect(filterDestinations(visible, "audit")).toEqual([]);
    expect(filterDestinations(visible, "USERS").flatMap((g) => g.destinations.map((d) => d.id))).toEqual(["users"]);
  });

  it("Enter in the filter moves focus to the first result", async () => {
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    await user.type(within(nav()).getByRole("searchbox", { name: "Find a section" }), "audit{Enter}");
    expect(within(nav()).getByRole("link", { name: "Audit" })).toHaveFocus();
  });
});

describe("breadcrumbs", () => {
  it("names the section and the page", () => {
    mockPath = "/admin/billing";
    render(<AdminShell><p>x</p></AdminShell>);
    const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(crumbs).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Admin", "/Products and Commercial", "/Billing"]);
    expect(within(crumbs).getByRole("link", { name: "Admin" })).toHaveAttribute("href", "/admin");
    expect(crumbs.querySelector("[aria-current='page']")).toHaveTextContent("Billing");
  });

  it("is absent on the Command Center root", () => {
    render(<AdminShell><p>x</p></AdminShell>);
    expect(screen.queryByRole("navigation", { name: "Breadcrumb" })).toBeNull();
  });

  it("includes deeper segments and generic labels for identifiers", () => {
    const groups = groupedDestinations(ALL);
    expect(breadcrumbsFor("/admin/review/rag", groups).map((c) => c.label)).toEqual(["Admin", "AI and Knowledge", "Review / Diagnostics", "Rag"]);
    expect(breadcrumbsFor("/admin/users/42", groups).map((c) => c.label)).toEqual(["Admin", "Customers and Workspaces", "Users", "Details"]);
    expect(breadcrumbsFor("/admin/users/42", groups)[2].href).toBe("/admin/users");
    expect(breadcrumbsFor("/admin/support/0123456789abcdef0123456789abcdef", groups).at(-1)?.label).toBe("Details");
  });

  it("is empty for a path the account cannot see or that is not an Admin destination", () => {
    expect(breadcrumbsFor("/admin/billing", groupedDestinations(["platform.users.read"]))).toEqual([]);
    expect(breadcrumbsFor("/review/agent", groupedDestinations(ALL))).toEqual([]);
  });
});

describe("responsive drawer", () => {
  it("below lg the sidebar sits behind a menu button that names the current page; Escape closes and refocuses it", async () => {
    mockPath = "/admin/audit";
    const user = userEvent.setup();
    render(<AdminShell><p>x</p></AdminShell>);
    const toggle = within(nav()).getByRole("button", { name: "Admin menu: Audit" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById("admin-nav-list")!.className).toContain("hidden");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("admin-nav-list")!.className).not.toMatch(/(^|\s)hidden(\s|$)/);
    within(nav()).getByRole("link", { name: "Audit" }).focus();
    await user.keyboard("{Escape}");
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
