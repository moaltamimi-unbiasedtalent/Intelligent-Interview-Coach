import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.7 Admin AI and model administration UI. APIs are mocked: no model, no provider and no network exists here.

let mockPerms: string[] = [];
let mockUser = { user_id: 7, email: "me@example.com" };
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/ai" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { ...mockUser, platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const f = { ai: vi.fn(), cat: vi.fn(), code: vi.fn(), envs: vi.fn(), hist: vi.fn(), apprs: vi.fn(), cfgs: vi.fn(), cfg: vi.fn(), create: vi.fn(), update: vi.fn(), validate: vi.fn(),
  evaluate: vi.fn(), reqAppr: vi.fn(), decide: vi.fn(), activate: vi.fn(), rollback: vi.fn(), retire: vi.fn() };
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    ai: (...a: unknown[]) => f.ai(...a), aiCatalogue: (...a: unknown[]) => f.cat(...a), aiCodeDefined: (...a: unknown[]) => f.code(...a), aiEnvironments: (...a: unknown[]) => f.envs(...a),
    aiHistory: (...a: unknown[]) => f.hist(...a), aiApprovals: (...a: unknown[]) => f.apprs(...a), aiConfigs: (...a: unknown[]) => f.cfgs(...a), aiConfig: (...a: unknown[]) => f.cfg(...a),
    aiCreate: (...a: unknown[]) => f.create(...a), aiUpdate: (...a: unknown[]) => f.update(...a), aiValidate: (...a: unknown[]) => f.validate(...a), aiEvaluate: (...a: unknown[]) => f.evaluate(...a),
    aiRequestApproval: (...a: unknown[]) => f.reqAppr(...a), aiDecide: (...a: unknown[]) => f.decide(...a), aiActivate: (...a: unknown[]) => f.activate(...a),
    aiRollback: (...a: unknown[]) => f.rollback(...a), aiRetire: (...a: unknown[]) => f.retire(...a),
  } },
}));

import { AIConfigDetailView } from "@/components/admin/AIConfigDetailView";
import { AIView } from "@/components/admin/AIView";

const RES = { catalogue_id: "terra", provider_slug: "x/terra", source: "code_default" };
const RUNTIME = (o: Record<string, unknown> = {}) => ({ environment: "staging", mode: "code_defaults", active_version: null, content_hash: null, fallback_reason: null,
  profiles: { fast: { ...RES, catalogue_id: "luna" }, balanced: RES, advanced: { ...RES, catalogue_id: "sol" } }, operations: [], realtime: { capability: "realtime", chat_slug: null, governed: false }, note: "n", ...o });
const SUMMARY = (o: Record<string, unknown> = {}) => ({ public_id: "c".repeat(32), version: 1, name: "Lower retries", notes: "", state: "draft", content_hash: "a".repeat(64), catalogue_version: "v",
  created_by_email: "author@example.com", created_by_user_id: 9, created_at: null, validated_at: null, retired_at: null, active_in: [], ...o });
const DETAIL = (o: Record<string, unknown> = {}) => ({ ...SUMMARY(), settings: { profiles: { fast: "luna", balanced: "terra", advanced: "sol" }, operations: { orchestration: { max_output_tokens: 1536, timeout_s: 60, max_retries: 2 } } },
  validation: [], validation_passed: false, changed_from_baseline: [], evaluations: [], approvals: [], activations: [], latest_evaluation_passed: false, ...o });
const page = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 50 });
const CAT = { version: "2026-10-04.1", note: "Defined in code.", items: [
  { id: "luna", display_name: "Luna (Fast tier)", tier: "fast", allowed_profiles: ["fast", "balanced"], provider_slug: "p/luna", supports_tools: true, supports_structured_output: true, supports_temperature: false, cost_class: 1, note: "" },
  { id: "terra", display_name: "Terra (Balanced tier)", tier: "balanced", allowed_profiles: ["fast", "balanced", "advanced"], provider_slug: "p/terra", supports_tools: true, supports_structured_output: true, supports_temperature: false, cost_class: 2, note: "" }] };

