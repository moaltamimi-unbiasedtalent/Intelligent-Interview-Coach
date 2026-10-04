import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiErrorFromBody, stateKeyForError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

// P10B-W10.11 Admin Configuration (durable pause) and Feature flags, plus the candidate pause error contract. APIs are mocked.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/configuration" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { user_id: 7, platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
const pauseGet = vi.fn(); const pauseSet = vi.fn(); const flagsGet = vi.fn(); const flagSet = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { pause: (...a: unknown[]) => pauseGet(...a), setPause: (...a: unknown[]) => pauseSet(...a), flags: (...a: unknown[]) => flagsGet(...a), setFlag: (...a: unknown[]) => flagSet(...a) } },
}));

import { ConfigurationView } from "@/components/admin/ConfigurationView";
import { FlagsView } from "@/components/admin/FlagsView";

const ITEM = (o: Record<string, unknown> = {}) => ({ capability: "agent", paused: false, source: "baseline", baseline_paused: false, revision: 0, paused_at: null, resumed_at: null, updated_at: null, reason: "", ...o });
const OVERVIEW = (items = [ITEM(), ITEM({ capability: "ocr" })]) => ({ environment: "staging", durable: true, items, protected_scope: ["agent", "ocr"], note: "Pausing a capability refuses NEW candidate activity." });
const FLAG = (o: Record<string, unknown> = {}) => ({ flag_id: "external_research", display_name: "External market research", description: "Allows external research.", category: "research", candidate_visible: true,
  baseline: true, baseline_source: "environment variable EXTERNAL_RESEARCH_ENABLED (default on)", override: null, state: "inherited", effective: true, revision: 0, updated_at: null,
  updated_by_user_id: null, reason: "", notes: "Disabling it turns research off.", consumers: [], ...o });
const FLAGS = (items = [FLAG(), FLAG({ flag_id: "company_web_research", display_name: "Company website research" })]) => ({ environment: "staging", items, not_mutable: { AGENT_COACH_ENABLED: "read-only environment capability" }, note: "Only the flags listed here exist." });

beforeEach(() => {
  mockPerms = ["platform.flags.read", "platform.flags.manage", "platform.config.manage"];
  pauseGet.mockResolvedValue(OVERVIEW()); pauseSet.mockResolvedValue(ITEM({ paused: true, revision: 1 }));
  flagsGet.mockResolvedValue(FLAGS()); flagSet.mockResolvedValue(FLAG({ state: "disabled_override", override: false, effective: false, revision: 1 }));
});
afterEach(() => vi.clearAllMocks());

describe("Admin Configuration (durable pause)", () => {
  it("shows the server-decided environment, running state and no settings editor", async () => {
    render(<ConfigurationView />);
    expect(await screen.findByRole("heading", { name: "Platform runtime: Running" })).toBeInTheDocument();
    expect(screen.getByText("staging")).toBeInTheDocument();
    expect(screen.getByText(/survives a restart/)).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /environment/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /key|value|json|env/i })).not.toBeInTheDocument();
    expect(screen.getByText(/no environment-variable, secret, database or JSON editor/)).toBeInTheDocument();
  });

  it("pausing needs a reason, sends the loaded revision and reports the outcome", async () => {
    render(<ConfigurationView />);
    await userEvent.click(await screen.findByRole("button", { name: "Pause Mo (agent) runs" }));
    const dlg = await screen.findByRole("alertdialog");
    expect(within(dlg).getByRole("button", { name: "Cancel" })).toHaveFocus();                        // safe default
    await userEvent.click(within(dlg).getByRole("button", { name: "Pause" }));
    expect(await within(dlg).findByText("A reason is required.")).toBeInTheDocument();
    expect(pauseSet).not.toHaveBeenCalled();
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "provider incident");
    await userEvent.click(within(dlg).getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(pauseSet).toHaveBeenCalledWith("agent", true, 0, "provider incident"));
    expect(await screen.findByText("Mo (agent) runs paused.")).toBeInTheDocument();
  });

  it("a paused platform is prominent with text, and Resume uses the current revision", async () => {
    pauseGet.mockResolvedValue(OVERVIEW([ITEM({ paused: true, source: "override", revision: 3, paused_at: "2026-10-04T10:00:00", reason: "incident" }), ITEM({ capability: "ocr" })]));
    render(<ConfigurationView />);
    expect(await screen.findByRole("heading", { name: "Platform runtime: Paused (restricted)" })).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();                                          // text, not colour only
    await userEvent.click(screen.getByRole("button", { name: "Resume Mo (agent) runs" }));
    const dlg = await screen.findByRole("alertdialog");
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "recovered");
    await userEvent.click(within(dlg).getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(pauseSet).toHaveBeenCalledWith("agent", false, 3, "recovered"));
  });

  it("a revision conflict is shown inside the dialog and nothing is retried", async () => {
    pauseSet.mockRejectedValue(new Error("This switch changed since you loaded it. Reload and review the current state before changing it."));
    render(<ConfigurationView />);
    await userEvent.click(await screen.findByRole("button", { name: "Pause Mo (agent) runs" }));
    const dlg = await screen.findByRole("alertdialog");
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "x");
    await userEvent.click(within(dlg).getByRole("button", { name: "Pause" }));
    expect(await within(dlg).findByText(/changed since you loaded it/)).toBeInTheDocument();
    expect(pauseSet).toHaveBeenCalledTimes(1);
  });

  it("a read-only role sees the state but no Pause/Resume control", async () => {
    mockPerms = ["platform.flags.read"];
    render(<ConfigurationView />);
    await screen.findByRole("heading", { name: "Platform runtime: Running" });
    expect(screen.queryByRole("button", { name: /^(Pause|Resume)/ })).not.toBeInTheDocument();
    expect(screen.getByText(/can view the pause state but cannot change it/)).toBeInTheDocument();
  });

  it("denies the view without the flags read permission", () => {
    mockPerms = ["platform.overview.read"];
    render(<ConfigurationView />);
    expect(screen.getByText(/does not include access/)).toBeInTheDocument();
  });
});

