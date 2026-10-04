/** Hand-written admin response contracts (W10.1). Mirrors the backend allowlist schemas. */
export interface AdminBuildInfo {
  version: string;
  git_sha: string;
  build_time: string;
  environment: string;
  source: string;
}
export interface AdminMigrationStatus {
  repository_head: string | null;
  database_revision: string | null;
  state: "match" | "mismatch" | "unknown";
  warning: string | null;
}
export interface AdminCommandCenter {
  build: AdminBuildInfo;
  migrations: AdminMigrationStatus;
  health: { database: string; providers_probed: boolean; note: string };
  rate_limit: { mode: string; distributed: boolean; shared_store_requested: boolean; note: string };
  pause: { paused: Record<string, boolean>; durable: boolean; note: string };
  privacy_requests: { status: string; note: string; open?: number; submitted?: number; in_progress?: number; waiting_for_user?: number; unassigned_open?: number; completed?: number; total?: number; oldest_open_at?: string | null };
  accounts: Record<string, number>;
  workspaces: Record<string, number>;
  plans?: { by_plan: Record<string, { users: number; workspaces: number }>; accounts_without_subscription: number };
  integrations?: { total: number; configured: number; runtime_active: number; not_tested: number; unhealthy: number };
  jobs?: JobDiagnostics;
  billing?: { mock: boolean; label: string; open_invoices: number; past_due_invoices: number; failed_payments: number; pending_approvals: number; configured_plan_versions: number };
  ai?: { versions: number; by_state: Record<string, number>; pending_approvals: number; active: Record<string, boolean> };
  knowledge?: { sources: number; awaiting_review: number; indexing: number; failed: number; indexed_not_active: number; active: number };
  support?: { open: number; unassigned: number; waiting_for_customer: number; high_or_urgent: number; total: number };
  diagnostics_links: { label: string; path: string }[];
  boundary: string;
}
export interface AdminProviderRow {
  provider_id: string;
  label: string;
  configured: boolean;
  enabled: boolean;
  externally_managed: boolean;
  writable: boolean;
  status: "not_configured" | "configured_health_not_tested" | "internal";
  health: string;
  live_validation: string;
  mode: string | null;
}
export interface AdminProviders {
  providers: AdminProviderRow[];
  speech: Record<string, unknown>;
  ocr: { engine: string; available: boolean; pdf_ocr_available: boolean; poppler_available: boolean; live_quality: string };
  pause: Record<string, boolean>;
  pause_durable: boolean;
  rate_limit_mode: string;
  rate_limit_distributed: boolean;
  note: string;
}
export interface AdminAuditEvent {
  event_type: string;
  result: string;
  actor_user_id: number | null;
  target_type: string | null;
  target_id: string | null;
  request_id: string | null;
  context: Record<string, unknown> | null;
  created_at: string | null;
}

// --- W10.2: users, sessions, workspaces (allowlist contracts; metadata only) ---
export interface AdminUserSummary {
  user_id: number;
  email: string | null;
  display_name: string | null;
  status: string;
  platform_role: string;
  tier: string;
  onboarding_completed: boolean;
  interface_locale: string;
  email_verified: boolean;
  created_at: string | null;
  updated_at: string | null;
  workspace_count: number;
  active_session_count: number;
}
export interface AdminPage<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface AdminUserDetail {
  account: AdminUserSummary;
  access: { platform_role: string; capabilities: string[]; assignable_roles: string[]; is_self: boolean };
  sessions: { active_count: number; recent: { created_at: string | null; last_used_at: string | null; expires_at: string | null }[] };
  workspaces: { workspace_id: number; name: string; workspace_status: string; role: string; membership_status: string; joined_at: string | null }[];
  audit: AdminAuditEntry[];
  plan?: SubjectPlan | null;
}
export interface AdminAuditEntry {
  event_type: string;
  result: string;
  actor_user_id: number | null;
  request_id: string | null;
  created_at: string | null;
  context: Record<string, string | number | boolean | null> | null;
}
export interface AdminWorkspaceSummary {
  id: number;
  name: string;
  status: string;
  owner_user_id: number;
  owner_email: string | null;
  member_count: number;
  created_at: string | null;
}
export interface AdminWorkspaceDetail {
  workspace: AdminWorkspaceSummary;
  members: { user_id: number; email: string | null; account_status: string; role: string; membership_status: string; joined_at: string | null }[];
  active_share_count: number;
  active_owner_count: number;
  workspace_roles: string[];
  plan?: SubjectPlan | null;
}
export interface AdminUserQuery {
  q?: string;
  status?: string;
  role?: string;
  tier?: string;
  onboarding?: string;
  email_verified?: string;
  page?: number;
  page_size?: number;
}

