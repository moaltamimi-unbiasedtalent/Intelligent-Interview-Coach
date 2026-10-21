import { expect, test, type Page } from "@playwright/test";

// 02A Admin Knowledge environment identity panel and the separated CURATED / GOVERNED views, mocked at the network layer. The derivation of the
// identity, the guard and the refusal behaviour are proven by tests/test_knowledge_persistence_02a_*.py; these browser tests prove what the
// Admin sees and that no secret or path ever reaches the page.

const KB_ADMIN = ["platform.overview.read", "platform.knowledge.read", "platform.knowledge.manage", "platform.knowledge.approve"];
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };

const finding = (code: string, severity: "block" | "warn", message: string, fields: string[] = []) => ({ code, severity, message, fields });

function readiness(opts: { hosted?: boolean; worker?: string; findings?: ReturnType<typeof finding>[]; serving?: boolean; status?: string; fields?: string[] } = {}) {
  const hosted = opts.hosted ?? false;
  const findings = opts.findings ?? [];
  const serving = opts.serving ?? true;
  return {
    status: opts.status ?? "ready", message: serving ? "Governed knowledge is active, indexed and present in the store candidate retrieval reads." : "The knowledge environment guard is refusing governed retrieval: mismatch.",
    candidate_retrieval_ready: true, governed_retrieval_ready: serving, source_count: 1, active_source_count: 1, active_version_count: 1, indexed_active_version_count: 1,
    pending_job_count: 0, failed_job_count: 0, awaiting_review_count: 0, failed_version_count: 0,
    worker: { status: "available", seen_recently: 1, last_seen_at: "2026-10-21T10:00:00", stale_after_seconds: 60 },
    collection_status: "ok", collection: "governed_knowledge", store: { kind: "persistent", chunk_count: 4, location: "default" },
    embedding_provider_status: "available", embedder_state: { status: "available", provider: "local", embedder: "LocalHashEmbedder", note: "offline local embedder" },
    curated_corpus: { status: "available", chunk_count: 100, store_kind: "persistent" }, last_indexed_at: "2026-10-21T09:00:00", last_failure_category: null, last_failure_stage: null,
    views: {
      curated: { label: "Curated knowledge base", origin: "committed_corpus", admin_managed: false, description: "The committed corpus that ships with the product. It is read-only here and is not Admin-managed.", status: "available", chunk_count: 100 },
      governed: { label: "Admin-governed knowledge", origin: "admin_governed", admin_managed: true, description: "Sources an administrator registered, reviewed, approved, indexed and activated. Only active sources reach candidates.", status: opts.status ?? "ready", chunk_count: 4, active_source_count: 1, recorded_built_chunk_count: 4 },
    },
    environment: {
      environment: hosted ? "staging" : "development", hosted,
      database: { kind: "postgresql", fingerprint: "a".repeat(64) }, data_root: { label: "knowledge-data-root", short_hash: "0123456789ab" },
      private_files: { label: "knowledge-private-files", explicit: false, inside_data_root: true },
      collections: [{ collection_id: "career_knowledge_base", role: "curated", chunk_count: 100, persistent: true }, { collection_id: "governed_knowledge", role: "governed", chunk_count: 4, persistent: true }],
      manifest: { collection_id: "governed_knowledge", checksum: "f".repeat(64), source_version_count: 1, built_at: "2026-10-21T09:00:00", embedder_label: "LocalHashEmbedder", compatibility_hash: null, embedding_fields_known: false },
      embedder_identity: { provider: "local", model: "hash", dimensions: 256, degraded: false, degradation_reason: null },
      worker_identity: { status: opts.worker ?? "match", mismatched_fields: opts.fields ?? [], workers_checked: 1 },
      guard: { environment: hosted ? "staging" : "development", enforced: hosted, mode: hosted ? "enforced" : "development_warning", serving_allowed: serving, checked_at: "2026-10-21T10:00:00", findings },
      last_indexing: { result: "succeeded", at: "2026-10-21T09:00:00", failure_category: null },
    },
  };
}

