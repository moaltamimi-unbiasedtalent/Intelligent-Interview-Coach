import { expect, test, type Page } from "@playwright/test";

// P10B-W10.1 Admin shell + Command Center UX, mocked at the network layer. Server-side authorization,
// atomic audit and the safe provider schema are proven by the Python suites
// (tests/test_admin_foundation_w10_1.py, scripts/eval_admin_foundation.py); these browser tests prove the
// capability-aware navigation, the truthful Command Center and the candidate denial.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

const ADMIN_PERMS = [
  "platform.overview.read", "platform.users.read", "platform.users.manage", "platform.users.role.assign",
  "platform.users.sessions.revoke", "platform.workspaces.read", "platform.workspaces.manage", "platform.audit.read",
  "platform.support.read", "platform.support.reply", "platform.support.manage", "platform.support.note",
  "platform.plans.read", "platform.plans.manage", "platform.subscriptions.manage", "platform.integrations.manage",
  "platform.integrations.read", "platform.ai.read", "platform.knowledge.read", "platform.jobs.read", "platform.jobs.manage",
  "platform.knowledge.manage", "platform.knowledge.approve",
  "platform.privacy.read", "platform.privacy.execute", "platform.legal.manage",
];

function account(role: string, perms: string[]) {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: role,
    tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief",
    interface_locale: "en", conversation_language: "en",
  };
}

const HOME = {
  build: { version: "0.1.0", git_sha: "abc1234", build_time: "2026-10-02T10:00:00Z", environment: "staging", source: "x" },
  migrations: { repository_head: "0014_opportunities", database_revision: "0014_opportunities", state: "match", warning: null },
  health: { database: "reachable", providers_probed: false, note: "" },
  rate_limit: { mode: "in_memory_process_local", distributed: false, shared_store_requested: false, note: "" },
  pause: { paused: {}, durable: false, note: "Process-local and non-durable." },
  privacy_requests: { status: "not_operational", note: "Privacy-request administration is not available yet." },
  accounts: { users_total: 5, platform_admins: 1, premium_accounts: 2 },
  workspaces: { workspaces_total: 3 },
  diagnostics_links: [{ label: "Knowledge readiness", path: "/review/rag" }],
  boundary: "Operational metadata only. No candidate-private content is accessible here.",
};

const USER_ROW = { user_id: 2, email: "jane@example.com", display_name: null, status: "active", platform_role: "user", tier: "basic",
  onboarding_completed: true, interface_locale: "en", email_verified: false, created_at: null, updated_at: null,
  workspace_count: 1, active_session_count: 1 };