beforeEach(() => {
  mockPerms = ["platform.ai.read", "platform.ai.manage", "platform.ai.activate"];
  mockUser = { user_id: 7, email: "me@example.com" };
  f.ai.mockResolvedValue({ stats: { versions: 1, by_state: {}, pending_approvals: 0, active: { staging: false, production: false } }, runtime: RUNTIME(), catalogue_version: "v" });
  f.cat.mockResolvedValue(CAT);
  f.code.mockResolvedValue({ operations: [
    { operation: "orchestration", capability: "tool_calling", min_capability: "balanced", fallback_floor: "balanced", structured_output: false, requires_tools: true, tunable: true, deterministic: false, realtime: false, code_values: {} },
    { operation: "specialist_evidence_analysis", capability: "none", min_capability: "fast", fallback_floor: "fast", structured_output: false, requires_tools: false, tunable: false, deterministic: true, realtime: false, code_values: {} },
    { operation: "realtime_voice", capability: "realtime", min_capability: "balanced", fallback_floor: "balanced", structured_output: false, requires_tools: false, tunable: false, deterministic: false, realtime: true, code_values: {} }], tunable_fields: {}, note: "Code-defined." });
  f.envs.mockResolvedValue({ note: "n", items: [{ environment: "staging", mode: "code_defaults", active: null, version: null, profiles: RUNTIME().profiles }, { environment: "production", mode: "code_defaults", active: null, version: null, profiles: RUNTIME().profiles }] });
  f.hist.mockResolvedValue(page([])); f.apprs.mockResolvedValue(page([])); f.cfgs.mockResolvedValue(page([SUMMARY()])); f.cfg.mockResolvedValue(DETAIL());
  f.create.mockResolvedValue(DETAIL()); f.update.mockResolvedValue(DETAIL()); f.validate.mockResolvedValue(DETAIL({ state: "validated" })); f.evaluate.mockResolvedValue({});
  f.reqAppr.mockResolvedValue({}); f.decide.mockResolvedValue({}); f.activate.mockResolvedValue({}); f.rollback.mockResolvedValue({}); f.retire.mockResolvedValue({});
});
afterEach(() => vi.clearAllMocks());

describe("Admin AI overview", () => {
  it("states the boundary, shows code defaults and has no provider-name input", async () => {
    render(<AIView />);
    expect(await screen.findByRole("heading", { name: "Governed configuration, no live model calls" })).toBeInTheDocument();
    expect((await screen.findAllByText("Code defaults")).length).toBeGreaterThan(0);
    expect(screen.getByText(/do not measure live answer quality/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/model name|provider|slug/i)).not.toBeInTheDocument();
    expect(screen.queryAllByRole("textbox").map((e) => e.getAttribute("aria-label") ?? e.id)).not.toContain("provider");
  });

  it("lists deterministic and realtime operations as not configurable", async () => {
    render(<AIView />);
    expect(await screen.findByText(/No \(deterministic, no model\)/)).toBeInTheDocument();
    expect(screen.getByText(/No \(realtime voice\)/)).toBeInTheDocument();
    expect(screen.getAllByText("Numbers only").length).toBe(1);
  });

  it("shows a refusal when an active configuration was rejected by the resolver", async () => {
    f.ai.mockResolvedValue({ stats: { versions: 1, by_state: {}, pending_approvals: 0, active: { staging: true, production: false } }, runtime: RUNTIME({ fallback_reason: "hash_mismatch" }), catalogue_version: "v" });
    render(<AIView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/refused and code defaults are in use \(reason: hash mismatch\)/);
  });

  it("a read-only role sees no create or rollback controls", async () => {
    mockPerms = ["platform.ai.read"];
    f.envs.mockResolvedValue({ note: "n", items: [{ environment: "staging", mode: "governed", active: null, version: SUMMARY({ state: "approved" }), profiles: RUNTIME().profiles }] });
    render(<AIView />);
    await screen.findByText("Configuration versions");
    expect(screen.queryByRole("button", { name: "Create draft" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Roll back|Revert/ })).not.toBeInTheDocument();
  });

  it("creating a draft sends only a name, notes and an optional base (no slug)", async () => {
    render(<AIView />);
    await userEvent.type(await screen.findByLabelText("Name"), "My draft");
    await userEvent.click(screen.getByRole("button", { name: "Create draft" }));
    await waitFor(() => expect(f.create).toHaveBeenCalledWith("My draft", "", null, null));
    expect(await screen.findByText(/Draft version 1 created/)).toBeInTheDocument();
  });

  it("denies the whole view without the AI read permission", () => {
    mockPerms = ["platform.overview.read"];
    render(<AIView />);
    expect(screen.getByText(/does not include access/)).toBeInTheDocument();
  });

  it("rollback requires a reason and revert is explicit", async () => {
    f.envs.mockResolvedValue({ note: "n", items: [{ environment: "staging", mode: "governed", active: { public_id: "f", environment: "staging", kind: "activate", version_ref: "c".repeat(32), version: 1, content_hash: null, activated_by_email: null, activated_at: null, deactivated_at: null, reason: "", open: true },
      version: SUMMARY({ state: "approved", active_in: ["staging"] }), profiles: RUNTIME().profiles }] });
    render(<AIView />);
    await userEvent.click(await screen.findByRole("button", { name: "Revert staging to code defaults" }));
    const dlg = await screen.findByRole("alertdialog");
    await userEvent.click(within(dlg).getByRole("button", { name: "Revert to code defaults" }));
    expect(await within(dlg).findByText("A reason is required.")).toBeInTheDocument();
    expect(f.rollback).not.toHaveBeenCalled();
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "back");
    await userEvent.click(within(dlg).getByRole("button", { name: "Revert to code defaults" }));
    await waitFor(() => expect(f.rollback).toHaveBeenCalledWith("staging", true, "back"));
  });
});

