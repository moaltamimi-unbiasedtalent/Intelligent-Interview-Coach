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

import base64
import hashlib
import json
import secrets as _stdlib_secrets
import time
from dataclasses import dataclass
from typing import Protocol
from src.core import secrets as _secrets

__all__ = [
    "OidcIdentity",
    "OidcError",
    "OidcProvider",
    "GoogleOidcProvider",
    "is_safe_redirect",
    "google_enabled",
    "oidc_status",
    "new_pkce_verifier",
    "pkce_challenge",
    "validate_id_token",
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
    def authorization_url(self, *, state: str, redirect_uri: str, code_challenge: str | None = None) -> str:  # pragma: no cover - protocol
        ...

    def exchange(self, *, code: str, redirect_uri: str, code_verifier: str | None = None) -> OidcIdentity:  # pragma: no cover - protocol
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
    return oidc_status()["enabled"]


def oidc_status() -> dict:
    """Secret-free, FAIL-CLOSED description of Google sign-in. ``enabled`` is True only when the flag is explicitly on AND both client settings exist.

    The default (nothing set) is ``disabled``: ``/auth/oidc/google/start`` answers "not configured" and no provider object is built. ``reason`` is one of
    ``enabled``, ``flag_off`` (the explicit disable path: ``FEATURE_GOOGLE_LOGIN`` unset or false), ``client_id_missing``, ``client_secret_missing``.
    ``live_validated`` is always False: no real-Google round trip is recorded in this repository (05D, NOT RUN until staging).
    """
    from src.application.authorization import flag_enabled

    has_id = bool((_secrets.read_setting("GOOGLE_CLIENT_ID") or "").strip())
    has_secret = bool((_secrets.read_setting("GOOGLE_CLIENT_SECRET") or "").strip())
    if not flag_enabled("google_login"):
        reason = "flag_off"
    elif not has_id:
        reason = "client_id_missing"
    elif not has_secret:
        reason = "client_secret_missing"
    else:
        reason = "enabled"
    return {"enabled": reason == "enabled", "reason": reason, "client_id_set": has_id, "client_secret_set": has_secret, "live_validated": False}


# --- PKCE (RFC 7636, S256) --------------------------------------------------------------------------------------------
def new_pkce_verifier() -> str:
    """A fresh transaction-specific code verifier: 48 random bytes, 64 URL-safe characters (RFC 7636 allows 43 to 128)."""
    return _stdlib_secrets.token_urlsafe(48)


def pkce_challenge(verifier: str) -> str:
    """``BASE64URL(SHA256(verifier))`` without padding (the S256 method)."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


# --- ID token validation (OpenID Connect Core 1.0, 3.1.3.7) ---------------------------------------------------------------
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
CLOCK_SKEW_SECONDS = 60
ID_TOKEN_MAX_AGE_SECONDS = 24 * 60 * 60     # iat plausibility: Google ID tokens live one hour; anything older than a day is refused


def _b64url_json(part: str) -> dict:
    raw = base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise OidcError("Google sign-in failed.")
    return value


def validate_id_token(id_token: object, *, client_id: str, access_token: str | None = None, now: float | None = None) -> dict:
    """Validate an ID token received DIRECTLY from the token endpoint and return its claims.

    Authenticity method (3.1.3.7 step 6): the token was returned in the TLS-authenticated response of OUR OWN code redemption at a
    hard-coded Google endpoint, so TLS server validation stands in for the signature check, which the specification permits for exactly
    this case; the token never passes through the browser. Everything else is enforced:

    * structure: three segments, JSON header and payload;
    * algorithm restriction: ``alg`` must be ``RS256`` (Google's registered algorithm), so ``none`` and any HMAC algorithm are refused;
    * ``iss`` is Google's issuer (either documented form);
    * ``aud`` contains this client id; with several audiences ``azp`` is required, and any ``azp`` must equal this client id;
    * ``exp`` is in the future and ``iat`` is neither in the future nor implausibly old (60 second skew);
    * ``sub`` is a non-empty string of at most 255 characters;
    * ``at_hash``, when present, matches the access token (3.1.3.6);
    * ``email_verified``, when present, is a real boolean (a string such as "false" is refused outright).
    No claim from an unvalidated token is ever returned.
    """
    bad = OidcError("Google sign-in failed.")
    if not isinstance(id_token, str) or id_token.count(".") != 2:
        raise bad
    try:
        header_part, payload_part, _signature = id_token.split(".")
        header, claims = _b64url_json(header_part), _b64url_json(payload_part)
    except OidcError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise bad from exc
    if header.get("alg") != "RS256":
        raise bad
    t = time.time() if now is None else now
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise bad
    aud = claims.get("aud")
    audiences = [aud] if isinstance(aud, str) else aud if isinstance(aud, list) and all(isinstance(a, str) for a in aud) else None
    if not audiences or client_id not in audiences:
        raise bad
    azp = claims.get("azp")
    if (len(audiences) > 1 and azp is None) or (azp is not None and azp != client_id):
        raise bad
    exp, iat = claims.get("exp"), claims.get("iat")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or exp <= t - CLOCK_SKEW_SECONDS:
        raise bad
    if isinstance(iat, bool) or not isinstance(iat, (int, float)) or iat > t + CLOCK_SKEW_SECONDS or t - iat > ID_TOKEN_MAX_AGE_SECONDS:
        raise bad
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > 255:
        raise bad
    if "email_verified" in claims and not isinstance(claims["email_verified"], bool):
        raise bad
    if "email" in claims and not isinstance(claims["email"], str):
        raise bad
    at_hash = claims.get("at_hash")
    if at_hash is not None and access_token is not None:
        digest = hashlib.sha256(access_token.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest[: len(digest) // 2]).rstrip(b"=").decode("ascii")
        if not isinstance(at_hash, str) or not _stdlib_secrets.compare_digest(at_hash, expected):
            raise bad
    return claims


class GoogleOidcProvider:
    """Google OIDC via the authorization-code flow with PKCE (live = UNVALIDATED).

    Constructed only when ``GOOGLE_CLIENT_ID``/``GOOGLE_CLIENT_SECRET`` are set. The authorization request carries a PKCE S256
    challenge; the code exchange posts the matching verifier with the client secret over TLS to Google's token endpoint. The ID token
    returned by that endpoint is validated (see :func:`validate_id_token`) and is the AUTHORITATIVE source of the subject; the UserInfo
    response is only a supplement and its ``sub`` MUST equal the validated ID-token ``sub`` (OIDC Core 5.3.2), as must any email it
    repeats. A mismatch rejects the whole sign-in before any local account is created or linked. No network call is made unless the
    flow is exercised with real credentials; tests inject a mock transport.
    """

    _AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN = "https://oauth2.googleapis.com/token"
    _USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self, *, client_id: str, client_secret: str, transport=None, clock=None) -> None:
        if not client_id or not client_secret:
            raise OidcError("Google login is not configured.")
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport     # tests inject an httpx MockTransport; production leaves it None
        self._clock = clock             # tests inject a fixed clock; production uses time.time

    def authorization_url(self, *, state: str, redirect_uri: str, code_challenge: str | None = None) -> str:
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
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self._AUTH}?{urlencode(params)}"

    def exchange(self, *, code: str, redirect_uri: str, code_verifier: str | None = None) -> OidcIdentity:
        if not code_verifier:
            raise OidcError("Google sign-in failed.")        # a flow without PKCE is never completed
        try:
            import httpx

            with httpx.Client(timeout=10.0, follow_redirects=False, transport=self._transport) as client:
                token_resp = client.post(
                    self._TOKEN,
                    data={
                        "code": code,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                        "code_verifier": code_verifier,
                    },
                )
                if token_resp.status_code != 200:
                    raise OidcError("Google sign-in failed.")
                body = token_resp.json()
                access_token = body.get("access_token")
                id_token = body.get("id_token")
                if not access_token or not isinstance(access_token, str):
                    raise OidcError("Google sign-in failed.")
                claims = validate_id_token(id_token, client_id=self._client_id, access_token=access_token,
                                           now=self._clock() if self._clock else None)
                info = client.get(self._USERINFO, headers={"Authorization": f"Bearer {access_token}"})
                if info.status_code != 200:
                    raise OidcError("Google sign-in failed.")
                userinfo = info.json()
        except OidcError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak provider internals
            raise OidcError("Google sign-in failed.") from exc

        if not isinstance(userinfo, dict) or userinfo.get("sub") != claims["sub"]:
            raise OidcError("Google sign-in failed.")        # 5.3.2: the UserInfo subject MUST match the ID token subject
        ui_verified = userinfo.get("email_verified")
        if ui_verified is not None and not isinstance(ui_verified, bool):
            raise OidcError("Google sign-in failed.")
        email = claims.get("email")
        ui_email = userinfo.get("email")
        if ui_email is not None and (not isinstance(ui_email, str) or (email is not None and ui_email.lower() != email.lower())):
            raise OidcError("Google sign-in failed.")
        email = email if email is not None else ui_email
        verified = claims.get("email_verified") is True and ui_verified is not False      # strict booleans only
        name = userinfo.get("name") if isinstance(userinfo.get("name"), str) else None
        return OidcIdentity(provider="google", subject=claims["sub"], email=email, email_verified=bool(verified and email),
                            display_name=name)