const USER_DETAIL = {
  plan: { current: { plan_code: "basic", version: 1, display_name: "Basic", status: "active", source: "system_default", started_at: "2026-10-01", ended_at: null }, history: [] },
  account: USER_ROW,
  access: { platform_role: "user", capabilities: [], assignable_roles: ["user", "support_operator"], is_self: false },
  sessions: { active_count: 1, recent: [{ created_at: "2026-10-01T10:00:00", last_used_at: null, expires_at: "2026-10-30T10:00:00" }] },
  workspaces: [{ workspace_id: 3, name: "Team Alpha", workspace_status: "active", role: "workspace_member", membership_status: "active", joined_at: null }],
  audit: [],
};
// Stateful stand-in for the knowledge lifecycle. The test plays the W10.9 worker by calling kb.worker(); the real lifecycle with a
// real worker is proven by tests/test_knowledge_admin_w10_8.py and the manual QA.
const PRIV_ID = "p".repeat(32);
const priv = {
  status: "submitted", assignee: null as number | null, result: null as string | null, legalPublished: false,
  row() {
    return { public_id: PRIV_ID, request_type: "correction", type_label: "Correction of my data", status: this.status, result_category: this.result,
      created_at: "2026-10-03T10:00:00", updated_at: null, source: "candidate_portal", user_id: 5, candidate_email: "cand@example.com",
      assigned_user_id: this.assignee, assignee_email: this.assignee ? "admin@example.com" : null, acknowledged_at: null, completed_at: null, closed_at: null, related_job_id: null };
  },
  next() { return ({ submitted: ["acknowledged", "rejected"], acknowledged: ["in_progress", "waiting_for_user", "completed", "rejected"], in_progress: ["waiting_for_user", "completed", "rejected"], completed: ["closed"] } as Record<string, string[]>)[this.status] ?? []; },
  detail() {
    return { ...this.row(), request_note: "Please correct my surname.", candidate: { user_id: 5, email: "cand@example.com", status: "active", platform_role: "user", created_at: null },
      allowed_statuses: this.next(), result_categories: ["correction_made", "information_provided"], can_execute_deletion: false,
      legal: [{ document: "terms", current_version: "baseline-1", accepted_current: false, last_accepted_at: null }], audit: [] };
  },
  version(id: number, state: string) {
    return { id, version: id === 1 ? "baseline-1" : "2.0", state, is_baseline: id === 1, content_ref: "/terms", content_hash: id === 1 ? null : "a".repeat(64),
      effective_at: id === 1 ? null : "2026-12-01T00:00:00", published_at: state === "draft" ? null : "2026-10-03T10:00:00", created_at: null, acceptances: id === 1 ? 2 : 0 };
  },
  legal() {
    const pub = this.legalPublished;
    const v1 = this.version(1, pub ? "retired" : "published"), v2 = this.version(2, pub ? "published" : "draft");
    return { documents: [{ code: "terms", title: "Terms of use", current: pub ? v2 : v1, versions: [v2, v1], current_accepted: pub ? 0 : 2, current_not_recorded: pub ? 5 : 3 }],
      active_accounts: 5, note: "Counts reflect RECORDED acceptances only. This is not a compliance measure." };
  },
};
const kb = {
  state: "none" as string,
  worker() {
    if (this.state === "queued") this.state = "review_required";
    else if (this.state === "indexing") this.state = "indexed";
  },
  view() {
    const s = this.state;
    return {
      source_public_id: "s".repeat(32), title: "Product framework", version_public_id: "v".repeat(32), version: 1, state: s, active: s === "active",
      language: "en", authority_level: 2, authority_meaning: "Level 2: public or professional framework", publisher: "Example Body",
      licence_class: "public_official", licence_label: "Public / official source", scan_status: s === "queued" ? "not_scanned" : "scan_passed",
      chunk_count: ["indexed", "active", "retired"].includes(s) ? 3 : null, failure_category: null, created_at: "2026-10-03T10:00:00", updated_at: "2026-10-03T10:00:00",
      source_reference: "https://example.org/f", provenance_note: "Public framework.", original_filename: "framework.txt", media_type: "text/plain", byte_size: 120,
      checksum_sha256: "a".repeat(64), scanner: "fake", extracted_chars: s === "queued" ? null : 120,
      preview: s === "queued" ? null : "Product managers prioritise a roadmap. <script>alert(1)</script>", preview_is_truncated: false, failed_stage: null,
      rejection_reason: null, approved_at: ["approved", "indexing", "indexed", "active"].includes(s) ? "2026-10-03T10:05:00" : null, approved_by_user_id: 1,
      indexed_at: null, activated_at: null, retired_at: null, parse_job_id: "p".repeat(32), index_job_id: s === "indexing" || s === "indexed" || s === "active" ? "i".repeat(32) : null,
      index: ["indexed", "active"].includes(s) ? { state: "built", chunk_count: 3, embedder: "LocalHashEmbedder", collection: "governed_knowledge", built_at: null } : null,
      blockers: [], metadata_frozen: !["queued", "review_required", "failed"].includes(s), audit: [],
      can: { edit: s === "review_required", approve: s === "review_required", reject: s === "review_required" || s === "approved", index: s === "approved",
        activate: s === "indexed", retire: s === "active" || s === "indexed", reprocess: false, delete: s === "review_required" },
    };
  },
};
const jobState = { retried: false, cancelled: false };
const JOB_BASE = {
  job_type: "diagnostic_noop", type_label: "Operational diagnostic (no-op)", priority: "normal", max_attempts: 2, manual_retries: 0,
  available_at: "2026-10-03T10:00:00+00:00", created_at: "2026-10-03T10:00:00+00:00", updated_at: null, started_at: null,
  lease: { held: false, owner: null, expires_at: null, heartbeat_at: null, stale: false }, waiting_for_retry: false,
  payload_summary: { label: "Console check" },
};
const FAILED_ID = "b".repeat(32), QUEUED_ID = "a".repeat(32);
const failedJob = () => ({ ...JOB_BASE, public_id: FAILED_ID, state: jobState.retried ? "queued" : "failed", attempts: jobState.retried ? 0 : 2,
  finished_at: jobState.retried ? null : "2026-10-03T10:05:00+00:00", error_category: jobState.retried ? null : "configuration_error",
  error_message: jobState.retried ? null : "A required integration is not configured or was rejected.", can_retry: !jobState.retried, can_cancel: jobState.retried,
  manual_retries: jobState.retried ? 1 : 0 });
