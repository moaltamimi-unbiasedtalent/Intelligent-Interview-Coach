import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// W12.4F: the Admin speech page and the derived capability-readiness panel. Server speech is NOT active; saving records a decision only.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/speech" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const speech = vi.fn();
const setSpeech = vi.fn();
const readiness = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { admin: { speech: (...a: unknown[]) => speech(...a), setSpeech: (...a: unknown[]) => setSpeech(...a), readiness: (...a: unknown[]) => readiness(...a) } } }));

import { SpeechView } from "@/components/admin/SpeechView";
import { CapabilityReadiness } from "@/components/admin/CapabilityReadiness";
import { ADMIN_DESTINATIONS } from "@/lib/admin/capabilities";
import { ApiError } from "@/lib/api/errors";

const READY = (o: Record<string, unknown> = {}) => ({ provider: "openai_whisper", configured: false, dependency_available: false, model_available: false, ready_for_offline_execution: false,
  validated_with_fixture: true, validated_with_genuine_model: "NOT_VERIFIED", live_authorized: false, operational: false, deployment: "none", blockers: ["disabled by configuration", "server speech is not authorized (code constant)"], note: "", ...o });
const CFG = (o: Record<string, unknown> = {}) => ({ stt_provider: "openai_whisper", tts_provider: "kyutai_pocket_tts", stt_enabled: false, tts_enabled: false, languages: ["en", "de", "fr", "es", "it", "pt", "nl"],
  browser_stt_allowed: true, browser_tts_allowed: true, stt_timeout_seconds: 30, tts_timeout_seconds: 20, revision: 0, persisted: false, ...o });
const LANG = (o: Record<string, unknown> = {}) => ({ product_authorized: true, stt_provider_supports: true, tts_provider_supports: true, tts_provider_unverified: false, admin_selected: true, effective_stt: true, effective_tts: true, ...o });
const OVERVIEW = (cfg = CFG()) => ({ environment: "development", config: cfg, stt: READY(), tts: READY({ provider: "kyutai_pocket_tts" }),
  language_matrix: { en: LANG(), nl: LANG({ tts_provider_supports: false, tts_provider_unverified: true, effective_tts: false }), ru: LANG({ product_authorized: false, effective_stt: false, effective_tts: false }) },
  provider_facts: {}, authorization: { server_speech_providers: false, hosted_whisper_api_transport: false, model_downloads: false, voice_cloning: false }, note: "Server-side speech is governed here but is NOT active." });

beforeEach(() => {
  mockPerms = ["platform.flags.read", "platform.config.manage"];
  speech.mockResolvedValue(OVERVIEW());
  setSpeech.mockResolvedValue(CFG({ revision: 1 }));
});
afterEach(() => vi.clearAllMocks());

describe("Admin speech page", () => {
  it("states plainly that server speech is not active and never shows a provider as operational", async () => {
    render(<SpeechView />);
    expect(await screen.findByText(/Server speech: not active/)).toBeInTheDocument();
    expect(screen.getAllByText("Not operational")).toHaveLength(2);
    expect(screen.getAllByText("NOT_VERIFIED").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Not authorized").length).toBeGreaterThanOrEqual(4);
    expect(screen.getByText("Unverified")).toBeInTheDocument();            // Dutch TTS
  });

  it("saves only the changed field with the expected revision and a required reason, and says nothing was started", async () => {
    const user = userEvent.setup();
    render(<SpeechView />);
    await screen.findByText(/Server speech: not active/);
    await user.click(screen.getByLabelText("Allow browser speech output (fallback)"));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    const confirm = await screen.findByRole("button", { name: "Save" });
    await user.click(confirm);
    expect(await screen.findByText("A reason is required.")).toBeInTheDocument();
    expect(setSpeech).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText(/Reason/), "disable browser output while reviewing");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(setSpeech).toHaveBeenCalledWith({ browser_tts_allowed: false }, 0, "disable browser output while reviewing"));
    expect(await screen.findByText(/No provider was started or contacted/)).toBeInTheDocument();
  });

  it("shows a stale-revision refusal inside the dialog without losing the draft", async () => {
    setSpeech.mockRejectedValue(new ApiError({ kind: "conflict", status: 409, code: "conflict", message: "The speech settings changed since you loaded them." }));
    const user = userEvent.setup();
    render(<SpeechView />);
    await screen.findByText(/Server speech: not active/);
    await user.click(screen.getByLabelText("Server speech to text selected"));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await user.type(await screen.findByLabelText(/Reason/), "select for review");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/changed since you loaded them/)).toBeInTheDocument();
  });

  it("offers no editing to a role without configuration permission and exposes no free-form control", async () => {
    mockPerms = ["platform.flags.read"];
    render(<SpeechView />);
    await screen.findByText(/Server speech: not active/);
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    expect(screen.getByText(/cannot change it/)).toBeInTheDocument();
    expect(screen.getByLabelText("Server speech to text selected")).toBeDisabled();
    expect(screen.queryByRole("textbox")).toBeNull();                     // only checkboxes and numbers: no path, command, endpoint or secret field
    expect(screen.queryByLabelText("ru")).toBeNull();                     // Russian can never be selected
  });

  it("is a registered destination gated by the flags read permission", () => {
    const d = ADMIN_DESTINATIONS.find((x) => x.id === "speech");
    expect(d?.href).toBe("/admin/speech");
    expect(d?.anyOf).toEqual(["platform.flags.read"]);
  });
});