async function mock(page: Page, body: unknown) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: "knowledge_admin", tier: "basic", status: "active", email_verified: true, providers: ["password"],
        auth_method: "session", capabilities: [], admin_permissions: KB_ADMIN, response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    }
    if (path.endsWith("/admin/knowledge/readiness")) return json(body);
    if (path.endsWith("/admin/knowledge/active")) return json({ items: [], total: 0 });
    if (path.endsWith("/admin/knowledge/meta")) {
      return json({ languages: ["en", "de", "fr", "es", "it", "pt", "nl"], authority_levels: [{ level: 1, meaning: "Level 1: official" }, { level: 2, meaning: "Level 2: framework" }, { level: 3, meaning: "Level 3: industry" }],
        licence_classes: [{ code: "public_official", label: "Public / official source", activatable: true }], states: [], rejection_reasons: [], upload: { max_bytes: 5242880, extensions: ["md", "pdf", "txt"], preview_chars: 4000 } });
    }
    if (path.endsWith("/admin/knowledge/sources")) return json({ items: [], total: 0, page: 1, page_size: 25 });
    if (path.endsWith("/knowledge/sources")) return json({ sources: [{ source_id: "onet", title: "O*NET Database", group: "occupations", source_type: "occupation_taxonomy", source_url: "https://www.onetcenter.org/", provider: "official", country: "US", reference_year: null }] });
    return json({});
  });
}

test("the identity panel shows the safe environment facts and a healthy match", async ({ page }) => {
  await mock(page, readiness({ hosted: true, findings: [finding("database_is_sqlite", "warn", "The registry database is SQLite (acceptable for development, not for a hosted deployment).")] }));
  await page.goto("/admin/knowledge");
  const panel = page.getByTestId("env-identity");
  await expect(panel).toBeVisible();
  await expect(page.getByTestId("env-name")).toContainText("staging (hosted: fails closed)");
  await expect(page.getByTestId("env-db")).toContainText("postgresql, fingerprint aaaaaaaaaaaa");
  await expect(page.getByTestId("env-root")).toContainText("knowledge-data-root, id 0123456789ab");
  await expect(page.getByTestId("env-worker")).toContainText("Matches the API");
  await expect(page.getByTestId("env-guard")).toContainText("Serving allowed");
  await expect(page.getByTestId("env-collections")).toContainText("governed_knowledge");
  await expect(page.getByTestId("env-manifest")).toContainText("embedding model fields not recorded");
  await expect(page.getByTestId("env-last-indexing")).toContainText("succeeded");
  const text = (await page.locator("body").innerText()) + (await page.content());
  expect(text).not.toMatch(/postgresql:\/\/|sqlite:\/\/|password|\/Users\/|\/Volumes\/|\/var\/folders\/|\/data\/knowledge/i);
});

test("an identity mismatch is shown as a refusal with the precise field, never as an empty source list", async ({ page }) => {
  await mock(page, readiness({ hosted: true, worker: "mismatch", fields: ["data_root.short_hash"], serving: false, status: "configuration_error",
    findings: [finding("identity_mismatch", "block", "The API and a live worker are configured with different knowledge environments (data root, database or embedding settings).", ["data_root.short_hash"])] }));
  await page.goto("/admin/knowledge");
  await expect(page.getByTestId("env-guard")).toContainText("Serving refused");
  await expect(page.getByTestId("finding-identity_mismatch")).toContainText("Blocking");
  await expect(page.getByTestId("finding-identity_mismatch")).toContainText("Differs: data root");
  await expect(page.getByTestId("env-worker")).toContainText("Does NOT match the API (data root)");
  await expect(page.getByTestId("knowledge-readiness")).toContainText("Configuration problem");
  await expect(page.getByTestId("candidate-ready")).toBeVisible();
});

test("development warnings are labelled and curated and governed knowledge are separate views", async ({ page }) => {
  await mock(page, readiness({ findings: [finding("worker_not_seen", "warn", "No worker has reported recently, so the worker's environment cannot be compared.")], worker: "no_worker" }));
  await page.goto("/admin/knowledge");
  await expect(page.getByTestId("env-guard")).toContainText("Development: warnings only");
  await expect(page.getByTestId("finding-worker_not_seen")).toContainText("Warning");
  const curated = page.getByTestId("curated-view");
  const governed = page.getByTestId("governed-view");
  await expect(curated).toContainText("read-only");
  await expect(curated).toContainText("100 chunks");
  await expect(curated).toContainText("Not managed from this page");
  await expect(governed).toContainText("1 active source(s)");
  await expect(governed).toContainText("4 chunks in the store");
  await expect(governed).toContainText("Managed on this page");
  await expect(page.getByRole("heading", { name: "Curated knowledge base (read-only)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Admin-governed knowledge" })).toBeVisible();
});
