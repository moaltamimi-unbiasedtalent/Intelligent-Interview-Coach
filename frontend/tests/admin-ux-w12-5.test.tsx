import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// W12.5 Admin UX corrections: Review inside the Admin shell (F-01), responsive Integrations (F-04), keyboard-operable scroll regions, humanized tables (F-07),
// audit cross-navigation (F-06), Providers/Integrations cross-links (F-17). APIs are mocked; no provider is contacted.

let mockPerms: string[] = [];
let mockPath = "/admin/review";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => mockPath }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const integrations = vi.fn(); const providers = vi.fn(); const audit = vi.fn(); const auditPage = vi.fn(); const events = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { integrations: (...a: unknown[]) => integrations(...a), providers: (...a: unknown[]) => providers(...a), audit: (...a: unknown[]) => audit(...a),
    auditPage: (...a: unknown[]) => auditPage(...a), securityEvents: (...a: unknown[]) => events(...a) } },
}));

import ReviewLayout from "@/app/review/layout";
import { IntegrationsView } from "@/components/admin/IntegrationsView";
import { ProvidersView } from "@/components/admin/ProvidersView";
import { AuditView } from "@/components/admin/AuditView";
import { SecurityView } from "@/components/admin/SecurityView";
import { ActiveFormPanel, ScrollRegion, Table, formatCell, humanizeHeader, useRestoreFocus } from "@/components/admin/ui";

const ITEM = (code: string, o: Record<string, unknown> = {}) => ({ code, name: `Name ${code}`, category: "ai_model", category_label: "AI / model", adapter: "a", description: "d", classification: "runtime_active",
  configuration_status: "configured", slots: [{ slot: "api_key", source_kind: "environment" }], settings: [], runtime: {}, store: {}, health: { status: "not_tested", last_tested_at: null }, test: {}, validation_note: "", ...o });

beforeEach(() => {
  mockPerms = ["platform.overview.read", "platform.ai.read", "platform.knowledge.read", "platform.integrations.read", "platform.audit.read", "platform.security.read"];
  mockPath = "/admin/review";
  integrations.mockResolvedValue({ items: [ITEM("openrouter"), ITEM("clamav", { slots: [], classification: "supported_unconfigured", health: { status: "healthy", last_tested_at: "2026-10-13T09:00:12.123456" } })] });
  providers.mockResolvedValue({ providers: [], speech: {}, ocr: { engine: "x", available: false, pdf_ocr_available: false, live_quality: "UNVALIDATED" }, note: "n" });
  audit.mockResolvedValue({ events: [{ created_at: "2026-10-13T09:00:12.123456", event_type: "admin.x", result: "success", actor_user_id: 1, target_type: "user", target_id: "2", request_id: "r", context: null }] });
  auditPage.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 });
  events.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 });
  window.location.hash = "";
});
afterEach(() => vi.clearAllMocks());

