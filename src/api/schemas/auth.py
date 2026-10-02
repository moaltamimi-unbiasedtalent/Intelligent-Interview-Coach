"""Typed request/response contracts for the authentication & account API (P1/E1).

Deliberately minimal and non-leaking: responses never echo a password, token,
password hash or session token (the session travels only in an HttpOnly cookie).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.locales import AppLocale

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
    # W10.1: admin permissions resolved SERVER-side from the persisted role (empty for candidates). The
    # frontend uses this list for navigation only (UX); the backend re-checks every admin request.
    admin_permissions: list[str] = []
    # Presentation depth preference (P2/E2) — brief/detailed. Low-sensitivity metadata.
    response_detail: str = "brief"
    # Internationalization (P3.5) — independent, bounded language preferences.
    interface_locale: str = "en"
    conversation_language: str = "en"
    # P10B Wave 2 personalisation + first-run onboarding lifecycle (low-sensitivity; every tier).
    coaching_style: str = "balanced"
    career_geography: str = ""
    target_role: str = ""
    onboarding_completed: bool = True
    onboarding_step: int = 0


# Bounded career-geography identifier (P10B Wave 2) — account-default target market, DELIBERATELY
# independent of any language/locale. "" means unspecified.
CareerGeography = Literal[
    "", "global", "de", "at", "ch", "fr", "es", "it", "pt", "nl", "be", "lu",
    "gb", "ie", "us", "ca", "au", "nz", "other",
]


class PreferencesRequest(BaseModel):
    """Partial update of low-sensitivity user preferences (P2/E2 + P3.5 + P10B Wave 2).

    Every field is optional; only supplied fields are changed. Each bounded field is a Literal,
    so a spoofed/arbitrary value is rejected (422) and can never be persisted. ``display_name`` and
    ``target_role`` are free text stored as DATA (bounded length) — never fed to a model as a prompt.
    """

    model_config = {"extra": "forbid"}

    response_detail: Literal["brief", "detailed"] | None = None
    interface_locale: AppLocale | None = None
    conversation_language: AppLocale | None = None
    coaching_style: Literal["supportive", "balanced", "direct", "challenging"] | None = None
    career_geography: CareerGeography | None = None
    target_role: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, max_length=255)


class OnboardingRequest(BaseModel):
    """Persist onboarding progress (resume) and/or mark it complete (P10B Wave 2)."""

    model_config = {"extra": "forbid"}

    step: int | None = Field(default=None, ge=0, le=8)
    complete: bool = False


class PremiumStatusResponse(BaseModel):
    """Demonstration of server-side entitlement enforcement (premium-only endpoint)."""

    entitled: bool
    tier: str
    message: str