describe("Admin AI configuration detail", () => {
  it("a draft is editable with catalogue ids only and saves a bounded config", async () => {
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByRole("heading", { name: "Edit draft" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/slug|provider/i)).not.toBeInTheDocument();
    const retries = await screen.findByLabelText("orchestration Max retries");
    await userEvent.clear(retries);
    await userEvent.type(retries, "1");
    await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(f.update).toHaveBeenCalled());
    const body = f.update.mock.calls[0][1];
    expect(body.settings.profiles).toEqual({ fast: "luna", balanced: "terra", advanced: "sol" });
    expect(body.settings.operations.orchestration.max_retries).toBe(1);
  });

  it("a frozen configuration shows settings read-only", async () => {
    f.cfg.mockResolvedValue(DETAIL({ state: "validated" }));
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByRole("heading", { name: "Settings (frozen)" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument();
  });

  it("the requester or author cannot approve; a different administrator can", async () => {
    const approval = { public_id: "e".repeat(32), version_ref: "c".repeat(32), content_hash: "a".repeat(64), status: "pending", requested_by_email: "me@example.com", requested_at: null, decided_by_email: null, decided_at: null, reason: "r" };
    f.cfg.mockResolvedValue(DETAIL({ state: "evaluated", latest_evaluation_passed: true, approvals: [approval] }));
    const { unmount } = render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByText(/must decide this request/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    unmount();
    mockUser = { user_id: 8, email: "second@example.com" };
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dlg = await screen.findByRole("alertdialog");
    await userEvent.type(within(dlg).getByLabelText(/Reason/), "ok");
    await userEvent.click(within(dlg).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(f.decide).toHaveBeenCalledWith("e".repeat(32), true, "ok"));
  });

  it("author without a second person never gets an approve control even with activation permission", async () => {
    mockUser = { user_id: 9, email: "author@example.com" };
    const approval = { public_id: "e".repeat(32), version_ref: "c".repeat(32), content_hash: "a".repeat(64), status: "pending", requested_by_email: "x@example.com", requested_at: null, decided_by_email: null, decided_at: null, reason: "r" };
    f.cfg.mockResolvedValue(DETAIL({ state: "evaluated", latest_evaluation_passed: true, approvals: [approval] }));
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByText(/must decide this request/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("activation: only approved configs; production is disabled until staging has run", async () => {
    f.cfg.mockResolvedValue(DETAIL({ state: "approved" }));
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByRole("button", { name: "Activate in staging" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Activate in production" })).toBeDisabled();
    expect(screen.getByText(/Production needs a prior staging activation/)).toBeInTheDocument();
  });

  it("an unapproved configuration offers no activation", async () => {
    f.cfg.mockResolvedValue(DETAIL({ state: "evaluated", latest_evaluation_passed: true }));
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByText(/Only an approved configuration can be activated/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Activate in/ })).not.toBeInTheDocument();
  });

  it("evaluation shows hash binding, evaluator version, live calls and failed checks", async () => {
    f.cfg.mockResolvedValue(DETAIL({ state: "evaluation_failed", evaluations: [{ public_id: "d".repeat(32), content_hash: "b".repeat(64), evaluator_version: "ai-eval-1", status: "failed",
      checks: [{ code: "x", label: "A check", passed: false, detail: "It broke." }], summary: {}, live_calls: 0, failure_category: null, created_at: null, finished_at: null }] }));
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    expect(await screen.findByText(/does not match this content/)).toBeInTheDocument();
    expect(screen.getByText(/live calls: 0/)).toBeInTheDocument();
    expect(screen.getByText(/A check: It broke\./)).toBeInTheDocument();
    expect(screen.getByText(/not a measure of live answer quality/)).toBeInTheDocument();
  });

  it("a read-only role sees no lifecycle buttons", async () => {
    mockPerms = ["platform.ai.read"];
    f.cfg.mockResolvedValue(DETAIL({ state: "validated" }));
    render(<AIConfigDetailView id={"c".repeat(32)} />);
    await screen.findByRole("heading", { name: "Settings (frozen)" });
    for (const n of ["Validate", "Evaluate", "Submit for approval", "Retire", "Activate in staging"]) expect(screen.queryByRole("button", { name: n })).not.toBeInTheDocument();
  });
});

describe("AI admin sources", () => {
  const walk = (d: string): string[] => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
  it("no AI admin source stores to the browser or names a provider endpoint", () => {
    const files = [...walk(join(process.cwd(), "app/admin/ai")), join(process.cwd(), "components/admin/AIView.tsx"), join(process.cwd(), "components/admin/AIConfigDetailView.tsx")];
    for (const p of files) {
      const t = readFileSync(p, "utf8");
      expect(t).not.toMatch(/localStorage|sessionStorage|indexedDB|openrouter\.ai|api\.openai/);
      expect(t).not.toContain("—");
    }
  });
});