describe("Admin Feature flags", () => {
  it("lists only the registered flags with baseline, state, effective value and no create control", async () => {
    render(<FlagsView />);
    expect(await screen.findByText("External market research")).toBeInTheDocument();
    expect(screen.getByText("Company website research")).toBeInTheDocument();
    expect(screen.getAllByText("Inherited baseline").length).toBe(2);
    expect(screen.getAllByText(/environment variable EXTERNAL_RESEARCH_ENABLED/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /add|create|new flag/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();                                  // no generic key/value or JSON editor
    expect(screen.getByText(/AGENT_COACH_ENABLED/)).toBeInTheDocument();                           // a non-mutable setting is explained, not editable
  });

  it("disable override sends the loaded revision; reset is disabled when already inherited", async () => {
    render(<FlagsView />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Disable override for External market research" }))[0]);
    expect(screen.getAllByRole("button", { name: "Reset External market research to inherited baseline" })[0]).toBeDisabled();
    const dlg = await screen.findByRole("alertdialog");
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "cost");
    await userEvent.click(within(dlg).getByRole("button", { name: "Disable override" }));
    await waitFor(() => expect(flagSet).toHaveBeenCalledWith("external_research", false, 0, "cost"));
    expect(await screen.findByText(/disabled override/)).toBeInTheDocument();
  });

  it("an explicit override shows distinctly and can be reset to inherit (null)", async () => {
    flagsGet.mockResolvedValue(FLAGS([FLAG({ state: "disabled_override", override: false, effective: false, revision: 2 })]));
    render(<FlagsView />);
    expect(await screen.findByText("Disabled override")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reset External market research to inherited baseline" }));
    const dlg = await screen.findByRole("alertdialog");
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "back");
    await userEvent.click(within(dlg).getByRole("button", { name: "Reset to inherited baseline" }));
    await waitFor(() => expect(flagSet).toHaveBeenCalledWith("external_research", null, 2, "back"));
  });

  it("a flags-read-only role cannot change anything", async () => {
    mockPerms = ["platform.flags.read"];
    render(<FlagsView />);
    await screen.findByText("External market research");
    expect(screen.queryByRole("button", { name: /override|Reset/ })).not.toBeInTheDocument();
  });
});

describe("Candidate pause contract", () => {
  it("platform_paused is a stable code mapped to a localized message in all eight locales", () => {
    const err = apiErrorFromBody(503, { error: { code: "platform_paused", message: "anything", request_id: "r" } }, null);
    expect(err.kind).toBe("paused");
    expect(stateKeyForError(err.kind)).toBe("states.platformPaused");
    const seen = new Set<string>();
    for (const l of SUPPORTED_LOCALE_CODES) {
      const msg = translate(l, "states.platformPaused");
      expect(msg).not.toBe("states.platformPaused");
      expect(msg).not.toMatch(/operator|incident|reason|@/i);
      seen.add(msg);
    }
    expect(seen.size).toBe(8);
  });

  it("matching on English text is never needed: a 503 without the code stays a normal unavailable error", () => {
    expect(apiErrorFromBody(503, { error: { code: "http_error", message: "paused by the operator", request_id: "r" } }, null).kind).toBe("unavailable");
    expect(apiErrorFromBody(503, { error: { code: "platform_state_unavailable", message: "x", request_id: "r" } }, null).kind).toBe("unavailable");
  });

  it("the API client never auto-retries a PUT write", async () => {
    const { isRetryable } = await import("@/lib/api/retry");
    expect(isRetryable("PUT", new ApiError({ kind: "unavailable", status: 503, code: "x", message: "m" }))).toBe(false);
  });
});

describe("W10.11 sources", () => {
  it("the admin pages store nothing in the browser and expose no secrets or role names", () => {
    for (const f of ["components/admin/ConfigurationView.tsx", "components/admin/FlagsView.tsx"]) {
      const t = readFileSync(join(process.cwd(), f), "utf8");
      expect(t).not.toMatch(/localStorage|sessionStorage|indexedDB|platform_admin|operations_admin|DATABASE_URL|API_KEY/);
      expect(t).not.toContain("—");
    }
  });
});