describe("Capability readiness panel", () => {
  it("renders derived statuses with qualifiers and the no-production-claim boundary", async () => {
    readiness.mockResolvedValue({ summary: {}, vocabulary: { statuses: [], qualifiers: [] }, boundary: "This is not a statement that the platform is production ready.",
      capabilities: [{ id: "billing", label: "Billing", admin_path: "/admin/billing", status: "MOCK", qualifiers: ["OFFLINE_VALIDATED", "LIVE_UNVERIFIED"], ownership: "Commercial activation workflow", basis: "runtime",
        evidence: "live billing disabled", limitations: ["Simulated billing"] }] });
    render(<CapabilityReadiness />);
    expect(await screen.findByText("Mock")).toBeInTheDocument();
    expect(screen.getByText(/Offline validated · Live unverified/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Billing" })).toHaveAttribute("href", "/admin/billing");
    expect(screen.getByText(/not a statement that the platform is production ready/)).toBeInTheDocument();
  });

  it("shows an accessible unavailable state for a malformed or empty response instead of crashing or inventing statuses", async () => {
    for (const bad of [{}, { capabilities: [] }, { capabilities: null }]) {
      readiness.mockResolvedValue(bad);
      const { unmount } = render(<CapabilityReadiness />);
      expect(await screen.findByRole("status")).toHaveTextContent(/unavailable right now/);
      expect(screen.queryByRole("table")).toBeNull();                              // no fabricated readiness rows
      unmount();
    }
  });

  it("W12.5 correction: structurally malformed NON-EMPTY rows give the unavailable state, never a crash or an invented status", async () => {
    const good = { id: "billing", label: "Billing", admin_path: "/admin/billing", status: "MOCK", qualifiers: ["OFFLINE_VALIDATED"], ownership: "Owner", basis: "runtime", evidence: "e", limitations: [] };
    const bad: unknown[] = [
      [{ id: "x" }],                                              // required fields missing
      [{ ...good, qualifiers: null }],                            // qualifiers not an array (used to throw on .length / .map)
      [{ ...good, limitations: "none" }],                         // limitations not an array
      [{ ...good, status: "SHINY_NEW_STATUS" }],                  // unknown status is not shown as if it were known
      [{ ...good, status: "toString" }],                          // not a prototype key either
      [{ ...good, evidence: 5 }],
      [{ ...good, label: "" }],
      [null],
      [good, { ...good, id: "second", qualifiers: undefined }],   // one bad row among good rows invalidates the response
      ["not an object"],
    ];
    for (const rows of bad) {
      readiness.mockResolvedValue({ summary: {}, vocabulary: { statuses: [], qualifiers: [] }, boundary: "b", capabilities: rows });
      const { unmount } = render(<CapabilityReadiness />);
      expect(await screen.findByRole("status")).toHaveTextContent(/unavailable right now/);
      expect(screen.queryByRole("table")).toBeNull();
      expect(screen.queryByText("Billing")).toBeNull();           // no row text leaks through
      unmount();
    }
  });

  it("W12.5 correction: a fully valid response still renders every row", async () => {
    const good = (id: string, status: string) => ({ id, label: `Cap ${id}`, admin_path: null, status, qualifiers: [], ownership: "Owner", basis: "code", evidence: "e", limitations: ["l"] });
    readiness.mockResolvedValue({ summary: {}, vocabulary: { statuses: [], qualifiers: [] }, boundary: "b", capabilities: [good("a", "OPERATIONAL"), good("b", "READ_ONLY")] });
    render(<CapabilityReadiness />);
    expect(await screen.findByText("Cap a")).toBeInTheDocument();
    expect(screen.getByText("Cap b")).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
  });

  it("shows the unavailable state when the endpoint fails (never a fabricated healthy state)", async () => {
    readiness.mockRejectedValue(new Error("down"));
    render(<CapabilityReadiness />);
    expect(await screen.findByRole("status")).toHaveTextContent(/unavailable right now/);
    expect(screen.queryByRole("table")).toBeNull();
  });
});