const queuedJob = () => ({ ...JOB_BASE, public_id: QUEUED_ID, state: jobState.cancelled ? "cancelled" : "queued", attempts: 0,
  finished_at: jobState.cancelled ? "2026-10-03T10:06:00+00:00" : null, error_category: null, error_message: null, can_retry: false, can_cancel: !jobState.cancelled });
const itState = { tested: false };
const INT_ROW = (tested: boolean) => ({
  code: "openrouter", name: "OpenRouter (language models)", category: "ai_model", category_label: "AI / model", adapter: "OpenRouter chat API",
  description: "Chat model provider.", classification: "runtime_active", configuration_status: "configured",
  slots: [{ slot: "api_key", label: "API key", external_name: "OPENROUTER_API_KEY", configured: true, source: "environment", writable: false }],
  settings: [], runtime: { enabled: true, managed: "environment", toggle_supported: false, note: "Runtime state is owned by the deployment environment." },
  store: { name: "environment", writable: false },
  health: tested ? { status: "healthy", last_tested_at: "2026-10-03T10:00:00", category: "ok", latency_ms: 11 } : { status: "not_tested", last_tested_at: null, category: null, latency_ms: null },
  test: { supported: true, note: "Calls one key-information endpoint." }, validation_note: "Healthy only after a successful manual test." });
const INT_GOOGLE = { ...INT_ROW(false), code: "google_oidc", name: "Google sign-in (OIDC)", category: "authentication", category_label: "Authentication",
  classification: "code_present_not_validated", test: { supported: false, note: "No manual probe." },
  validation_note: "Backend support present; end-to-end sign-in is not validated." };
