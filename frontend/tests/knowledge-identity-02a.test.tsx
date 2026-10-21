import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 02A: the environment identity panel and the separated curated / governed views on /admin/knowledge. The API is mocked; the point is truthful presentation
// and that nothing path-like or secret-like is rendered.

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/knowledge" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: ["platform.knowledge.read"] }, status: "authenticated" }),
}));
vi.mock("@/components/i18n/I18nProvider", () => ({ useT: () => (k: string) => k }));

const readiness = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { knowledge: { sources: () => Promise.resolve({ sources: [] }) }, admin: {
    knowledgeReadiness: (...a: unknown[]) => readiness(...a), knowledgeActive: () => Promise.resolve({ items: [], total: 0 }),
    testKnowledgeRetrieval: vi.fn(), knowledgeSources: () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 25 }),
    knowledgeMeta: () => Promise.resolve({ languages: ["en"], authority_levels: [{ level: 1, meaning: "Level 1" }], licence_classes: [], states: [], rejection_reasons: [], upload: { max_bytes: 1, extensions: ["pdf"], preview_chars: 1 } }),
  } },
}));

import { KnowledgeView } from "@/components/admin/KnowledgeView";

const base = (env: Record<string, unknown>, over: Record<string, unknown> = {}) => ({
  status: "ready", message: "ok", candidate_retrieval_ready: true, governed_retrieval_ready: true, source_count: 1, active_source_count: 1, active_version_count: 1,
  indexed_active_version_count: 1, pending_job_count: 0, failed_job_count: 0, awaiting_review_count: 0, failed_version_count: 0,
  worker: { status: "available", seen_recently: 1, last_seen_at: null, stale_after_seconds: 60 }, collection_status: "ok", collection: "governed_knowledge",
  store: { kind: "persistent", chunk_count: 4, location: "default" }, embedding_provider_status: "available",
  embedder_state: { status: "available", provider: "local", embedder: "LocalHashEmbedder", note: "" }, curated_corpus: { status: "available", chunk_count: 100, store_kind: "persistent" },
  last_indexed_at: null, last_failure_category: null, last_failure_stage: null,
  views: { curated: { label: "c", origin: "committed_corpus", admin_managed: false, description: "Curated description.", status: "available", chunk_count: 100 },
           governed: { label: "g", origin: "admin_governed", admin_managed: true, description: "Governed description.", status: "ready", chunk_count: 4, active_source_count: 1 } },
  environment: {
    environment: "production", hosted: true, database: { kind: "postgresql", fingerprint: "b".repeat(64) }, data_root: { label: "knowledge-data-root", short_hash: "abcdef012345" },
    private_files: { label: "knowledge-private-files", explicit: false, inside_data_root: true },
    collections: [{ collection_id: "governed_knowledge", role: "governed", chunk_count: 4, persistent: true }, { collection_id: "career_knowledge_base", role: "curated", chunk_count: null, persistent: true }],
    manifest: { collection_id: "governed_knowledge", checksum: "c".repeat(64), source_version_count: 1, built_at: null, embedder_label: "LocalHashEmbedder", compatibility_hash: null, embedding_fields_known: false },
    embedder_identity: { provider: "local", model: "hash", dimensions: 256, degraded: false, degradation_reason: null },
    worker_identity: { status: "match", mismatched_fields: [], workers_checked: 1 },
    guard: { environment: "production", enforced: true, mode: "enforced", serving_allowed: true, checked_at: "2026-10-21T10:00:00", findings: [] },
    last_indexing: { result: "none", at: null, failure_category: null }, ...env,
  }, ...over,
});

beforeEach(() => readiness.mockReset().mockResolvedValue(base({})));

describe("Knowledge environment identity (02A)", () => {
  it("shows the safe identity facts and never a path or connection string", async () => {
    render(<KnowledgeView />);
    const panel = await screen.findByTestId("env-identity");
    expect(within(panel).getByTestId("env-name").textContent).toMatch(/production \(hosted: fails closed\)/);
    expect(within(panel).getByTestId("env-db").textContent).toMatch(/postgresql, fingerprint bbbbbbbbbbbb/);
    expect(within(panel).getByTestId("env-worker").textContent).toMatch(/Matches the API/);
    expect(within(panel).getByTestId("env-last-indexing").textContent).toMatch(/No indexing job has run/);
    expect(within(panel).getByTestId("env-collections").textContent).toMatch(/unreadable/);
    expect(panel.textContent).not.toMatch(/:\/\/|password|\/Users\/|\/data\//i);
  });

  it("presents an enforced mismatch as a refusal naming the differing field", async () => {
    readiness.mockResolvedValue(base({
      worker_identity: { status: "mismatch", mismatched_fields: ["database.fingerprint"], workers_checked: 1 },
      guard: { environment: "production", enforced: true, mode: "enforced", serving_allowed: false, checked_at: "x",
               findings: [{ code: "identity_mismatch", severity: "block", message: "The API and a live worker differ.", fields: ["database.fingerprint"] }] },
    }, { status: "configuration_error", governed_retrieval_ready: false }));
    render(<KnowledgeView />);
    expect((await screen.findByTestId("env-guard")).textContent).toMatch(/Serving refused/);
    expect(screen.getByTestId("finding-identity_mismatch").textContent).toMatch(/Blocking.*Differs: database/);
    expect(screen.getByTestId("env-worker").textContent).toMatch(/Does NOT match the API \(database\)/);
  });

  it("labels development findings as warnings and keeps curated and governed views separate", async () => {
    readiness.mockResolvedValue(base({
      environment: "development", hosted: false,
      guard: { environment: "development", enforced: false, mode: "development_warning", serving_allowed: true, checked_at: "x",
               findings: [{ code: "governed_collection_empty", severity: "block", message: "The collection is empty.", fields: [] }] },
    }));
    render(<KnowledgeView />);
    expect((await screen.findByTestId("env-guard")).textContent).toMatch(/Development: warnings only/);
    expect(screen.getByTestId("finding-governed_collection_empty").textContent).toMatch(/Would block when hosted/);
    expect(within(screen.getByTestId("curated-view")).getByText(/100 chunks/)).toBeTruthy();
    expect(within(screen.getByTestId("governed-view")).getByText(/1 active source\(s\)/)).toBeTruthy();
    expect(screen.getByTestId("curated-view").textContent).not.toMatch(/active source/);
  });

  it("still renders when the backend omits the new fields (backward compatible)", async () => {
    readiness.mockResolvedValue({ ...base({}), environment: undefined, views: undefined });
    render(<KnowledgeView />);
    expect(await screen.findByTestId("knowledge-readiness")).toBeTruthy();
    expect(screen.queryByTestId("env-identity")).toBeNull();
  });
});
