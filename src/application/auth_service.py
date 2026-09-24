"""Authentication application service (Capstone P1/E1).

Framework-free orchestration of the account lifecycle over the identity
repositories, the password hasher, the opaque-token helpers and the email sender.
It owns the *decisions* (what is valid, what to audit, what to email); the HTTP
layer only maps results to responses/cookies.

Security posture:
* Passwords are bcrypt-hashed; the service never sees or stores plaintext at rest.
* Login failures are generic (no user enumeration); registration and
  forgot-password return uniform outcomes regardless of whether the email exists.
* Verification / reset tokens are single-use, expiring, and stored only as hashes.
* Every notable event is audited WITHOUT secrets, tokens or private content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote

from src.application.errors import ValidationError
from src.auth_repository import (
    AccountRecord,
    AccountRepository,
    AuditRepository,
    SessionRepository,
    TokenRepository,
)
from src.mail import EmailMessage, EmailSender
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
)
from src.authsec import passwords, tokens

__all__ = [
    "AuthConfig",
    "AuthenticationService",
    "InvalidCredentialsError",
    "RegisterOutcome",
    "LoginResult",
]


class InvalidCredentialsError(ValidationError):
    """Login failed. Deliberately generic (no enumeration) — mapped to 401 by the route."""


@dataclass(frozen=True)
class AuthConfig:
    session_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    verify_ttl_seconds: int = 60 * 60 * 24  # 24 hours
    reset_ttl_seconds: int = 60 * 60  # 1 hour
    app_base_url: str = "http://localhost:3000"
    cookie_name: str = "ask4mo_session"

    @classmethod
    def from_env(cls) -> "AuthConfig":
        base = (os.environ.get("APP_BASE_URL") or "").strip()
        if not base:
            origins = (os.environ.get("FRONTEND_ORIGINS") or "").strip()
            base = origins.split(",")[0].strip() if origins else "http://localhost:3000"
        return cls(app_base_url=base.rstrip("/"))


@dataclass(frozen=True)
class RegisterOutcome:
    """Uniform registration result (does not reveal whether the email existed)."""

    created: bool


@dataclass(frozen=True)
class LoginResult:
    session_token: str
    user_id: int


class AuthenticationService:
    def __init__(
        self,
        *,
        accounts: AccountRepository,
        sessions: SessionRepository,
        auth_tokens: TokenRepository,
        audit: AuditRepository,
        email: EmailSender,
        config: AuthConfig | None = None,
    ) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._tokens = auth_tokens
        self._audit = audit
        self._email = email
        self._config = config or AuthConfig()

    @property
    def config(self) -> AuthConfig:
        return self._config

    # -- registration ---------------------------------------------------------

    def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
        request_id: str | None = None,
    ) -> RegisterOutcome:
        """Create a password account and email a verification link.

        Returns a UNIFORM outcome: whether or not the email already exists, the caller
        sends the same response. If the email is taken, no duplicate is created and a
        neutral "account already exists" note is emailed instead.
        """
        email_norm = _valid_email(email)
        _valid_password(password)
        name = (display_name or "").strip() or None

        user_id = self._accounts.create_password_account(
            email=email_norm,
            password_hash=passwords.hash_password(password),
            display_name=name,
        )
        if user_id is None:
            # Email already registered — do not enumerate; send a neutral notice.
            self._audit.record(
                event_type="account.register",
                result="duplicate",
                target_type="email",
                request_id=request_id,
            )
            self._email.send(
                EmailMessage(
                    to=email_norm,
                    subject="Your Ask4Mo account",
                    body=(
                        "Someone tried to create an Ask4Mo account with this email, "
                        "but one already exists. If this was you, please sign in or "
                        "reset your password."
                    ),
                    category="email_verification",
                )
            )
            return RegisterOutcome(created=False)

        self._audit.record(
            event_type="account.register",
            result="success",
            actor_user_id=user_id,
            request_id=request_id,
        )
        self._send_verification(user_id=user_id, email=email_norm)
        return RegisterOutcome(created=True)

    # -- login / logout -------------------------------------------------------

    def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> LoginResult:
        """Verify credentials and open a server-side session.

        Raises :class:`InvalidCredentialsError` (generic) for any failure — wrong
        password, unknown email, no password credential, or a non-active account —
        so the caller cannot distinguish them.
        """
        email_norm = _valid_email(email)
        account = self._accounts.find_by_email(email_norm)
        # Always run a hash comparison to keep timing uniform whether or not the
        # account/credential exists (mitigates account enumeration via timing).
        stored = self._accounts.get_password_hash(account.user_id) if account else None
        ok = passwords.verify_password(password, stored)

        if not account or not ok or account.status != ACCOUNT_STATUS_ACTIVE:
            self._audit.record(
                event_type="account.login",
                result="failure",
                actor_user_id=account.user_id if account else None,
                request_id=request_id,
                context={"reason": "invalid_credentials"},
            )
            raise InvalidCredentialsError("Incorrect email or password.")

        raw = tokens.generate_token(tokens.SESSION_TOKEN_BYTES)
        self._sessions.create(
            token_hash=tokens.hash_token(raw),
            user_id=account.user_id,
            ttl_seconds=self._config.session_ttl_seconds,
            user_agent=_trim(user_agent, 256),
        )
        self._audit.record(
            event_type="account.login",
            result="success",
            actor_user_id=account.user_id,
            request_id=request_id,
        )
        return LoginResult(session_token=raw, user_id=account.user_id)

    def oidc_login(
        self, *, identity, user_agent: str | None = None, request_id: str | None = None
    ) -> LoginResult:
        """Resolve a verified social identity to a session (create/link the account).

        ``identity`` is an :class:`src.application.oidc.OidcIdentity`. Account linking
        (by provider-verified email) and duplicate handling live in the repository.
        """
        user_id = self._accounts.link_or_create_oidc(
            provider=identity.provider,
            provider_subject=identity.subject,
            email=identity.email,
            email_verified=identity.email_verified,
            display_name=identity.display_name,
        )
        raw = tokens.generate_token(tokens.SESSION_TOKEN_BYTES)
        self._sessions.create(
            token_hash=tokens.hash_token(raw),
            user_id=user_id,
            ttl_seconds=self._config.session_ttl_seconds,
            user_agent=_trim(user_agent, 256),
        )
        self._audit.record(
            event_type="account.oidc_login",
            result="success",
            actor_user_id=user_id,
            request_id=request_id,
            context={"provider": identity.provider},
        )
        return LoginResult(session_token=raw, user_id=user_id)

    def logout(self, *, session_token: str, request_id: str | None = None) -> bool:
        """Invalidate the current session server-side (idempotent)."""
        revoked = self._sessions.revoke(tokens.hash_token(session_token))
        if revoked:
            self._audit.record(
                event_type="account.logout", result="success", request_id=request_id
            )
        return revoked

    def resolve_session(self, session_token: str) -> int | None:
        """Return the owning user_id for a live session token, else None."""
        if not session_token:
            return None
        return self._sessions.resolve(tokens.hash_token(session_token))

    # -- email verification ---------------------------------------------------

    def send_verification(self, *, user_id: int) -> None:
        account = self._accounts.get_account(user_id)
        if account and account.email and not account.email_verified:
            self._send_verification(user_id=user_id, email=account.email)

    def _send_verification(self, *, user_id: int, email: str) -> None:
        raw = tokens.generate_token(tokens.LINK_TOKEN_BYTES)
        self._tokens.issue(
            token_hash=tokens.hash_token(raw),
            user_id=user_id,
            purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
            ttl_seconds=self._config.verify_ttl_seconds,
        )
        link = f"{self._config.app_base_url}/verify-email?token={quote(raw)}"
        self._email.send(
            EmailMessage(
                to=email,
                subject="Verify your Ask4Mo email",
                body=f"Welcome to Ask4Mo. Verify your email:\n{link}\n\nThis link expires in 24 hours.",
                category="email_verification",
            )
        )

    def verify_email(self, *, token: str, request_id: str | None = None) -> bool:
        """Consume a verification token (single-use) and mark the email verified."""
        if not token:
            return False
        user_id = self._tokens.consume(
            token_hash=tokens.hash_token(token),
            purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
        )
        if user_id is None:
            self._audit.record(
                event_type="account.verify_email", result="failure", request_id=request_id
            )
            return False
        self._accounts.mark_email_verified(user_id)
        self._audit.record(
            event_type="account.verify_email",
            result="success",
            actor_user_id=user_id,
            request_id=request_id,
        )
        return True

    # -- password reset -------------------------------------------------------

    def request_password_reset(self, *, email: str, request_id: str | None = None) -> None:
        """Issue a reset link IF the account exists — always returns None (no enumeration)."""
        try:
            email_norm = _valid_email(email)
        except ValidationError:
            return
        account = self._accounts.find_by_email(email_norm)
        if account is None:
            self._audit.record(
                event_type="account.reset_request", result="unknown_email", request_id=request_id
            )
            return
        raw = tokens.generate_token(tokens.LINK_TOKEN_BYTES)
        self._tokens.issue(
            token_hash=tokens.hash_token(raw),
            user_id=account.user_id,
            purpose=TOKEN_PURPOSE_PASSWORD_RESET,
            ttl_seconds=self._config.reset_ttl_seconds,
        )
        link = f"{self._config.app_base_url}/reset-password?token={quote(raw)}"
        self._email.send(
            EmailMessage(
                to=email_norm,
                subject="Reset your Ask4Mo password",
                body=f"Reset your password:\n{link}\n\nThis link expires in 1 hour. If you did not request this, ignore this email.",
                category="password_reset",
            )
        )
        self._audit.record(
            event_type="account.reset_request",
            result="success",
            actor_user_id=account.user_id,
            request_id=request_id,
        )

    def reset_password(
        self, *, token: str, new_password: str, request_id: str | None = None
    ) -> bool:
        """Consume a reset token, set the new password and revoke all sessions."""
        _valid_password(new_password)
        if not token:
            return False
        user_id = self._tokens.consume(
            token_hash=tokens.hash_token(token),
            purpose=TOKEN_PURPOSE_PASSWORD_RESET,
        )
        if user_id is None:
            self._audit.record(
                event_type="account.reset_complete", result="failure", request_id=request_id
            )
            return False
        self._accounts.set_password(user_id, passwords.hash_password(new_password))
        # Reset invalidates every existing session (defence in depth after takeover).
        self._sessions.revoke_all_for_user(user_id)
        self._tokens.invalidate_for_user(
            user_id=user_id, purpose=TOKEN_PURPOSE_PASSWORD_RESET
        )
        self._audit.record(
            event_type="account.reset_complete",
            result="success",
            actor_user_id=user_id,
            request_id=request_id,
        )
        return True

    # -- account view ---------------------------------------------------------

    def account(self, user_id: int) -> AccountRecord | None:
        return self._accounts.get_account(user_id)


# --- validation helpers ------------------------------------------------------


def _valid_email(email: str) -> str:
    value = (email or "").strip().lower()
    # Minimal structural check (not RFC-complete): one @, a dot in the domain, no spaces.
    if not value or " " in value or value.count("@") != 1:
        raise ValidationError("Enter a valid email address.")
    local, _, domain = value.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValidationError("Enter a valid email address.")
    if len(value) > 320:
        raise ValidationError("Enter a valid email address.")
    return value


def _valid_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < passwords.MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {passwords.MIN_PASSWORD_LENGTH} characters."
        )
    if len(password) > passwords.MAX_PASSWORD_LENGTH:
        raise ValidationError("Password is too long.")


def _trim(value: str | None, n: int) -> str | None:
    if not value:
        return None
    return value[:n]
