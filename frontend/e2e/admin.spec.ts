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
  "platform.billing.read", "platform.billing.refund", "platform.plans.price.change",
  "platform.ai.manage", "platform.ai.activate",
];

let currentUid = 1;
function account(role: string, perms: string[]) {
  return {
    user_id: currentUid, email: "u@example.com", display_name: null, platform_role: role,
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
// Stateful stand-in for the governed AI configuration lifecycle. The test plays the W10.9 worker by calling ai.worker(); the real lifecycle (worker,
// resolver, hash binding, second approver, rollback) is proven by tests/test_ai_admin_w10_7.py. No live model is involved anywhere.
const AI_ID = "c".repeat(32);
const AI_APPROVAL = "e".repeat(32);
const AI_PROFILES = { fast: "luna", balanced: "terra", advanced: "sol" };
const ai = {
  created: false, state: "draft", retries: 2, evalQueued: false, approvalRequested: false, staging: false, production: false, stagingEver: false, reverted: false,
  worker() { if (this.evalQueued) { this.evalQueued = false; this.state = "evaluated"; } },
  hash() { return (this.retries === 2 ? "a" : "b").repeat(64); },
  summary() { return { public_id: AI_ID, version: 1, name: "Lower retries", notes: "", state: this.state, content_hash: this.hash(), catalogue_version: "2026-10-04.1",
    created_by_email: "first@example.com", created_by_user_id: 1, created_at: null, validated_at: null, retired_at: null,
    active_in: [this.staging ? "staging" : "", this.production ? "production" : ""].filter(Boolean) }; },
  detail() {
    const ops = { orchestration: { max_output_tokens: 1536, timeout_s: 60, max_retries: this.retries }, final_response: { max_output_tokens: 1536, timeout_s: 60, max_retries: 2 } };
    return { ...this.summary(), settings: { profiles: AI_PROFILES, operations: ops }, validation: this.state === "draft" ? [] : [{ code: "tunable_bounds", label: "Every tunable is inside its code-defined bounds", passed: true, detail: "" }],
      validation_passed: this.state !== "draft", changed_from_baseline: this.retries === 2 ? [] : [{ field: "operation.orchestration.max_retries", baseline: 2, value: this.retries }],
      evaluations: this.state === "evaluated" || this.state === "approved" ? [{ public_id: "d".repeat(32), content_hash: this.hash(), evaluator_version: "ai-eval-1", status: "passed",
        checks: [{ code: "resolution_matrix", label: "All 24 operation x profile resolutions hold their invariants", passed: true, detail: "" }], summary: {}, live_calls: 0, failure_category: null, created_at: null, finished_at: null }]
        : this.evalQueued ? [{ public_id: "d".repeat(32), content_hash: this.hash(), evaluator_version: "ai-eval-1", status: "queued", checks: [], summary: {}, live_calls: 0, failure_category: null, created_at: null, finished_at: null }] : [],
      approvals: this.approvalRequested ? [{ public_id: AI_APPROVAL, version_ref: AI_ID, content_hash: this.hash(), status: this.state === "approved" ? "approved" : "pending",
        requested_by_email: "first@example.com", requested_at: null, decided_by_email: this.state === "approved" ? "second@example.com" : null, decided_at: null, reason: "ready" }] : [],
      activations: [this.stagingEver ? { public_id: "f".repeat(32), environment: "staging", kind: "activate", version_ref: AI_ID, version: 1, content_hash: this.hash(), activated_by_email: "second@example.com", activated_at: null, deactivated_at: null, reason: "go", open: this.staging } : null].filter(Boolean),
      latest_evaluation_passed: this.state === "evaluated" || this.state === "approved" };
  },
  governedIn(env: string) { return !this.reverted && (env === "staging" ? this.staging : this.production); },
  runtime() {
    const gov = this.staging;
    return { environment: "staging", mode: gov ? "governed" : "code_defaults", active_version: gov ? 1 : null, content_hash: gov ? this.hash() : null, fallback_reason: null,
      profiles: Object.fromEntries(Object.entries(AI_PROFILES).map(([p, c]) => [p, { catalogue_id: c, provider_slug: `x/${c}`, source: gov ? "governed_configuration" : "code_default" }])),
      operations: [], realtime: { capability: "realtime", chat_slug: null, governed: false }, note: "Realtime voice, deterministic operations, the three specialists and the Interview session profile are code-defined and unaffected." };
  },
};
// Stateful stand-in for MOCK billing. The test plays the W10.9 worker by calling bill.worker(); the real lifecycle (worker, provider, replay) is proven by
// tests/test_billing_w10_5.py. Entitlements are untouched by every step (asserted through the candidate-visible plan stub).
const bill = {
  configured: false, priceApproved: false, refundState: "none" as "none" | "pending" | "approved" | "executed", entitlements: ["standard_history"],
  worker() { if (this.refundState === "approved") this.refundState = "executed"; },
  mode: { provider: "mock", enabled: true, live: false, mode: "mock", label: "MOCK BILLING - NOT LIVE BILLING", configuration_error: null, checkout: false, note: "No live payments are processed." },
  terms() {
    const cur = this.priceApproved ? { public_id: "t".repeat(32), version: 1, amount_minor: 1099, currency: "EUR", interval: "month", trial_days: null, visibility: "internal", state: "active", activated_at: null, retired_at: null, approval_id: null } : null;
    return { items: [{ plan_version_id: 3, plan_code: "premium", plan_version: 1, plan_name: "Premium (preview)", plan_status: "active", current: cur, configured: !!cur,
      history: cur ? [cur] : [], pending_approval_id: this.configured && !this.priceApproved ? "p".repeat(32) : null }], note: "n" };
  },
  approvals() {
    const out: unknown[] = [];
    if (this.configured) out.push({ public_id: "p".repeat(32), action_type: "price_change", target_ref: "plan_version:3", proposed: { plan_version_id: 3, amount_minor: 1099, currency: "EUR" },
      reason: "Initial test terms", status: this.priceApproved ? "executed" : "pending", requested_by_user_id: 1, requested_by_email: "u@example.com", requested_at: null,
      decided_by_user_id: this.priceApproved ? 2 : null, decided_at: null, executed_at: null, execution_ref: null, failure_category: null });
    if (this.refundState !== "none") out.push({ public_id: "r".repeat(32), action_type: "refund", target_ref: "payment:1", proposed: { amount_minor: 500, currency: "EUR" }, reason: "Duplicate",
      status: this.refundState === "pending" ? "pending" : this.refundState, requested_by_user_id: 1, requested_by_email: "u@example.com", requested_at: null,
      decided_by_user_id: this.refundState === "pending" ? null : 2, decided_at: null, executed_at: null, execution_ref: null, failure_category: null });
    return out;
  },
  payment() {
    const refunded = this.refundState === "executed" ? 500 : 0;
    return { public_id: "q".repeat(32), provider: "mock", provider_payment_id: "pay_1", mock: true, invoice_public_id: "i", amount_minor: 2000, currency: "EUR", status: "succeeded",
      failure_category: null, refunded_minor: refunded, refundable_minor: 2000 - refunded - (this.refundState === "approved" ? 500 : 0), created_at: null };
  },
};
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
    if (path.endsWith("/admin/ai/catalogue")) return json({ version: "2026-10-04.1", note: "The approved catalogue is defined in code.", items: ["luna", "terra", "sol"].map((id, i) => ({ id, display_name: `${id[0].toUpperCase()}${id.slice(1)} entry`, tier: ["fast", "balanced", "advanced"][i], allowed_profiles: ["balanced"], provider_slug: `x/${id}`, supports_tools: true, supports_structured_output: true, supports_temperature: false, cost_class: i + 1, note: "" })) });
    if (path.endsWith("/admin/ai/code-defined")) return json({ operations: [{ operation: "orchestration", capability: "tool_calling", min_capability: "balanced", fallback_floor: "balanced", structured_output: false, requires_tools: true, tunable: true, deterministic: false, realtime: false, code_values: {} },
      { operation: "specialist_evidence_analysis", capability: "none", min_capability: "fast", fallback_floor: "fast", structured_output: false, requires_tools: false, tunable: false, deterministic: true, realtime: false, code_values: {} }], tunable_fields: {}, note: "Code-defined." });
    if (path.endsWith("/admin/ai/runtime")) return json(ai.runtime());
    if (path.endsWith("/admin/ai/environments")) return json({ note: "With nothing active an environment uses the code-defined registry.", this_environment: "staging", items: ["staging"].map((env) => ({ environment: env, mode: ai.governedIn(env) ? "governed" : "code_defaults",
      active: ai.governedIn(env) ? { public_id: "f".repeat(32), environment: env, kind: "activate", version_ref: AI_ID, version: 1, content_hash: ai.hash(), activated_by_email: "second@example.com", activated_at: null, deactivated_at: null, reason: "go", open: true } : null,
      version: ai.governedIn(env) ? ai.summary() : null, profiles: ai.runtime().profiles })) });
    if (path.endsWith("/admin/ai/history")) return json({ items: ai.stagingEver ? [{ public_id: "f".repeat(32), environment: "staging", kind: ai.reverted ? "revert_to_code" : "activate", version_ref: ai.reverted ? null : AI_ID, version: ai.reverted ? null : 1, content_hash: null, activated_by_email: "second@example.com", activated_at: null, deactivated_at: null, reason: "go", open: true }] : [], total: 1, page: 1, page_size: 50 });
    if (path.endsWith("/admin/ai/approvals")) return json({ items: ai.approvalRequested ? ai.detail().approvals : [], total: ai.approvalRequested ? 1 : 0, page: 1, page_size: 50 });
    if (/\/admin\/ai\/approvals\/[^/]+\/approve$/.test(path) && method === "POST") { ai.state = "approved"; return json(ai.detail().approvals[0]); }
    if (/\/admin\/ai\/configs\/[^/]+\/validate$/.test(path) && method === "POST") { ai.state = "validated"; return json(ai.detail()); }
    if (/\/admin\/ai\/configs\/[^/]+\/evaluate$/.test(path) && method === "POST") { ai.evalQueued = true; return json(ai.detail().evaluations[0], 202); }
    if (/\/admin\/ai\/configs\/[^/]+\/request-approval$/.test(path) && method === "POST") { ai.approvalRequested = true; return json(ai.detail().approvals[0], 201); }
    if (/\/admin\/ai\/configs\/[^/]+\/activate$/.test(path) && method === "POST") {
      ai.staging = true; ai.stagingEver = true; ai.reverted = false;                                      // the server decides the environment
      return json({ public_id: "f".repeat(32), environment: "staging", kind: "activate", version_ref: AI_ID, version: 1, content_hash: ai.hash(), activated_by_email: "second@example.com", activated_at: null, deactivated_at: null, reason: "go", open: true }, 201);
    }
    if (path.endsWith("/admin/ai/rollback") && method === "POST") { ai.staging = false; ai.production = false; ai.reverted = true;
      return json({ public_id: "g".repeat(32), environment: "staging", kind: "revert_to_code", version_ref: null, version: null, content_hash: null, activated_by_email: "second@example.com", activated_at: null, deactivated_at: null, reason: "off", open: true }, 201); }
    if (/\/admin\/ai\/configs\/[^/]+$/.test(path) && method === "PATCH") { const b = JSON.parse(route.request().postData() ?? "{}"); ai.retries = b.settings?.operations?.orchestration?.max_retries ?? ai.retries; return json(ai.detail()); }
    if (/\/admin\/ai\/configs\/[^/]+$/.test(path)) return json(ai.detail());
    if (path.endsWith("/admin/ai/configs") && method === "POST") { ai.created = true; return json(ai.detail(), 201); }
    if (path.endsWith("/admin/ai/configs")) return json({ items: ai.created ? [ai.summary()] : [], total: ai.created ? 1 : 0, page: 1, page_size: 50 });
    if (path.endsWith("/admin/ai")) return json({ stats: { versions: ai.created ? 1 : 0, by_state: {}, pending_approvals: 0, active: { staging: ai.staging, production: ai.production } }, runtime: ai.runtime(), catalogue_version: "2026-10-04.1" });
    if (path.endsWith("/admin/billing") && method === "GET") return json({ mode: bill.mode, stats: { mock: true, label: bill.mode.label, open_invoices: 0, past_due_invoices: 1, failed_payments: 1, pending_approvals: 0, configured_plan_versions: bill.priceApproved ? 1 : 0 }, terms: bill.terms() });
    if (path.endsWith("/admin/billing/price-changes") && method === "POST") { bill.configured = true; return json(bill.approvals()[0], 201); }
    if (/\/admin\/billing\/price-changes\/[^/]+\/approve$/.test(path) && method === "POST") { bill.priceApproved = true; return json(bill.approvals()[0]); }
    if (/\/admin\/billing\/payments\/[^/]+\/refunds$/.test(path) && method === "POST") { bill.refundState = "pending"; return json(bill.approvals().slice(-1)[0], 201); }
    if (/\/admin\/billing\/refunds\/[^/]+\/approve$/.test(path) && method === "POST") { bill.refundState = "approved"; return json(bill.approvals().slice(-1)[0]); }
    if (path.endsWith("/admin/billing/approvals")) return json({ items: bill.approvals(), total: bill.approvals().length, page: 1, page_size: 50 });
    if (path.endsWith("/admin/billing/invoices")) return json({ items: [{ public_id: "i".repeat(32), provider: "mock", provider_invoice_id: "inv_1", mock: true, state: "past_due", amount_due_minor: 2000, amount_paid_minor: 0,
      currency: "EUR", subject: { type: "user", id: 5, label: "cand@example.com" }, period_start: null, period_end: null, due_at: null, created_at: null }], total: 1, page: 1, page_size: 25 });
    if (path.endsWith("/admin/billing/payments")) return json({ items: [bill.payment(), { ...bill.payment(), public_id: "z".repeat(32), provider_payment_id: "pay_f", status: "failed", failure_category: "declined", refunded_minor: 0, refundable_minor: 0 }], total: 2, page: 1, page_size: 25 });
    if (path.endsWith("/admin/billing/refunds")) return json({ items: bill.refundState === "executed" ? [{ public_id: "x", provider: "mock", provider_refund_id: "mock_re_1", mock: true, payment_public_id: "q".repeat(32), amount_minor: 500, currency: "EUR", state: "succeeded", created_at: null, executed_at: null }] : [], total: bill.refundState === "executed" ? 1 : 0, page: 1, page_size: 50 });
    if (path.endsWith("/admin/billing/customers")) return json({ items: [], total: 0, page: 1, page_size: 50 });
    if (path.endsWith("/auth/plan")) return json({ ...MY_PLAN, entitlements: MY_PLAN.entitlements });
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
  for (const label of ["Overview", "Users", "Workspaces", "Review / Diagnostics", "Audit", "Provider status", "Jobs", "Knowledge", "Privacy", "Legal", "Billing", "AI and models"]) {
    await expect(nav.getByRole("link", { name: new RegExp(label) })).toBeVisible();
  }
  for (const future of ["Subscriptions", "Incidents", "Feature Flags"]) {
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

test("W10.5: mock billing: MOCK banner, terms request, no self-approval, second admin approves, entitlements unchanged, refund request, second approval, worker executes", async ({ page }) => {
  bill.configured = false; bill.priceApproved = false; bill.refundState = "none";
  currentUid = 1;
  await mockAdmin(page, "billing_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: /^Billing/ }).click();
  await expect(page.getByRole("heading", { name: "MOCK BILLING — NOT LIVE BILLING" })).toBeVisible();
  await expect(page.getByText(/No live payments are processed/).first()).toBeVisible();
  await expect(page.getByText("MOCK inv_1")).toBeVisible();
  await expect(page.getByText("MOCK pay_f")).toBeVisible();
  await expect(page.getByText(/Not configured \(this is not free\)/)).toBeVisible();
  await expect(page.getByRole("button", { name: /buy|subscribe|checkout/i })).toHaveCount(0);

  await page.getByRole("button", { name: /Propose mock terms for Premium/ }).click();
  await page.getByLabel(/Amount in minor units/).fill("1099");
  await page.getByLabel("Reason").fill("Initial test terms");
  await page.getByRole("button", { name: "Request approval" }).click();
  await expect(page.getByText(/A different administrator must approve it/)).toBeVisible();
  await expect(page.getByText("A second approver is required")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);                      // the requester cannot self-approve

  await page.unroute("**/api/v1/**");
  currentUid = 2;                                                                                  // a different qualified administrator
  await mockAdmin(page, "billing_admin", ADMIN_PERMS);
  await page.goto("/admin/billing");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/New mock commercial terms are active/)).toBeVisible();
  await expect(page.getByText("10.99 EUR per month")).toBeVisible();

  await page.unroute("**/api/v1/**");
  currentUid = 1;
  await mockAdmin(page, "billing_admin", ADMIN_PERMS);
  await page.goto("/admin/billing");
  await page.getByRole("button", { name: /Request a mock refund for pay_1/ }).click();
  await expect(page.getByText(/Mock refund — no real money moves\./).first()).toBeVisible();
  await page.getByLabel(/Refund amount in minor units/).fill("500");
  await page.getByLabel("Reason").fill("Duplicate");
  await page.getByRole("button", { name: "Request approval" }).click();
  await expect(page.getByText("A second approver is required")).toBeVisible();

  await page.unroute("**/api/v1/**");
  currentUid = 2;
  await mockAdmin(page, "billing_admin", ADMIN_PERMS);
  await page.goto("/admin/billing");
  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/Mock refund approved and queued/)).toBeVisible();
  bill.worker();                                                                                    // the W10.9 worker executes the approved refund
  await page.reload();
  await expect(page.getByText(/MOCK refund of 5.00 EUR/)).toBeVisible();
  await expect(page.getByText("Executed").first()).toBeVisible();
  expect(bill.entitlements).toEqual(["standard_history"]);                                         // billing never touched access

  await page.unroute("**/api/v1/**");
  currentUid = 1;
  await mockAdmin(page, "platform_admin", ["platform.overview.read", "platform.billing.read"]);
  await page.goto("/admin/billing");
  await expect(page.getByRole("heading", { name: "MOCK BILLING — NOT LIVE BILLING" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Propose|refund|Approve|Reject/i })).toHaveCount(0);
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

test("W10.7: AI administration: code defaults, draft, validate, evaluate (worker), no self-approval, second admin approves, this server's environment only, rollback", async ({ page }) => {
  Object.assign(ai, { created: false, state: "draft", retries: 2, evalQueued: false, approvalRequested: false, staging: false, production: false, stagingEver: false, reverted: false });
  currentUid = 1;
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto("/admin");
  await page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: /^AI and models/ }).click();
  await expect(page.getByRole("heading", { name: "Governed configuration, no live model calls" })).toBeVisible();
  await expect(page.getByText("Code defaults").first()).toBeVisible();
  await expect(page.getByLabel(/model name|provider|slug/i)).toHaveCount(0);                      // no raw provider-name input exists
  await expect(page.getByText("No (deterministic, no model)")).toBeVisible();                       // deterministic operations are listed as not configurable

  await page.getByLabel("Name").fill("Lower retries");
  await page.getByRole("button", { name: "Create draft" }).click();
  await expect(page.getByText(/Draft version 1 created/)).toBeVisible();
  await page.getByRole("link", { name: "Lower retries" }).click();
  await expect(page.getByRole("heading", { name: "Edit draft" })).toBeVisible();
  await page.getByLabel("orchestration Max retries").fill("1");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Draft saved.")).toBeVisible();
  await expect(page.getByText(/operation orchestration max retries/)).toBeVisible();

  await page.getByRole("button", { name: "Validate" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Validate" }).click();
  await expect(page.getByText("Validation finished.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Settings (frozen)" })).toBeVisible();
  await page.getByRole("button", { name: "Evaluate" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Queue evaluation" }).click();
  await expect(page.getByText(/Evaluation queued/)).toBeVisible();
  ai.worker();                                                                                       // the W10.9 worker evaluates the exact hash
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText(/matches this content/)).toBeVisible();
  await expect(page.getByText(/live calls: 0/)).toBeVisible();
  await page.getByRole("button", { name: "Submit for approval" }).click();
  await page.getByRole("alertdialog").getByLabel(/Reason/).fill("Reviewed");
  await page.getByRole("alertdialog").getByRole("button", { name: "Submit for approval" }).click();
  await expect(page.getByText(/must decide this request/)).toBeVisible();                           // the requester cannot self-approve
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Activate in/ })).toHaveCount(0);

  await page.unroute("**/api/v1/**");
  currentUid = 2;                                                                                    // a different qualified administrator
  await mockAdmin(page, "platform_admin", ADMIN_PERMS);
  await page.goto(`/admin/ai/${AI_ID}`);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve" }).click();               // a reason is required
  await expect(page.getByRole("alertdialog").getByText("A reason is required.")).toBeVisible();
  await page.getByRole("alertdialog").getByLabel(/Reason/).fill("Looks right");
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/Approved\. It is not active/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Activate in production/ })).toHaveCount(0);        // this server is staging; the browser cannot target production
  await expect(page.getByRole("combobox", { name: /environment/i })).toHaveCount(0);
  await page.getByRole("button", { name: "Activate in staging" }).click();
  await page.getByRole("alertdialog").getByLabel(/Reason/).fill("Roll out to staging");
  await page.getByRole("alertdialog").getByRole("button", { name: "Activate", exact: true }).click();
  await expect(page.getByText("Active in staging.")).toBeVisible();

  await page.goto("/admin/ai");
  await expect(page.getByText("Governed configuration", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Version 1").first()).toBeVisible();
  await page.getByRole("button", { name: "Revert staging to code defaults" }).click();
  await page.getByRole("alertdialog").getByLabel(/Reason/).fill("Back to code");
  await page.getByRole("alertdialog").getByRole("button", { name: "Revert to code defaults" }).click();
  await expect(page.getByText(/staging now uses the code-defined defaults/)).toBeVisible();
  await expect(page.getByText("Code defaults").first()).toBeVisible();

  await page.unroute("**/api/v1/**");
  await mockAdmin(page, "operations_admin", ["platform.overview.read", "platform.ai.read"]);        // read-only role: no write controls
  await page.goto("/admin/ai");
  await expect(page.getByRole("button", { name: "Create draft" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Roll back|Revert/ })).toHaveCount(0);
});
