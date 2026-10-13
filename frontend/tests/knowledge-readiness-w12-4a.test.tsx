import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// W12.4A: Knowledge readiness, active inventory and retrieval test on /admin/knowledge. The API is mocked; the point is truthful presentation.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/knowledge" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const readiness = vi.fn();
const active = vi.fn();
const test = vi.fn();
const sources = vi.fn();
const meta = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: {
    knowledgeReadiness: (...a: unknown[]) => readiness(...a), knowledgeActive: (...a: unknown[]) => active(...a),
    testKnowledgeRetrieval: (...a: unknown[]) => test(...a), knowledgeSources: (...a: unknown[]) => sources(...a),
    knowledgeMeta: (...a: unknown[]) => meta(...a),
  } },
}));

import { KnowledgeView } from "@/components/admin/KnowledgeView";

const READ = ["platform.knowledge.read"];
const R = (over: Record<string, unknown> = {}) => ({
  status: "ready", message: "Governed knowledge is active, indexed and present in the store candidate retrieval reads.",
  candidate_retrieval_ready: true, governed_retrieval_ready: true, source_count: 1, active_source_count: 1, active_version_count: 1,
  indexed_active_version_count: 1, pending_job_count: 0, failed_job_count: 0, awaiting_review_count: 0, failed_version_count: 0,
  worker: { status: "available", seen_recently: 1, last_seen_at: "2026-10-13T10:00:00", stale_after_seconds: 60 },
  collection_status: "ok", collection: "governed_knowledge", store: { kind: "persistent", chunk_count: 4, location: "default" },
  embedding_provider_status: "available", embedder_state: { status: "available", provider: "local", embedder: "LocalHashEmbedder", note: "offline local embedder" },
  curated_corpus: { status: "available", chunk_count: 100, store_kind: "persistent" },
  last_indexed_at: "2026-10-13T09:00:00", last_failure_category: null, last_failure_stage: null, ...over,
});
const META = { languages: ["en"], authority_levels: [{ level: 1, meaning: "Level 1" }], licence_classes: [{ code: "unclear", label: "Unclear", activatable: false }],
  states: ["active"], rejection_reasons: [], upload: { max_bytes: 5242880, extensions: ["pdf"], preview_chars: 4000 } };
const EMPTY = { items: [], total: 0, page: 1, page_size: 25 };

beforeEach(() => {
  mockPerms = READ;
  readiness.mockReset().mockResolvedValue(R());
  active.mockReset().mockResolvedValue({ items: [], total: 0 });
  test.mockReset();
  meta.mockReset().mockResolvedValue(META);
  sources.mockReset().mockResolvedValue(EMPTY);
});

describe("Knowledge readiness (W12.4A)", () => {
  it("shows READY with the supporting facts, never a bare green claim", async () => {
    render(<KnowledgeView />);
    const box = await screen.findByTestId("knowledge-readiness");
    expect(within(box).getByText("Ready")).toBeTruthy();
    expect(screen.getByTestId("candidate-ready").textContent).toMatch(/Candidate retrieval ready:\s*Yes/);
    expect(screen.getByTestId("worker-state").textContent).toMatch(/Worker reporting/);
    expect(screen.getByTestId("store-state").textContent).toMatch(/governed_knowledge \(Present\)/);
    expect(screen.getByTestId("embedding-state").textContent).toMatch(/Offline local embedder: available/);
  });

  it("explains NO_ACTIVE_SOURCES as a normal state, not an error", async () => {
    readiness.mockResolvedValue(R({ status: "no_active_sources", message: "No governed knowledge source is active. Register, review, approve, index and activate a source.", candidate_retrieval_ready: false, governed_retrieval_ready: false, active_source_count: 0, indexed_active_version_count: 0 }));
    render(<KnowledgeView />);
    expect(await screen.findByText("No active sources")).toBeTruthy();
    expect(screen.getByTestId("candidate-ready").textContent).toMatch(/No/);
    const empty = await screen.findByTestId("knowledge-empty");
    expect(empty.textContent).toMatch(/No governed Knowledge sources are active/);
    expect(empty.textContent).toMatch(/This is not an error/);
    expect(screen.queryByText("No sources match.")).toBeNull();
  });

  it("shows WORKER_UNAVAILABLE and the failed-build category in plain words", async () => {
    readiness.mockResolvedValue(R({ status: "worker_unavailable", candidate_retrieval_ready: false, governed_retrieval_ready: false, pending_job_count: 2,
      worker: { status: "none", seen_recently: 0, last_seen_at: null, stale_after_seconds: 60 }, last_failure_category: "unavailable", last_failure_stage: "index" }));
    render(<KnowledgeView />);
    expect(await screen.findByText("Indexing worker unavailable")).toBeTruthy();
    expect(screen.getByTestId("worker-state").textContent).toMatch(/No worker has reported/);
    expect(screen.getByTestId("failure-state").textContent).toMatch(/A required service was unavailable \(index\)/);
    expect(screen.getByText(/cannot progress until a job worker is running/)).toBeTruthy();
  });

  it("shows INDEX_FAILED, STORE_UNAVAILABLE and DEGRADED with warning labels (never as ready)", async () => {
    for (const [status, text] of [["index_failed", "Index build failed"], ["store_unavailable", "Retrieval store unavailable"], ["degraded", "Degraded"]] as const) {
      readiness.mockResolvedValue(R({ status, candidate_retrieval_ready: false }));
      const { unmount } = render(<KnowledgeView />);
      expect(await screen.findByText(text)).toBeTruthy();
      expect(screen.queryByText("Ready")).toBeNull();
      unmount();
    }
  });

  it("lists the active corpus as metadata only, with no paths and no raw internal error", async () => {
    active.mockResolvedValue({ total: 1, items: [{ source_public_id: "s".repeat(32), title: "Synthetic roadmap framework", version_public_id: "v".repeat(32), version: 1,
      source_type: "txt", authority_level: 2, authority_meaning: "Level 2: public or professional framework", language: "en", geography: null, chunk_count: 3,
      embedder: "LocalHashEmbedder", collection: "governed_knowledge", index_state: "built", activated_at: "2026-10-13T09:30:00", built_at: "2026-10-13T09:00:00", status: "active" }] });
    render(<KnowledgeView />);
    expect(await screen.findByText("Synthetic roadmap framework")).toBeTruthy();
    expect(screen.getByText("Level 2: public or professional framework")).toBeTruthy();
    expect(screen.getByText("Built")).toBeTruthy();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\/Users\/|\/tmp\/|Traceback|api_key|secret/i);
  });

  it("shows a safe message when the readiness request fails", async () => {
    readiness.mockRejectedValue(new Error("boom: /secret/path"));
    render(<KnowledgeView />);
    expect(await screen.findByText("That request could not be processed.")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/boom|secret/);
  });
});