// --- W10.3 support (Admin side) ---
export interface AdminTicketSummary {
  id: number;
  public_id: string;
  owner_user_id: number;
  owner_email: string | null;
  category: string;
  priority: string;
  status: string;
  subject: string;
  assigned_user_id: number | null;
  assignee_email: string | null;
  message_count: number;
  created_at: string | null;
  updated_at: string | null;
}
export interface AdminTicketDetail {
  ticket: AdminTicketSummary & {
    initial_request_id: string | null;
    source_route: string | null;
    source_environment: string | null;
    resolved_at: string | null;
    closed_at: string | null;
    allowed_statuses: string[];
  };
  messages: { id: number; author_kind: string; author_user_id: number | null; body: string; request_id: string | null; created_at: string | null }[];
  internal_notes: { id: number; author_user_id: number | null; body: string; request_id: string | null; created_at: string | null }[];
  account: AdminUserSummary | null;
  priorities: string[];
  statuses: string[];
}
export interface AdminAssignee {
  user_id: number;
  email: string | null;
  platform_role: string;
}
export interface AdminTicketQuery {
  q?: string;
  status?: string;
  category?: string;
  priority?: string;
  assignee?: string;
  page?: number;
  page_size?: number;
}

// --- W10.4 plans, subscriptions, entitlements (no price, no payment state) ---
export interface PlanVersionRow {
  id: number;
  plan_code: string;
  version: number;
  display_name: string;
  status: "draft" | "active" | "retired";
  enabled_entitlements: number;
  total_entitlements: number;
  subscribers: { users: number; workspaces: number };
  created_at: string | null;
  activated_at: string | null;
  retired_at: string | null;
}
export interface EntitlementRow {
  code: string;
  label: string;
  description: string;
  type: string;
  enabled: boolean;
  limit: number | null;
}
export interface PlanDetail extends Omit<PlanVersionRow, "enabled_entitlements" | "total_entitlements"> {
  editable: boolean;
  entitlements: EntitlementRow[];
}
export interface AssignablePlan {
  plan_code: string;
  version: number;
  display_name: string;
}
export interface SubscriptionEntry {
  plan_code: string;
  version: number;
  display_name: string;
  status: string;
  source: string;
  started_at: string | null;
  ended_at: string | null;
}
export interface SubjectPlan {
  current: SubscriptionEntry | null;
  history: SubscriptionEntry[];
}

// --- W10.6 integrations (metadata only: no secret value, prefix, suffix, mask, URL or upstream response) ---
export interface CredentialStatus {
  slot: string;
  label: string;
  external_name: string;
  configured: boolean;
  source: string;
  writable: boolean;
}
export interface IntegrationRow {
  code: string;
  name: string;
  category: string;
  category_label: string;
  adapter: string;
  description: string;
  classification: string;
  configuration_status: string;
  slots: CredentialStatus[];
  settings: { code: string; label: string; selected: string | null }[];
  runtime: { enabled: boolean | null; managed: string; toggle_supported: boolean; note: string };
  store: { name: string; writable: boolean };
  health: { status: "not_tested" | "healthy" | "unhealthy"; last_tested_at: string | null; category: string | null; latency_ms: number | null };
  test: { supported: boolean; note: string };
  validation_note: string;
}
export interface IntegrationDetail extends IntegrationRow {
  audit: AdminAuditEntry[];
}
export interface IntegrationTestResult {
  integration: string;
  outcome: string;
  category: string;
  latency_ms: number | null;
}

