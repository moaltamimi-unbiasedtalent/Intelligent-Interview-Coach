"""Allowlist response schemas for the admin surface (P10B-W10.1, SEC-W10-06).

Every field is explicit. There is no open-ended mapping pass-through, so a new environment variable or
config value can never leak into the response by accident; ``extra="forbid"`` guards construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


HEALTH_NOT_TESTED = "Health not tested"
ProviderState = Literal["not_configured", "configured_health_not_tested", "internal"]


class ProviderRow(_Strict):
    provider_id: str
    label: str
    configured: bool
    enabled: bool
    externally_managed: bool = True   # configured through deployment env, not by this console
    writable: bool = False            # the console cannot change provider configuration (AD-04)
    status: ProviderState
    health: str = HEALTH_NOT_TESTED   # configured is NOT healthy; no live call is made here
    live_validation: str = "UNVALIDATED"
    mode: str | None = None           # fixed vocabulary only (e.g. console/brevo)


class OcrLanguageStatus(_Strict):
    configured: bool
    runtime_available: bool


class OcrStatus(_Strict):
    engine: str
    available: bool
    pdf_ocr_available: bool
    poppler_available: bool
    languages: dict[str, OcrLanguageStatus]
    live_quality: str


class RealtimeStatus(_Strict):
    enabled: bool
    configured: bool
    available: bool
    max_session_seconds: int
    max_concurrent_per_user: int
    live_validation: str
    audio_visible_to_admin: bool = False
    transcript_visible_to_admin: bool = False


class SpeechStatus(_Strict):
    architecture: str
    input: str
    output: str
    camera: str
    audio_persisted_by_ask4mo: bool
    voice_trait_inference: str
    live_quality: str
    realtime: RealtimeStatus


class ProvidersResponse(_Strict):
    providers: list[ProviderRow]
    speech: SpeechStatus
    ocr: OcrStatus
    pause: dict[str, bool]
    pause_durable: bool = False
    rate_limit_mode: str
    rate_limit_distributed: bool
    note: str


# --- W10.2: users, sessions, workspaces (allowlist; metadata only) --------------------------------------
# No field here may carry candidate content (CV/document text, answers, report text, Mo conversations,
# memories, preparation chats, evidence) and none may carry a session token or its hash. A deterministic
# test and eval_admin_access.py introspect these models for banned names.

ScalarMeta = str | int | bool | None


class AdminUserSummary(_Strict):
    user_id: int
    email: str | None
    display_name: str | None
    status: str
    platform_role: str
    tier: str
    onboarding_completed: bool
    interface_locale: str
    email_verified: bool
    created_at: str | None
    updated_at: str | None
    workspace_count: int
    active_session_count: int


class AdminUserList(_Strict):
    items: list[AdminUserSummary]
    total: int
    page: int
    page_size: int
    users: list[AdminUserSummary] = []   # same page, kept for the pre-W10.2 response shape


class AdminSessionMeta(_Strict):
    created_at: str | None
    last_used_at: str | None
    expires_at: str | None


class AdminSessions(_Strict):
    active_count: int
    recent: list[AdminSessionMeta]


class AdminUserWorkspace(_Strict):
    workspace_id: int
    name: str
    workspace_status: str
    role: str
    membership_status: str
    joined_at: str | None


class AdminAuditEntry(_Strict):
    event_type: str
    result: str
    actor_user_id: int | None
    request_id: str | None
    created_at: str | None
    context: dict[str, ScalarMeta] | None


class AdminAccess(_Strict):
    platform_role: str
    capabilities: list[str]          # server-resolved from the code-defined preset
    assignable_roles: list[str]      # the code-defined presets an admin may select (never custom)
    is_self: bool


class AdminUserDetail(_Strict):
    account: AdminUserSummary
    access: AdminAccess
    sessions: AdminSessions
    workspaces: list[AdminUserWorkspace]
    audit: list[AdminAuditEntry]
    plan: "SubjectPlan | None" = None


class AdminWorkspaceSummary(_Strict):
    id: int
    name: str
    status: str
    owner_user_id: int
    owner_email: str | None
    member_count: int
    created_at: str | None


class AdminWorkspaceList(_Strict):
    items: list[AdminWorkspaceSummary]
    total: int
    page: int
    page_size: int
    workspaces: list[AdminWorkspaceSummary] = []


class AdminWorkspaceMember(_Strict):
    user_id: int
    email: str | None
    account_status: str
    role: str
    membership_status: str
    joined_at: str | None


class AdminWorkspaceDetail(_Strict):
    workspace: AdminWorkspaceSummary
    members: list[AdminWorkspaceMember]
    active_share_count: int
    active_owner_count: int
    workspace_roles: list[str]
    plan: "SubjectPlan | None" = None


# --- W10.3: support (Admin side). Metadata plus content the candidate deliberately submitted to Support.
class AdminTicketSummary(_Strict):
    id: int
    public_id: str
    owner_user_id: int
    owner_email: str | None
    category: str
    priority: str
    status: str
    subject: str
    assigned_user_id: int | None
    assignee_email: str | None
    message_count: int
    created_at: str | None
    updated_at: str | None


class AdminTicketPage(_Strict):
    items: list[AdminTicketSummary]
    total: int
    page: int
    page_size: int


class AdminTicketCore(AdminTicketSummary):
    initial_request_id: str | None
    source_route: str | None
    source_environment: str | None
    resolved_at: str | None
    closed_at: str | None
    allowed_statuses: list[str]


class AdminTicketMessage(_Strict):
    id: int
    author_kind: str
    author_user_id: int | None
    body: str
    request_id: str | None
    created_at: str | None


class AdminInternalNote(_Strict):
    id: int
    author_user_id: int | None
    body: str
    request_id: str | None
    created_at: str | None


class AdminTicketDetail(_Strict):
    ticket: AdminTicketCore
    messages: list[AdminTicketMessage]
    internal_notes: list[AdminInternalNote]
    account: AdminUserSummary | None
    priorities: list[str]
    statuses: list[str]


class AdminAssignee(_Strict):
    user_id: int
    email: str | None
    platform_role: str


# --- W10.4: plans, subscriptions, entitlements (no price, no payment state) ------------------------------
class Subscribers(_Strict):
    users: int
    workspaces: int


class PlanVersionRow(_Strict):
    id: int
    plan_code: str
    version: int
    display_name: str
    status: str
    enabled_entitlements: int
    total_entitlements: int
    subscribers: Subscribers
    created_at: str | None
    activated_at: str | None
    retired_at: str | None


class PlanList(_Strict):
    items: list[PlanVersionRow]


class EntitlementRow(_Strict):
    code: str
    label: str
    description: str
    type: str
    enabled: bool
    limit: int | None


class PlanDetail(_Strict):
    id: int
    plan_code: str
    version: int
    display_name: str
    status: str
    editable: bool
    entitlements: list[EntitlementRow]
    subscribers: Subscribers
    created_at: str | None
    activated_at: str | None
    retired_at: str | None


class AssignablePlan(_Strict):
    plan_code: str
    version: int
    display_name: str


class SubscriptionEntry(_Strict):
    plan_code: str
    version: int
    display_name: str
    status: str
    source: str
    started_at: str | None
    ended_at: str | None


class SubjectPlan(_Strict):
    current: SubscriptionEntry | None
    history: list[SubscriptionEntry]


AdminUserDetail.model_rebuild()
AdminWorkspaceDetail.model_rebuild()


# --- W10.6: integrations (metadata only: no secret value, prefix, suffix, mask, URL or upstream response) ---
class CredentialStatus(_Strict):
    slot: str
    label: str
    external_name: str      # the NAME of the environment variable the operator manages, never its value
    configured: bool
    source: str
    writable: bool


class SettingView(_Strict):
    code: str
    label: str
    selected: str | None    # an allowlisted vocabulary choice, "other", or null (never a free-form value)


class RuntimeView(_Strict):
    enabled: bool | None
    managed: str
    toggle_supported: bool
    note: str


class CredentialStoreView(_Strict):
    name: str
    writable: bool


class HealthView(_Strict):
    status: str             # not_tested | healthy | unhealthy (only an explicit manual test can set healthy)
    last_tested_at: str | None
    category: str | None
    latency_ms: int | None


class TestSupport(_Strict):
    supported: bool
    note: str


class IntegrationRow(_Strict):
    code: str
    name: str
    category: str
    category_label: str
    adapter: str
    description: str
    classification: str
    configuration_status: str
    slots: list[CredentialStatus]
    settings: list[SettingView]
    runtime: RuntimeView
    store: CredentialStoreView
    health: HealthView
    test: TestSupport
    validation_note: str


class IntegrationList(_Strict):
    items: list[IntegrationRow]


class IntegrationDetail(IntegrationRow):
    audit: list[AdminAuditEntry]


class IntegrationTestResult(_Strict):
    integration: str
    outcome: str
    category: str
    latency_ms: int | None


# ---- W10.9 jobs: safe projections only. No raw payload field exists; the type-defined summary is the only view. ----
class JobLease(_Strict):
    held: bool
    owner: str | None = None
    expires_at: str | None = None
    heartbeat_at: str | None = None
    stale: bool


class JobRow(_Strict):
    public_id: str
    job_type: str
    type_label: str
    state: str
    priority: str
    attempts: int
    max_attempts: int
    manual_retries: int
    available_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    lease: JobLease
    waiting_for_retry: bool
    payload_summary: dict[str, str]
    can_retry: bool
    can_cancel: bool


class JobList(_Strict):
    items: list[JobRow]
    total: int
    page: int
    page_size: int


class JobDetail(JobRow):
    audit: list[AdminAuditEntry]


class JobTypeInfo(_Strict):
    job_type: str
    label: str
    max_attempts: int
    manual_retry: bool
    cancellable_when_queued: bool
    idempotency: str


class JobEnqueueRequest(_Strict):
    job_type: str
    payload: dict[str, str]
    dedupe_id: str | None = None
    priority: str = "normal"


class JobEnqueueResult(_Strict):
    job: JobRow
    created: bool


# ---- W10.8 knowledge: governance metadata only. A bounded preview is the only content view; there is no full-text or chunk field. ----
class KnowledgeRow(_Strict):
    source_public_id: str
    title: str
    version_public_id: str
    version: int
    state: str
    active: bool
    language: str
    authority_level: int
    authority_meaning: str
    publisher: str
    licence_class: str
    licence_label: str
    scan_status: str
    chunk_count: int | None = None
    failure_category: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class KnowledgeList(_Strict):
    items: list[KnowledgeRow]
    total: int
    page: int
    page_size: int


class KnowledgeSourceDetail(_Strict):
    source_public_id: str
    title: str
    created_at: str | None = None
    versions: list[KnowledgeRow]


class KnowledgeIndexInfo(_Strict):
    state: str
    chunk_count: int
    embedder: str
    collection: str
    built_at: str | None = None


class KnowledgeActions(_Strict):
    edit: bool
    approve: bool
    reject: bool
    index: bool
    activate: bool
    retire: bool
    reprocess: bool
    delete: bool


class KnowledgeVersionDetail(KnowledgeRow):
    source_reference: str | None = None
    provenance_note: str
    original_filename: str
    media_type: str
    byte_size: int
    checksum_sha256: str
    scanner: str | None = None
    extracted_chars: int | None = None
    preview: str | None = None
    preview_is_truncated: bool
    failed_stage: str | None = None
    rejection_reason: str | None = None
    approved_at: str | None = None
    approved_by_user_id: int | None = None
    indexed_at: str | None = None
    activated_at: str | None = None
    retired_at: str | None = None
    parse_job_id: str | None = None
    index_job_id: str | None = None
    index: KnowledgeIndexInfo | None = None
    blockers: list[str]
    metadata_frozen: bool
    can: KnowledgeActions
    audit: list[AdminAuditEntry] = []


class KnowledgeMetaUpdate(_Strict):
    language: str
    authority_level: int
    publisher: str = ""
    source_reference: str | None = None
    provenance_note: str = ""
    licence_class: str


class KnowledgeRejectRequest(_Strict):
    reason: str


class KnowledgeMeta(_Strict):
    languages: list[str]
    authority_levels: list[dict[str, str | int]]
    licence_classes: list[dict[str, str | bool]]
    states: list[str]
    rejection_reasons: list[str]
    upload: dict[str, str | int | list[str]]


# ---- W10.10 privacy/legal (Admin). Safe operational metadata only: no candidate content, no exported data, no IP/device. ----
class PrivacyRequestRow(_Strict):
    public_id: str
    request_type: str
    type_label: str
    status: str
    result_category: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    source: str
    user_id: int | None = None
    candidate_email: str | None = None
    assigned_user_id: int | None = None
    assignee_email: str | None = None
    acknowledged_at: str | None = None
    completed_at: str | None = None
    closed_at: str | None = None
    related_job_id: str | None = None


class PrivacyRequestPage(_Strict):
    items: list[PrivacyRequestRow]
    total: int
    page: int
    page_size: int


class PrivacyCandidate(_Strict):
    user_id: int
    email: str | None = None
    status: str
    platform_role: str
    created_at: str | None = None


class PrivacyRequestDetail(PrivacyRequestRow):
    request_note: str | None = None
    candidate: PrivacyCandidate | None = None
    allowed_statuses: list[str]
    result_categories: list[str]
    can_execute_deletion: bool
    legal: list[dict[str, str | bool | None]] = []
    audit: list[AdminAuditEntry] = []


class PrivacyRecordRequest(_Strict):
    account: str
    request_type: str
    note: str | None = None


class PrivacyAssignRequest(_Strict):
    assignee_user_id: int | None = None


class PrivacyStatusRequest(_Strict):
    status: str
    result_category: str | None = None


class LegalVersionRow(_Strict):
    id: int
    version: str
    state: str
    is_baseline: bool
    content_ref: str
    content_hash: str | None = None
    effective_at: str | None = None
    published_at: str | None = None
    created_at: str | None = None
    acceptances: int | None = None


class LegalDocumentAdmin(_Strict):
    code: str
    title: str
    current: LegalVersionRow | None = None
    versions: list[LegalVersionRow]
    current_accepted: int
    current_not_recorded: int


class LegalOverview(_Strict):
    documents: list[LegalDocumentAdmin]
    active_accounts: int
    note: str


class LegalDraftRequest(_Strict):
    version: str
    content_ref: str
    content_hash: str | None = None
    effective_at: str | None = None


class LegalDraftUpdate(_Strict):
    content_ref: str
    content_hash: str | None = None
    effective_at: str | None = None