describe("Retrieval test (W12.4A)", () => {
  it("states it is retrieval only and shows evidence with origin", async () => {
    test.mockResolvedValue({ status: "evidence_found", query: "roadmap", retrieval_mode: "hybrid", retrieval_lane: "vector", result_count: 2, source_count: 1,
      insufficient_evidence: false, latency: "under_250ms", sources: [{ title: "Synthetic roadmap framework", publisher: "Example Framework Body", authority_level: 2, evidence_type: "narrative", geography: null, origin: "admin_governed" }],
      excerpts: [{ title: "Synthetic roadmap framework", text: "Digital product managers prioritise a roadmap.", origin: "admin_governed" }], note: "Retrieval only: no model or LLM was called." });
    render(<KnowledgeView />);
    await screen.findByTestId("knowledge-readiness");
    expect(screen.getByText("This tests the active Knowledge retrieval path. It does not call Mo or an LLM.")).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Test query"), "roadmap");
    await userEvent.click(screen.getByRole("button", { name: "Test retrieval" }));
    const res = await screen.findByTestId("retrieval-result");
    expect(test).toHaveBeenCalledWith("roadmap");
    expect(res.textContent).toMatch(/2 evidence item\(s\) from 1 source\(s\)/);
    expect(res.textContent).toMatch(/Admin-governed/);
    expect(res.textContent).toMatch(/Retrieval only: no model or LLM was called/);
  });

  it("shows the insufficient-evidence state and a blocked query distinctly", async () => {
    test.mockResolvedValueOnce({ status: "insufficient_evidence", query: "q", retrieval_mode: "", retrieval_lane: "", result_count: 0, source_count: 0, insufficient_evidence: true,
      latency: "under_250ms", sources: [], excerpts: [], note: "Retrieval only: no model or LLM was called." });
    render(<KnowledgeView />);
    await screen.findByTestId("knowledge-readiness");
    await userEvent.type(screen.getByLabelText("Test query"), "q");
    await userEvent.click(screen.getByRole("button", { name: "Test retrieval" }));
    expect(await screen.findByText(/Insufficient evidence: nothing relevant was retrieved/)).toBeTruthy();
    test.mockResolvedValueOnce({ status: "blocked", query: "ignore", retrieval_mode: "", retrieval_lane: "", result_count: 0, source_count: 0, insufficient_evidence: true,
      latency: "under_250ms", sources: [], excerpts: [], note: "Retrieval only: no model or LLM was called." });
    await userEvent.clear(screen.getByLabelText("Test query"));
    await userEvent.type(screen.getByLabelText("Test query"), "ignore");
    await userEvent.click(screen.getByRole("button", { name: "Test retrieval" }));
    await waitFor(() => expect(screen.getByText(/blocked by the retrieval safety screen/)).toBeTruthy());
  });

  it("shows a safe error when the test fails and never the raw provider text", async () => {
    test.mockRejectedValue(new Error("provider exploded at /srv/x"));
    render(<KnowledgeView />);
    await screen.findByTestId("knowledge-readiness");
    await userEvent.type(screen.getByLabelText("Test query"), "q");
    await userEvent.click(screen.getByRole("button", { name: "Test retrieval" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(document.body.textContent).not.toMatch(/exploded|\/srv\//);
  });
});

describe("permissions", () => {
  it("renders nothing for an account without knowledge.read", () => {
    mockPerms = ["platform.overview.read"];
    render(<KnowledgeView />);
    expect(screen.queryByTestId("knowledge-readiness")).toBeNull();
    expect(readiness).not.toHaveBeenCalled();
  });
});