// --- W10.9 jobs (operational metadata only: no raw payload, error body, secret or candidate data) ---
export type JobState = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export interface JobRow {
  public_id: string;
  job_type: string;
  type_label: string;
  state: JobState;
  priority: string;
  attempts: number;
  max_attempts: number;
  manual_retries: number;
  available_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_category: string | null;
  error_message: string | null;
  lease: { held: boolean; owner: string | null; expires_at: string | null; heartbeat_at: string | null; stale: boolean };
  waiting_for_retry: boolean;
  payload_summary: Record<string, string>;
  can_retry: boolean;
  can_cancel: boolean;
}
export interface JobDetail extends JobRow {
  audit: AdminAuditEntry[];
}
export interface JobQuery {
  state?: string;
  job_type?: string;
  priority?: string;
  q?: string;
  page?: number;
  page_size?: number;
}
export interface JobDiagnostics {
  queue: {
    queued: number; running: number; failed: number; succeeded: number; cancelled: number;
    retry_waiting: number; stale_leases: number; oldest_ready_age_seconds: number | null;
  };
  by_type: ({ job_type: string; label: string } & Record<JobState, number>)[];
  workers: {
    seen_recently: number; last_seen_at: string | null; stale_after_seconds: number;
    items: { worker_id: string; status: string; started_at: string | null; last_seen_at: string | null; jobs_succeeded: number; jobs_failed: number; active: boolean }[];
  };
}
export interface JobTypeInfo {
  job_type: string;
  label: string;
  max_attempts: number;
  manual_retry: boolean;
  cancellable_when_queued: boolean;
  idempotency: string;
}

