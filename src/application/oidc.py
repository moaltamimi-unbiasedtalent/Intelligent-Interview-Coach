"""Bounded OIDC social-login abstraction (Capstone P1/E1).

ONE social provider (Google) behind a clean seam. The security-critical logic —
CSRF ``state`` validation, redirect allowlisting and account-linking rules — lives
here and in the route, and is fully covered by deterministic tests using a fake
provider. The concrete :class:`GoogleOidcProvider` performs the live authorization-
code exchange via a maintained OAuth flow; it is never reached without configured
credentials, so **live Google validation is classified UNVALIDATED** (see
docs/capstone/p1_e1_identity_platform.md). Core email/password auth never depends on
this module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "OidcIdentity",
    "OidcError",
    "OidcProvider",
    "GoogleOidcProvider",
    "is_safe_redirect",
    "google_enabled",
]


class OidcError(Exception):
    """A social-login failure (safe message; carries no provider secret/token)."""


@dataclass(frozen=True)
class OidcIdentity:
    """A verified identity returned by a provider after code exchange."""

    provider: str
    subject: str
    email: str | None
    email_verified: bool
    display_name: str | None = None


class OidcProvider(Protocol):
    def authorization_url(self, *, state: str, redirect_uri: str) -> str:  # pragma: no cover - protocol
        ...

    def exchange(self, *, code: str, redirect_uri: str) -> OidcIdentity:  # pragma: no cover - protocol
        ...


def is_safe_redirect(target: str | None, *, allowlist: tuple[str, ...] = ()) -> bool:
    """Allow ONLY same-origin relative paths (or an explicit allowlist entry).

    Rejects protocol-relative (``//evil``), absolute (``http://evil``) and other
    open-redirect shapes. The default post-login destination is ``/`` when unsafe.
    """
    if not target:
        return False
    if target in allowlist:
        return True
    # Must be a root-relative path and not protocol-relative or a backslash trick.
    if not target.startswith("/"):
        return False
    if target.startswith("//") or target.startswith("/\\"):
        return False
    if "://" in target or "\\" in target:
        return False
    return True


def google_enabled() -> bool:
    """Google login is on only when explicitly flagged AND configured."""
    from src.application.authorization import flag_enabled

    return flag_enabled("google_login") and bool(
        os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")
    )


class GoogleOidcProvider:
    """Google OIDC via the standard authorization-code flow (live = UNVALIDATED).

    Constructed only when ``GOOGLE_CLIENT_ID``/``GOOGLE_CLIENT_SECRET`` are set. The
    exchange posts the code to Google's token endpoint over TLS and reads verified
    claims from the userinfo endpoint (no locally hand-rolled JWT crypto). No network
    call is made unless the flow is actually exercised with real credentials.
    """

    _AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN = "https://oauth2.googleapis.com/token"
    _USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise OidcError("Google login is not configured.")
        self._client_id = client_id
        self._client_secret = client_secret

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        from urllib.parse import urlencode

        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{self._AUTH}?{urlencode(params)}"

    def exchange(self, *, code: str, redirect_uri: str) -> OidcIdentity:  # pragma: no cover - live path
        try:
            import httpx

            token_resp = httpx.post(
                self._TOKEN,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10.0,
            )
            if token_resp.status_code != 200:
                raise OidcError("Google sign-in failed.")
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise OidcError("Google sign-in failed.")
            info = httpx.get(
                self._USERINFO,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if info.status_code != 200:
                raise OidcError("Google sign-in failed.")
            claims = info.json()
        except OidcError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak provider internals
            raise OidcError("Google sign-in failed.") from exc

        sub = claims.get("sub")
        if not sub:
            raise OidcError("Google sign-in failed.")
        return OidcIdentity(
            provider="google",
            subject=str(sub),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified")),
            display_name=claims.get("name"),
        )
