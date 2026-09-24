"""Typed request/response contracts for the authentication & account API (P1/E1).

Deliberately minimal and non-leaking: responses never echo a password, token,
password hash or session token (the session travels only in an HttpOnly cookie).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "VerifyEmailRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "MessageResponse",
    "AccountResponse",
    "PremiumStatusResponse",
    "PreferencesRequest",
]


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=200)


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=512)
    password: str = Field(..., min_length=1, max_length=200)


class MessageResponse(BaseModel):
    """A neutral, non-enumerating message (same shape for success/uniform outcomes)."""

    message: str


class AccountResponse(BaseModel):
    """The caller's own account/profile summary (never another user's)."""

    user_id: int
    email: str | None
    display_name: str | None
    platform_role: str
    tier: str
    status: str
    email_verified: bool
    providers: list[str]
    auth_method: str
    capabilities: list[str]
    # Presentation depth preference (P2/E2) — brief/detailed. Low-sensitivity metadata.
    response_detail: str = "brief"


class PreferencesRequest(BaseModel):
    """Update low-sensitivity user preferences (P2/E2)."""

    response_detail: Literal["brief", "detailed"]


class PremiumStatusResponse(BaseModel):
    """Demonstration of server-side entitlement enforcement (premium-only endpoint)."""

    entitled: bool
    tier: str
    message: str