const PLAN_ROWS = [
  { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", enabled_entitlements: 5, total_entitlements: 5, subscribers: { users: 1, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: null },
  { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", enabled_entitlements: 4, total_entitlements: 5, subscribers: { users: 4, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: null },
];
const PLAN_DETAIL = { id: 3, plan_code: "premium", version: 2, display_name: "Premium (preview)", status: "draft", editable: true,
  entitlements: ["current_market_research", "standard_history", "standard_progress", "standard_model_profiles", "premium_preview"].map((k) => ({ code: k, label: `Label ${k}`, description: "d", type: "boolean", enabled: true, limit: null })),
  subscribers: { users: 0, workspaces: 0 }, created_at: null, activated_at: null, retired_at: null };
const MY_PLAN = { plan_code: "basic", plan_version: 1, entitlements: { current_market_research: { enabled: true, limit: null, unlimited: true }, premium_preview: { enabled: false, limit: null, unlimited: false } } };
const TICKET_ROW = { id: 5, public_id: "d".repeat(32), owner_user_id: 2, owner_email: "jane@example.com", category: "billing", priority: "normal",
  status: "new", subject: "Charged twice", assigned_user_id: null, assignee_email: null, message_count: 1, created_at: null, updated_at: null };
const TICKET_DETAIL = {
  ticket: { ...TICKET_ROW, initial_request_id: "req-1", source_route: "/pricing", source_environment: "test", resolved_at: null, closed_at: null, allowed_statuses: ["triaged", "in_progress", "closed"] },
  messages: [{ id: 1, author_kind: "candidate", author_user_id: 2, body: "I was charged twice.", request_id: "req-1", created_at: null }],
  internal_notes: [{ id: 2, author_user_id: 3, body: "Check the billing log", request_id: null, created_at: null }],
  account: USER_ROW, priorities: ["low", "normal", "high", "urgent"], statuses: [],
};
const WS_ROW = { id: 3, name: "Team Alpha", status: "active", owner_user_id: 1, owner_email: "owner@example.com", member_count: 2, created_at: null };
const WS_DETAIL = {
  workspace: WS_ROW,
  members: [{ user_id: 1, email: "owner@example.com", account_status: "active", role: "workspace_owner", membership_status: "active", joined_at: null },
            { user_id: 2, email: "jane@example.com", account_status: "active", role: "workspace_member", membership_status: "active", joined_at: null }],
  active_share_count: 0, active_owner_count: 1, workspace_roles: ["workspace_owner", "workspace_member"],
};

async function mockAdmin(page: Page, role: string, perms: string[], authed = true) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });

    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      if (!authed) return json({ error: { code: "unauthorized", message: "x" } }, 401);
      return json(account(role, perms));
    }
    if (path.endsWith("/admin/home")) return json(HOME);
    const method = route.request().method();
    if (path.endsWith("/admin/privacy/preparation/backfill") && method === "POST") return json({ job_id: "j", created: true }, 202);
    if (path.endsWith("/admin/privacy/preparation")) return json({ indexed_runs: 4, by_state: { ready: 4 }, by_source: { created: 3, backfill: 1 }, coverage_version: 1,
      note: "Counts indexed runs only. Historical runs with no relational reference cannot be discovered and are not included." });
    if (/\/admin\/privacy\/requests\/[^/]+\/assign$/.test(path) && method === "POST") { priv.assignee = 1; return json(priv.detail()); }
    if (/\/admin\/privacy\/requests\/[^/]+\/status$/.test(path) && method === "POST") {
      const b = JSON.parse(route.request().postData() ?? "{}");
      priv.status = b.status; if (b.result_category) priv.result = b.result_category;
      return json(priv.detail());
    }
    if (/\/admin\/privacy\/requests\/[^/]+$/.test(path)) return json(priv.detail());
    if (path.endsWith("/admin/privacy/requests")) return json({ items: [priv.row()], total: 1, page: 1, page_size: 25 });
    if (/\/admin\/legal\/versions\/\d+\/publish$/.test(path) && method === "POST") { priv.legalPublished = true; return json(priv.version(2, "published")); }
    if (path.endsWith("/admin/legal")) return json(priv.legal());
    if (path.endsWith("/admin/knowledge/meta")) return json({ languages: ["en", "de", "fr", "es", "it", "pt", "nl"],
      authority_levels: [{ level: 1, meaning: "Level 1: official or statistical source" }, { level: 2, meaning: "Level 2: public or professional framework" }, { level: 3, meaning: "Level 3: reputable public industry research" }],
      licence_classes: [{ code: "public_official", label: "Public / official source", activatable: true }, { code: "unclear", label: "Unclear (cannot be activated)", activatable: false }],
      states: ["queued", "review_required", "approved", "indexing", "indexed", "active", "retired"], rejection_reasons: ["out_of_scope"],
      upload: { max_bytes: 5242880, extensions: ["md", "pdf", "txt"], preview_chars: 4000 } });
    if (path.endsWith("/admin/knowledge/sources") && method === "POST") {
      kb.state = "queued";
      return json({ source_public_id: "s".repeat(32), version_public_id: "v".repeat(32), version: 1 }, 201);
    }
    if (/\/admin\/knowledge\/versions\/[^/]+\/(approve|index|activate|retire)$/.test(path) && method === "POST") {
      const act = path.split("/").pop() as string;
      kb.state = { approve: "approved", index: "indexing", activate: "active", retire: "retired" }[act] as string;
      return json(kb.view());
    }
    if (/\/admin\/knowledge\/versions\/[^/]+$/.test(path)) return json(kb.view());
    if (/\/admin\/knowledge\/sources\/[^/]+$/.test(path)) return json({ source_public_id: "s".repeat(32), title: "Product framework", created_at: null, versions: [kb.view()] });
    if (path.endsWith("/admin/knowledge/sources")) return json({ items: kb.state === "none" ? [] : [kb.view()], total: kb.state === "none" ? 0 : 1, page: 1, page_size: 25 });
    if (path.endsWith("/admin/jobs/diagnostics")) return json({ queue: { queued: 1, running: 0, failed: 1, succeeded: 4, cancelled: 0, retry_waiting: 0, stale_leases: 0, oldest_ready_age_seconds: 12 },
      by_type: [], workers: { seen_recently: 1, last_seen_at: "2026-10-03T10:00:00+00:00", stale_after_seconds: 60, items: [] } });
    if (path.endsWith("/admin/jobs/types")) return json([{ job_type: "diagnostic_noop", label: "Operational diagnostic (no-op)", max_attempts: 2, manual_retry: true, cancellable_when_queued: true, idempotency: "x" }]);
    if (/\/admin\/jobs\/[^/]+\/retry$/.test(path) && method === "POST") {
      jobState.retried = true;
      return json(failedJob());
    }
    if (/\/admin\/jobs\/[^/]+\/cancel$/.test(path) && method === "POST") {
      jobState.cancelled = true;
      return json(queuedJob());
    }
    if (/\/admin\/jobs\/[^/]+$/.test(path)) return json({ ...(path.includes(FAILED_ID) ? failedJob() : queuedJob()), audit: [] });
    if (path.endsWith("/admin/jobs")) {
      const st = new URL(route.request().url()).searchParams.get("state");
      const items = [queuedJob(), failedJob()].filter((j) => !st || j.state === st);
      return json({ items, total: items.length, page: 1, page_size: 25 });
    }
    if (/\/admin\/integrations\/[^/]+\/test$/.test(path) && method === "POST") {
      itState.tested = true;
      return json({ integration: "openrouter", outcome: "success", category: "ok", latency_ms: 11 });
    }
    if (/\/admin\/integrations\/[^/]+$/.test(path)) return json({ ...INT_ROW(itState.tested), audit: [] });
    if (path.endsWith("/admin/integrations")) return json({ items: [INT_ROW(itState.tested), INT_GOOGLE] });
    if (/\/admin\/plans\/versions\/\d+\/(activate|retire)$/.test(path) && method === "POST") return json({ ok: true });
    if (/\/admin\/plans\/versions\/\d+\/entitlements$/.test(path) && method === "PATCH") return json({ id: 3, changed: ["premium_preview"] });
    if (/\/admin\/plans\/[^/]+\/versions$/.test(path) && method === "POST") return json({ id: 3, plan_code: "premium", version: 2 });
    if (path.endsWith("/admin/plans/assignable")) return json([{ plan_code: "basic", version: 1, display_name: "Basic" }, { plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
    if (/\/admin\/plans\/\d+$/.test(path)) return json(PLAN_DETAIL);
    if (path.endsWith("/admin/plans")) return json({ items: PLAN_ROWS });
    if (/\/admin\/users\/\d+\/plan$/.test(path) && method === "POST") return json({ subject_type: "user", subject_id: 2, plan_code: "premium", version: 1, changed: true });
    if (path.endsWith("/auth/plan")) return json(MY_PLAN);
    if (/\/admin\/support\/tickets\/[^/]+\/(assign|status|priority|reply|notes)$/.test(path) && method === "POST") return json({ ok: true });
    if (path.endsWith("/admin/support/assignees")) return json([{ user_id: 3, email: "op@example.com", platform_role: "support_operator" }]);
    if (/\/admin\/support\/tickets\/[^/]+$/.test(path)) return json(TICKET_DETAIL);
    if (path.endsWith("/admin/support/tickets")) {
      const q = new URL(route.request().url()).searchParams;
      const items = [TICKET_ROW].filter((t) => !q.get("status") || t.status === q.get("status"));
      return json({ items, total: items.length, page: 1, page_size: 25 });
    }
    if (/\/admin\/users\/\d+\/status$/.test(path) && method === "POST") return json({ user_id: 2, status: "deactivated", changed: true, sessions_revoked: 1 });
    if (/\/admin\/users\/\d+\/sessions\/revoke$/.test(path) && method === "POST") return json({ user_id: 2, sessions_revoked: 1 });
    if (/\/admin\/users\/\d+$/.test(path)) return json(USER_DETAIL);
    if (path.endsWith("/admin/users")) {
      const q = new URL(route.request().url()).searchParams.get("q") ?? "";
      const items = [USER_ROW].filter((u) => !q || u.email.includes(q));
      return json({ items, users: items, total: items.length, page: 1, page_size: 25 });
    }
    if (/\/admin\/workspaces\/\d+$/.test(path)) return json(WS_DETAIL);
    if (path.endsWith("/admin/workspaces"))
      return json({ items: [WS_ROW], workspaces: [WS_ROW], total: 1, page: 1, page_size: 25 });
    if (path.endsWith("/admin/providers"))
      return json({
        providers: [{ provider_id: "openrouter", label: "Language model provider (OpenRouter)", configured: true, enabled: true,
          externally_managed: true, writable: false, status: "configured_health_not_tested", health: "Health not tested",
          live_validation: "UNVALIDATED", mode: null }],
        speech: {}, ocr: { engine: "tesseract", available: true, pdf_ocr_available: true, poppler_available: true, live_quality: "UNVALIDATED" },
        pause: {}, pause_durable: false, rate_limit_mode: "in_memory_process_local", rate_limit_distributed: false,
        note: "Configured does not mean healthy; no provider is contacted here.",
      });
    if (path.endsWith("/admin/audit"))
      return json({ events: [{ event_type: "admin.account_status_change", result: "success", actor_user_id: 1, target_type: "user",
        target_id: "2", request_id: "req-abc", context: { before: "active", after: "deactivated" }, created_at: null }] });
    return json({});
  });
}