// --- W10.8 knowledge (governance metadata only; a bounded preview is the only content view) ---
export interface KnowledgeRow {
  source_public_id: string;
  title: string;
  version_public_id: string;
  version: number;
  state: string;
  active: boolean;
  language: string;
  authority_level: number;
  authority_meaning: string;
  publisher: string;
  licence_class: string;
  licence_label: string;
  scan_status: string;
  chunk_count: number | null;
  failure_category: string | null;
  created_at: string | null;
  updated_at: string | null;
}
export interface KnowledgeSourceDetail {
  source_public_id: string;
  title: string;
  created_at: string | null;
  versions: KnowledgeRow[];
}
export interface KnowledgeVersionDetail extends KnowledgeRow {
  source_reference: string | null;
  provenance_note: string;
  original_filename: string;
  media_type: string;
  byte_size: number;
  checksum_sha256: string;
  scanner: string | null;
  extracted_chars: number | null;
  preview: string | null;
  preview_is_truncated: boolean;
  failed_stage: string | null;
  rejection_reason: string | null;
  approved_at: string | null;
  approved_by_user_id: number | null;
  indexed_at: string | null;
  activated_at: string | null;
  retired_at: string | null;
  parse_job_id: string | null;
  index_job_id: string | null;
  index: { state: string; chunk_count: number; embedder: string; collection: string; built_at: string | null } | null;
  blockers: string[];
  metadata_frozen: boolean;
  can: { edit: boolean; approve: boolean; reject: boolean; index: boolean; activate: boolean; retire: boolean; reprocess: boolean; delete: boolean };
  audit: AdminAuditEntry[];
}
export interface KnowledgeMeta {
  languages: string[];
  authority_levels: { level: number; meaning: string }[];
  licence_classes: { code: string; label: string; activatable: boolean }[];
  states: string[];
  rejection_reasons: string[];
  upload: { max_bytes: number; extensions: string[]; preview_chars: number };
}
export interface KnowledgeQuery {
  state?: string;
  language?: string;
  authority?: string;
  licence?: string;
  active?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

// --- W10.10 privacy and legal administration (safe operational metadata; no candidate content, no exports, no IP/device) ---
export interface PrivacyRequestRow {
  public_id: string;
  request_type: string;
  type_label: string;
  status: string;
  result_category: string | null;
  created_at: string | null;
  updated_at: string | null;
  source: string;
  user_id: number | null;
  candidate_email: string | null;
  assigned_user_id: number | null;
  assignee_email: string | null;
  acknowledged_at: string | null;
  completed_at: string | null;
  closed_at: string | null;
  related_job_id: string | null;
}
export interface PrivacyRequestDetail extends PrivacyRequestRow {
  request_note: string | null;
  candidate: { user_id: number; email: string | null; status: string; platform_role: string; created_at: string | null } | null;
  allowed_statuses: string[];
  result_categories: string[];
  can_execute_deletion: boolean;
  legal: { document: string; current_version: string | null; accepted_current: boolean; last_accepted_at: string | null }[];
  audit: AdminAuditEntry[];
}
export interface PrivacyQuery {
  status?: string;
  request_type?: string;
  assignee?: string;
  q?: string;
  page?: number;
  page_size?: number;
}
export interface LegalVersionRow {
  id: number;
  version: string;
  state: string;
  is_baseline: boolean;
  content_ref: string;
  content_hash: string | null;
  effective_at: string | null;
  published_at: string | null;
  created_at: string | null;
  acceptances: number | null;
}
export interface LegalOverview {
  documents: { code: string; title: string; current: LegalVersionRow | null; versions: LegalVersionRow[]; current_accepted: number; current_not_recorded: number }[];
  active_accounts: number;
  note: string;
}
export interface PreparationCoverage {
  indexed_runs: number;
  by_state: Record<string, number>;
  by_source: Record<string, number>;
  coverage_version: number;
  note: string;
}

// --- W10.5 MOCK billing (metadata only; no card, payment-instrument, bank, tax or raw provider field) ---
export interface BillingMode {
  provider: string;
  enabled: boolean;
  live: boolean;
  mode: string;
  label: string;
  configuration_error: string | null;
  checkout: boolean;
  note: string;
}
export interface BillingTermsView {
  public_id: string;
  version: number;
  amount_minor: number;
  currency: string;
  interval: string;
  trial_days: number | null;
  visibility: string;
  state: string;
  activated_at: string | null;
  retired_at: string | null;
  approval_id: string | null;
}
export interface BillingPlanTerms {
  plan_version_id: number;
  plan_code: string;
  plan_version: number;
  plan_name: string;
  plan_status: string;
  current: BillingTermsView | null;
  configured: boolean;
  history: BillingTermsView[];
  pending_approval_id: string | null;
}
export interface BillingStats {
  mock: boolean;
  label: string;
  open_invoices: number;
  past_due_invoices: number;
  failed_payments: number;
  pending_approvals: number;
  configured_plan_versions: number;
}
export interface BillingOverview {
  mode: BillingMode;
  stats: BillingStats;
  terms: { items: BillingPlanTerms[]; note: string };
}
export interface BillingApproval {
  public_id: string;
  action_type: string;
  target_ref: string;
  proposed: Record<string, string | number | null>;
  reason: string;
  status: string;
  requested_by_user_id: number | null;
  requested_by_email: string | null;
  requested_at: string | null;
  decided_by_user_id: number | null;
  decided_at: string | null;
  executed_at: string | null;
  execution_ref: string | null;
  failure_category: string | null;
}
export interface BillingSubject {
  type: string;
  id: number | null;
  label: string | null;
}
export interface BillingInvoice {
  public_id: string;
  provider: string;
  provider_invoice_id: string;
  mock: boolean;
  state: string;
  amount_due_minor: number;
  amount_paid_minor: number;
  currency: string;
  subject: BillingSubject;
  period_start: string | null;
  period_end: string | null;
  due_at: string | null;
  created_at: string | null;
}
export interface BillingPayment {
  public_id: string;
  provider: string;
  provider_payment_id: string;
  mock: boolean;
  invoice_public_id: string;
  amount_minor: number;
  currency: string;
  status: string;
  failure_category: string | null;
  refunded_minor: number;
  refundable_minor: number;
  created_at: string | null;
}
export interface BillingRefund {
  public_id: string;
  provider: string;
  provider_refund_id: string | null;
  mock: boolean;
  payment_public_id: string;
  amount_minor: number;
  currency: string;
  state: string;
  created_at: string | null;
  executed_at: string | null;
}
export interface BillingCustomer {
  public_id: string;
  provider: string;
  provider_customer_id: string;
  mock: boolean;
  subject: BillingSubject;
  state: string;
  provider_subscriptions: { public_id: string; provider_subscription_id: string; provider_state: string; plan_version_id: number; current_period_end: string | null; grace_until: string | null }[];
}
export interface BillingPriceInput {
  plan_version_id: number;
  amount_minor: number;
  currency: string;
  interval: string;
  trial_days: number | null;
  visibility: string;
  reason: string;
}

// ---- W10.7 AI and model administration ------------------------------------------------------------------------------
export interface AICatalogueEntry {
  id: string; display_name: string; tier: string; allowed_profiles: string[]; provider_slug: string;
  supports_tools: boolean; supports_structured_output: boolean; supports_temperature: boolean; cost_class: number; note: string;
}
export interface AICatalogue { version: string; items: AICatalogueEntry[]; note: string }
export interface AICodeDefined {
  operations: { operation: string; capability: string; min_capability: string; fallback_floor: string; structured_output: boolean; requires_tools: boolean;
    tunable: boolean; no_runtime_path?: boolean; deterministic: boolean; realtime: boolean; code_values: Record<string, number> }[];
  tunable_fields: Record<string, { min: number; max: number }>;
  note: string;
}
export interface AIOperationTuning { max_output_tokens?: number; timeout_s?: number; max_retries?: number }
export interface AIConfigInput { profiles?: Record<string, string>; operations?: Record<string, AIOperationTuning> }
export interface AICheck { code: string; label: string; passed: boolean; detail: string }
export interface AIEvaluation {
  public_id: string; content_hash: string; evaluator_version: string; status: string; checks: AICheck[];
  summary: Record<string, unknown>; live_calls: number; failure_category: string | null; created_at: string | null; finished_at: string | null;
}
export interface AIApproval {
  public_id: string; version_ref: string | null; content_hash: string; status: string; requested_by_email: string | null;
  requested_at: string | null; decided_by_email: string | null; decided_at: string | null; reason: string;
}
export interface AIActivation {
  public_id: string; environment: string; kind: string; version_ref: string | null; version: number | null; content_hash: string | null;
  activated_by_email: string | null; activated_at: string | null; deactivated_at: string | null; reason: string; open: boolean;
}
export interface AIVersionSummary {
  public_id: string; version: number; name: string; notes: string; state: string; content_hash: string; catalogue_version: string;
  created_by_email: string | null; created_by_user_id: number | null; created_at: string | null; validated_at: string | null; retired_at: string | null; active_in: string[];
}
export interface AIVersionDetail extends AIVersionSummary {
  settings: { profiles: Record<string, string>; operations: Record<string, Record<string, number>> };
  validation: AICheck[]; validation_passed: boolean; changed_from_baseline: { field: string; baseline: string | number; value: string | number }[];
  evaluations: AIEvaluation[]; approvals: AIApproval[]; activations: AIActivation[]; latest_evaluation_passed: boolean;
}
export interface AIProfileResolution { catalogue_id: string | null; provider_slug: string; source: string }
export interface AIEnvironments { items: AIEnvironment[]; this_environment: string; note: string }
export interface AIEnvironment { environment: string; mode: string; active: AIActivation | null; version: AIVersionSummary | null; profiles: Record<string, AIProfileResolution> }
export interface AIRuntime {
  environment: string; mode: string; active_version: number | null; content_hash: string | null; fallback_reason: string | null;
  profiles: Record<string, AIProfileResolution>;
  operations: { operation: string; capability: string; uses_model: boolean; profile: string | null; provider_slug: string | null; max_output_tokens: number; timeout_s: number; max_retries: number }[];
  realtime: { capability: string; chat_slug: string | null; governed: boolean }; note: string;
}
export interface AIOverview { stats: { versions: number; by_state: Record<string, number>; pending_approvals: number; active: Record<string, boolean> }; runtime: AIRuntime; catalogue_version: string }
