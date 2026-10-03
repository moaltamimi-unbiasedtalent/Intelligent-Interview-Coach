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
  privacy_requests: { status: string; note: string };
  accounts: Record<string, number>;
  workspaces: Record<string, number>;
  plans?: { by_plan: Record<string, { users: number; workspaces: number }>; accounts_without_subscription: number };
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