test("platform admin journey: Command Center, build metadata, audit, provider status, diagnostic link", async ({ page }) => {
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByText("abc1234")).toBeVisible();
  await expect(page.getByText("Up to date")).toBeVisible();
  await expect(page.getByText("Health not tested").first()).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Admin" });
  for (const label of ["Overview", "Users", "Workspaces", "Review / Diagnostics", "Audit", "Provider status", "Jobs", "Knowledge", "Privacy", "Legal"]) {
    await expect(nav.getByRole("link", { name: new RegExp(label) })).toBeVisible();
  }
  for (const future of ["Billing", "Subscriptions", "Incidents", "Feature Flags"]) {
    await expect(nav.getByRole("link", { name: new RegExp(future) })).toHaveCount(0);
  }
  await expect(page.getByRole("link", { name: "Knowledge readiness" })).toHaveAttribute("href", "/review/rag");

  await nav.getByRole("link", { name: /Audit/ }).click();
  await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
  await expect(page.getByText("req-abc")).toBeVisible();
  await expect(page.getByText("active to deactivated")).toBeVisible();

  await nav.getByRole("link", { name: /Provider status/ }).click();
  await expect(page.getByText("Language model provider (OpenRouter)")).toBeVisible();
  await expect(page.getByText("Health not tested")).toBeVisible();
  await expect(page.getByText(/sk-[a-z0-9]/i)).toHaveCount(0);
  // No candidate-private content anywhere on the admin surface.
  await expect(page.getByText(/curriculum vitae|raw answer|memory summary|password_hash/i)).toHaveCount(0);
});

