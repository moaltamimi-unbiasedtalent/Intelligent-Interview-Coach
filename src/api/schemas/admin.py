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