describe("F-01 Review and Diagnostics inside the Admin shell", () => {
  it("an administrator sees the Admin navigation around Review with Review / Diagnostics as the current page", () => {
    render(<ReviewLayout><p>review body</p></ReviewLayout>);
    const nav = screen.getByRole("navigation", { name: "Admin" });
    const current = within(nav).getAllByRole("link").filter((a) => a.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Review / Diagnostics");
    expect(within(nav).getByRole("link", { name: /Overview/ })).toHaveAttribute("href", "/admin");     // a way back to every Admin destination
    expect(screen.getByText("review body")).toBeInTheDocument();
  });

  it("a candidate (no Admin permission) gets the plain page: no Admin navigation is added to the owner-scoped Agent Inspector", () => {
    mockPerms = [];
    mockPath = "/review/agent";
    render(<ReviewLayout><p>inspector</p></ReviewLayout>);
    expect(screen.queryByRole("navigation", { name: "Admin" })).toBeNull();
    expect(screen.getByText("inspector")).toBeInTheDocument();
  });

  it("the navigation never lists a destination the account lacks permission for", () => {
    mockPerms = ["platform.ai.read"];
    render(<ReviewLayout><p>x</p></ReviewLayout>);
    const nav = screen.getByRole("navigation", { name: "Admin" });
    expect(within(nav).queryByRole("link", { name: /Billing/ })).toBeNull();
    expect(within(nav).queryByRole("link", { name: /Speech/ })).toBeNull();
  });
});

describe("F-04 Integrations responsive layout", () => {
  it("keeps every column and exposes a keyboard-scrollable labelled region", async () => {
    render(<IntegrationsView />);
    const region = await screen.findByRole("region", { name: /Integrations \(scrollable table\)/ });
    expect(region).toHaveAttribute("tabindex", "0");
    const headers = within(region).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["Integration", "Category", "Status", "Credentials", "Source", "Health", "Last tested"]);
    expect(within(region).getAllByRole("row")).toHaveLength(3);                                    // header + 2 integrations
    expect(within(region).getAllByRole("cell")[0]).toHaveAttribute("data-label", "Category");      // card labels for narrow screens
  });

  it("formats the last-tested time without microseconds and cross-links to Provider status", async () => {
    render(<IntegrationsView />);
    expect(await screen.findByText("2026-10-13 09:00:12 UTC")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Provider status" })).toHaveAttribute("href", "/admin/providers");
  });
});

describe("F-17 Providers and Integrations stay separate and cross-linked", () => {
  it("Provider status points to Integrations for health and credentials", async () => {
    render(<ProvidersView />);
    expect(await screen.findByRole("link", { name: "Integrations" })).toHaveAttribute("href", "/admin/integrations");
    expect(screen.getByText(/does not show health/)).toBeInTheDocument();
  });
});

describe("F-06 audit navigation", () => {
  it("the short audit list names the primary audit view and links to it", async () => {
    render(<AuditView />);
    const link = await screen.findByRole("link", { name: "Security, Audit" });
    expect(link).toHaveAttribute("href", "/admin/security#audit");
    expect(screen.getByText("2026-10-13 09:00:12 UTC")).toBeInTheDocument();                       // F-07: readable timestamp
    expect(screen.getByRole("columnheader", { name: "Event type" })).toBeInTheDocument();           // F-07: humanized header
  });

  it("/admin/security#audit opens the Audit tab and identifies it as the primary audit view", async () => {
    window.location.hash = "#audit";
    render(<SecurityView />);
    expect(await screen.findByText(/This is the primary audit view/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Audit" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("shared table and form primitives", () => {
  it("humanizes headers and timestamps for display only", () => {
    expect(humanizeHeader("created_at")).toBe("Created at");
    expect(formatCell("2026-10-13T09:00:12.987654")).toBe("2026-10-13 09:00:12 UTC");
    expect(formatCell("2026-10-13T09:00:12Z")).toBe("2026-10-13 09:00:12 UTC");
    expect(formatCell(null)).toBe("-");
    expect(formatCell("req-abc-123")).toBe("req-abc-123");
  });

  it("Table is a labelled, focusable scroll region", () => {
    render(<Table caption="Things" cols={["created_at"]} rows={[{ created_at: "x" }]} />);
    expect(screen.getByRole("region", { name: "Things (scrollable table)" })).toHaveAttribute("tabindex", "0");
  });

  it("ScrollRegion is keyboard reachable", async () => {
    render(<ScrollRegion label="Wide"><p>x</p></ScrollRegion>);
    await userEvent.tab();
    expect(screen.getByRole("region", { name: "Wide" })).toHaveFocus();
  });

  it("ActiveFormPanel focuses its first field, announces itself and closes on Escape; useRestoreFocus returns focus", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      const r = useRestoreFocus();
      return (
        <div>
          <button type="button" onClick={(e) => { r.capture(e.currentTarget); setOpen(true); }}>Open it</button>
          {open ? <ActiveFormPanel title="Edit thing" onClose={() => { setOpen(false); r.restore(); }}><input aria-label="field" /></ActiveFormPanel> : null}
        </div>
      );
    }
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open it" });
    await user.click(opener);
    expect(screen.getByLabelText("field")).toHaveFocus();
    expect(screen.getByRole("region", { name: "Edit thing" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Form opened: Edit thing");
    await user.keyboard("{Escape}");
    expect(screen.queryByLabelText("field")).toBeNull();
    await waitFor(() => expect(opener).toHaveFocus());
  });
});