test("W10.2: users search, safe detail, governed action with confirmation, workspace membership", async ({ page }) => {
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Users/ }).click();
  await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible();
  await page.getByLabel("Email or account id").fill("jane");
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("link", { name: "jane@example.com" }).click();
  await expect(page.getByRole("heading", { name: "Sessions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Access" })).toBeVisible();
  // No candidate-private content on a user's admin page.
  await expect(page.getByText(/curriculum vitae|interview answer|memory summary|conversation/i)).toHaveCount(0);
  await page.getByRole("button", { name: "Deactivate account" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await dialog.getByRole("button", { name: "Deactivate" }).click();
  await expect(page.getByText(/Account deactivated/)).toBeVisible();
  await page.getByRole("link", { name: "Team Alpha" }).click();
  await expect(page.getByRole("heading", { name: "Members" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove: jane@example.com" })).toBeVisible();
  await page.getByRole("button", { name: "Remove: jane@example.com" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();
});

test("W10.6: integrations inventory, environment-managed credential, manual test, read-only role", async ({ page }) => {
  itState.tested = false;
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Integrations/ }).click();
  await expect(page.getByRole("heading", { name: "Integrations", exact: true })).toBeVisible();
  await expect(page.getByText("Code present, not validated")).toBeVisible();
  await expect(page.getByText("Not tested").first()).toBeVisible();
  await page.getByRole("link", { name: "OpenRouter (language models)" }).click();
  await expect(page.getByText(/Managed outside Ask4Mo/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Replace|Set credential|Reveal|Rotate/ })).toHaveCount(0);
  await expect(page.locator('input[type="password"], input[type="url"]')).toHaveCount(0);
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByText("Connection test succeeded.")).toBeVisible();
  await expect(page.getByText("Last test succeeded")).toBeVisible();

  await page.unroute("**/api/v1/**");
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.integrations.read"]);
  await page.goto("/admin/integrations/openrouter");
  await expect(page.getByRole("heading", { name: "Connection test" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Test connection" })).toHaveCount(0);
});

test("W10.10: privacy queue, detail, assign, acknowledge, complete with a result, then legal registry publish; read-only role", async ({ page }) => {
  priv.status = "submitted"; priv.assignee = null; priv.result = null; priv.legalPublished = false;
  await mockAdmin(page, "security_privacy_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: /^Privacy/ }).click();
  await expect(page.getByRole("heading", { name: "Privacy", exact: true })).toBeVisible();
  await expect(page.getByText(/never shows a candidate's documents/)).toBeVisible();
  await expect(page.getByText(/cannot be discovered and are not included/)).toBeVisible();
  await page.getByRole("link", { name: PRIV_ID }).click();
  await expect(page.getByRole("heading", { name: "Candidate (account metadata only)" })).toBeVisible();
  await expect(page.getByTestId("privacy-note")).toContainText("Please correct my surname.");
  await expect(page.getByRole("button", { name: "Mark completed" })).toHaveCount(0);               // not a valid next step yet
  await page.getByRole("button", { name: "Assign to me" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Assigned to you.")).toBeVisible();
  for (const [btn, shown] of [["Mark acknowledged", "Status changed to acknowledged."], ["Mark in progress", "Status changed to in progress."]]) {
    await page.getByRole("button", { name: btn }).click();
    await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
    await page.getByRole("alertdialog").getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText(shown)).toBeVisible();
  }
  await page.getByRole("button", { name: "Mark completed" }).click();
  await page.getByRole("alertdialog").getByLabel("Result").selectOption("correction_made");
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Status changed to completed.")).toBeVisible();

  await page.goto("/admin/legal");
  await expect(page.getByRole("heading", { name: "Legal", exact: true })).toBeVisible();
  await expect(page.getByText(/baseline created when versioning was introduced/)).toBeVisible();
  await page.getByRole("button", { name: "Publish Terms of use version 2.0" }).click();
  await expect(page.getByRole("alertdialog").getByText(/can never be edited/)).toBeVisible();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText(/Version published/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Publish Terms of use/ })).toHaveCount(0);

  await page.unroute("**/api/v1/**");
  await mockAdmin(page, "platform_admin", ["platform.overview.read", "platform.privacy.read"]);
  await page.goto(`/admin/privacy/${PRIV_ID}`);
  await expect(page.getByRole("heading", { name: "Candidate (account metadata only)" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Assign|Mark|Delete the account/ })).toHaveCount(0);
});

test("W10.8: upload, scan/parse (worker), preview, approve, index (worker), activate, retire, read-only role", async ({ page }) => {
  kb.state = "none";
  await mockAdmin(page, "knowledge_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: /Knowledge/ }).click();
  await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();
  await expect(page.getByText("No sources match.")).toBeVisible();
  await page.getByLabel("Title", { exact: true }).fill("Product framework");
  await page.getByLabel("Publisher", { exact: true }).fill("Example Body");
  await page.getByLabel(/^File/).setInputFiles({ name: "framework.txt", mimeType: "text/plain", buffer: Buffer.from("Product managers prioritise a roadmap.") });
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/queued for scanning and parsing/)).toBeVisible();
  await expect(page.getByRole("table").getByText("Queued for scanning")).toBeVisible();
  kb.worker();                                                   // the W10.9 worker scans and parses
  await page.reload();
  await page.getByRole("link", { name: "Product framework" }).click();
  await expect(page.getByRole("heading", { name: "Preview" })).toBeVisible();
  await expect(page.getByTestId("knowledge-preview")).toContainText("<script>alert(1)</script>");   // shown as text, not executed
  await expect(page.getByText("Not active; not used in candidate answers")).toBeVisible();
  await expect(page.getByRole("button", { name: "Activate version" })).toHaveCount(0);              // parsed != approved != active
  await page.getByRole("button", { name: "Approve version" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("button", { name: "Queue indexing" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Activate version" })).toHaveCount(0);              // approved != indexed
  await page.getByRole("button", { name: "Queue indexing" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Queue indexing" }).click();
  await expect(page.getByRole("table").getByText(/Indexing/)).toBeVisible();
  kb.worker();                                                   // the worker indexes
  await page.reload();
  await expect(page.getByRole("button", { name: "Activate version" })).toBeVisible();               // indexed, still not active
  await page.getByRole("button", { name: "Activate version" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Activate" }).click();
  await expect(page.getByRole("table").getByText(/Active/)).toBeVisible();
  await page.getByRole("button", { name: "Retire version" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Retire" }).click();
  await expect(page.getByRole("table").getByText(/Retired/)).toBeVisible();

  await page.unroute("**/api/v1/**");
  await mockAdmin(page, "platform_admin", ["platform.overview.read", "platform.knowledge.read"]);
  await page.goto(`/admin/knowledge/${"s".repeat(32)}`);
  await expect(page.getByRole("heading", { name: "Provenance and use rights" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Approve|Reject|Queue indexing|Activate|Retire|Delete|Upload/ })).toHaveCount(0);
});

test("W10.9: jobs queue, failed filter, detail diagnostics, retry, cancel queued, read-only role", async ({ page }) => {
  jobState.retried = false;
  jobState.cancelled = false;
  await mockAdmin(page, "operations_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: /Jobs/ }).click();
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
  await expect(page.getByText("Workers seen recently")).toBeVisible();
  await page.getByLabel("State").selectOption("failed");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("link", { name: "Operational diagnostic (no-op)" })).toHaveCount(1);
  await page.getByRole("link", { name: "Operational diagnostic (no-op)" }).click();
  await expect(page.getByRole("heading", { name: "Execution" })).toBeVisible();
  await expect(page.getByText("Configuration problem")).toBeVisible();
  await expect(page.getByText(/Raw job input is never displayed/)).toBeVisible();
  await page.getByRole("button", { name: "Retry job" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Retry job" }).click();
  await expect(page.getByText("Job queued for another run.")).toBeVisible();
  await page.goto(`/admin/jobs/${QUEUED_ID}`);
  await page.getByRole("button", { name: "Cancel queued job" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel job" }).click();
  await expect(page.getByText("Job cancelled.")).toBeVisible();

  await page.unroute("**/api/v1/**");
  await mockAdmin(page, "knowledge_admin", ["platform.overview.read", "platform.jobs.read"]);
  await page.goto(`/admin/jobs/${FAILED_ID}`);
  await expect(page.getByRole("heading", { name: "Execution" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Retry job|Cancel queued job/ })).toHaveCount(0);
});

test("W10.4: plan catalogue, draft version, user plan assignment, candidate plan view", async ({ page }) => {
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Plans/ }).click();
  await expect(page.getByRole("heading", { name: "Plans", exact: true })).toBeVisible();
  await expect(page.getByText("5 of 5 enabled")).toBeVisible();
  await expect(page.getByText(/no prices, payments or invoices/)).toBeVisible();
  await page.getByRole("button", { name: "Create next draft of premium" }).click();
  await expect(page.getByText(/Draft version 2 of premium created/)).toBeVisible();
  await page.goto("/admin/plans/3");
  await expect(page.getByRole("heading", { name: "Entitlements" })).toBeVisible();
  await page.getByRole("button", { name: "Activate this version" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();

  await page.goto("/admin/users/2");
  await expect(page.getByRole("heading", { name: "Plan", exact: true })).toBeVisible();
  await expect(page.getByText("Basic (version 1)")).toBeVisible();
  await page.getByLabel("Change plan").selectOption("premium");
  await page.getByRole("button", { name: "Change plan" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Change plan" }).click();
  await expect(page.getByText(/Plan changed to Premium \(preview\)/)).toBeVisible();
});

test("W10.4: the candidate account page shows the plan truthfully with nothing to buy", async ({ page }) => {
  await mockAdmin(page, "user", []);
  await page.goto("/account");
  await expect(page.getByTestId("plan-summary")).toBeVisible();
  await expect(page.getByText("Premium is a preview.", { exact: false })).toBeVisible();
  await expect(page.getByTestId("plan-summary").getByRole("button")).toHaveCount(0);
  await expect(page.getByTestId("plan-summary").getByRole("link")).toHaveCount(0);
});

test("W10.3: support queue, filter, ticket detail, assign, status, reply and internal note", async ({ page }) => {
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.support.read", "platform.support.reply", "platform.support.manage", "platform.support.note"]);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await nav.getByRole("link", { name: /Support/ }).click();
  await expect(page.getByRole("heading", { name: "Support", exact: true })).toBeVisible();
  await page.getByLabel("Status").selectOption("new");
  await page.getByRole("button", { name: "Apply" }).click();
  await page.getByRole("link", { name: /Charged twice/ }).click();
  await expect(page.getByRole("heading", { name: "Ticket", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Messages (visible to the candidate)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Internal notes (never visible to the candidate)" })).toBeVisible();
  await expect(page.getByText("Check the billing log")).toBeVisible();

  await page.getByLabel("Assignee").focus();
  await page.getByLabel("Assignee").selectOption("3");
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Ticket assigned.")).toBeVisible();
  await page.getByLabel("Move to").selectOption("triaged");
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Change status" }).click();
  await expect(page.getByText("Status changed to triaged.")).toBeVisible();
  await page.getByLabel(/Reply \(the candidate/).fill("We are on it.");
  await page.getByRole("button", { name: "Send reply to candidate" }).click();
  await expect(page.getByText(/candidate sees it/)).toBeVisible();
  await page.getByLabel("Internal note (staff only)").fill("Escalated to billing");
  await page.getByRole("button", { name: "Save internal note" }).click();
  await expect(page.getByText(/never shown to the candidate/).first()).toBeVisible();
});

test("a limited admin role sees only the destinations the server granted", async ({ page }) => {
  await mockAdmin(page, "support_operator", ["platform.overview.read", "platform.users.read"]);
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "Admin" });
  await expect(nav.getByRole("link", { name: /Users/ })).toBeVisible();
  await expect(nav.getByRole("link", { name: /Audit/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /Provider status/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /Support/ })).toHaveCount(0);   // no support.read: no Support entry
});

test("candidate is denied the admin area", async ({ page }) => {
  await mockAdmin(page, "user", []);
  await page.goto("/admin");
  await expect(page.getByText(/not available|access/i).first()).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Admin" })).toHaveCount(0);
  await expect(page.getByText("abc1234")).toHaveCount(0);
});

test("unauthenticated access to admin is redirected to sign-in", async ({ page }) => {
  await mockAdmin(page, "user", [], false);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/sign-in/);
});
