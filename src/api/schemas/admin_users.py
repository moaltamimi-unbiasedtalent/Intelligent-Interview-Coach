"""Allowlist schemas of the 03C Admin Users additions (``extra="forbid"`` both ways). Metadata only: no field here may carry candidate content (CV, documents,
answers, Mo conversations, memory, evidence), a secret, a session or verification token, a provider subject, or a ticket/privacy-note body."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthMethod(_Strict):
    method: Literal["password", "google", "sso"]
    email_verified: bool
    linked_at: str | None


class AdminUserAuth(_Strict):
    methods: list[AuthMethod]
    local_sign_in: bool
    email_verified: bool
    pending_verification_links: int


class AdminUserActivity(_Strict):
    last_active: Literal["24h", "7d", "30d", "older", "never"]


class AdminUserCases(_Strict):
    support_open: int
    support_total: int
    privacy_open: int
    privacy_total: int
    pending_role_change: bool
    open_deletion_request_id: str | None
    open_deletion_status: str | None


class AdminUserMembership(_Strict):
    active: int
    total: int
    owner_of_active: int


# --- strict action bodies: reason and expected_revision are MANDATORY ---------------------------------------------------------------------------
class ActionBody(_Strict):
    expected_revision: str = Field(min_length=8, max_length=32, pattern=r"^[0-9a-f]+$")
    reason: str = Field(min_length=3, max_length=200)


class AssignPlanBody(ActionBody):
    plan_code: str = Field(min_length=1, max_length=32)


class ActionResult(_Strict):
    user_id: int
    action: str
    changed: bool
    sessions_revoked: int | None = None
    plan_code: str | None = None
    links_expired: int | None = None
    request_id: str | None = None
    mail_accepted: bool | None = None
    revision: str
