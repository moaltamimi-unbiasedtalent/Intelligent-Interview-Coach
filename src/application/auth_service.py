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
from src.mail import EmailMessage, EmailSender, SendResult
from src.mail.service import EmailAttemptRepository, EmailService
from src.mail.templates import normalise_locale, render
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
        email_attempts: EmailAttemptRepository | None = None,
    ) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._tokens = auth_tokens
        self._audit = audit
        self._email = email
        # One submission boundary (W12.4C): every message goes through EmailService, which returns what the provider answered and records a
        # minimal attempt. Identity code never sees HTTP, a credential or a provider response.
        self._mail = email if isinstance(email, EmailService) else EmailService(email, email_attempts)
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
        locale: str | None = None,
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
            loc = normalise_locale(locale)
            rendered = render("account_notice", locale=loc)
            self._deliver(EmailMessage(to=email_norm, subject=rendered.subject, body=rendered.body, category="account_notice"),
                          locale=loc, request_id=request_id, user_id=None)
            return RegisterOutcome(created=False)

        self._audit.record(
            event_type="account.register",
            result="success",
            actor_user_id=user_id,
            request_id=request_id,
        )
        loc = normalise_locale(locale)
        if locale:
            self._accounts.set_interface_locale(user_id, loc)      # the recipient's language for every later identity email
        self._send_verification(user_id=user_id, email=email_norm, locale=loc, request_id=request_id)
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

    def send_verification(self, *, user_id: int, request_id: str | None = None) -> SendResult | None:
        """(Re)send the caller's OWN verification link. Returns the submission result, or None when there is nothing to send."""
        account = self._accounts.get_account(user_id)
        if account and account.email and not account.email_verified:
            return self._send_verification(user_id=user_id, email=account.email, locale=account.interface_locale, request_id=request_id)
        return None

    def _send_verification(self, *, user_id: int, email: str, locale: str | None, request_id: str | None = None) -> SendResult:
        raw = tokens.generate_token(tokens.LINK_TOKEN_BYTES)
        self._tokens.issue(
            token_hash=tokens.hash_token(raw),
            user_id=user_id,
            purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
            ttl_seconds=self._config.verify_ttl_seconds,
        )
        link = f"{self._config.app_base_url}/verify-email?token={quote(raw)}"
        rendered = render("email_verification", locale=locale, link=link, expires_in_seconds=self._config.verify_ttl_seconds)
        return self._deliver(EmailMessage(to=email, subject=rendered.subject, body=rendered.body, category="email_verification"),
                             locale=rendered.locale, request_id=request_id, user_id=user_id)

    def _deliver(self, message: EmailMessage, *, locale: str | None, request_id: str | None, user_id: int | None) -> SendResult:
        """Submit and, when the provider did not take the message, audit a bounded failure (category only: no recipient, link or token)."""
        result = self._mail.deliver(message, locale=locale, request_id=request_id, user_id=user_id)
        if not result.accepted:
            self._audit.record(event_type="account.email_failed", result="failure", actor_user_id=user_id, request_id=request_id,
                               context={"message_type": message.category, "category": result.failure_category or "unknown"})
        return result

    def verify_email(self, *, token: str, request_id: str | None = None) -> bool:
        """Consume a verification token (single-use) and mark the email verified."""
        return self.verify_email_detailed(token=token, request_id=request_id)[0]

    def verify_email_detailed(self, *, token: str, request_id: str | None = None) -> tuple[bool, str | None]:
        """As :meth:`verify_email`, plus a bounded reason on failure (``invalid`` | ``used`` | ``expired``) for the holder of the link."""
        if not token:
            return False, "invalid"
        user_id, reason = self._tokens.consume_detailed(
            token_hash=tokens.hash_token(token),
            purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
        )
        if user_id is None:
            self._audit.record(
                event_type="account.verify_email", result="failure", request_id=request_id,
                context={"reason": reason or "invalid"},
            )
            return False, reason
        self._accounts.mark_email_verified(user_id)
        self._audit.record(
            event_type="account.verify_email",
            result="success",
            actor_user_id=user_id,
            request_id=request_id,
        )
        return True, None

    # -- password reset -------------------------------------------------------

    def request_password_reset(self, *, email: str, request_id: str | None = None) -> None:
        """Issue a reset link IF a password account exists — always returns None (no enumeration).

        Only an ACTIVE account that actually has a password credential gets a link: an OIDC-only identity cannot be given a password
        by this flow without a deliberate product decision, and a suspended or deactivated account is never mailed. The public
        response is identical in every case; only the audit trail records which branch was taken.
        """
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
        if account.status != ACCOUNT_STATUS_ACTIVE or not account.has_password:
            self._audit.record(
                event_type="account.reset_request", result="not_eligible", actor_user_id=account.user_id, request_id=request_id,
                context={"reason": "inactive_account" if account.status != ACCOUNT_STATUS_ACTIVE else "no_password_credential"},
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
        rendered = render("password_reset", locale=account.interface_locale, link=link, expires_in_seconds=self._config.reset_ttl_seconds)
        result = self._deliver(EmailMessage(to=email_norm, subject=rendered.subject, body=rendered.body, category="password_reset"),
                               locale=rendered.locale, request_id=request_id, user_id=account.user_id)
        self._audit.record(
            event_type="account.reset_request",
            result="success" if result.accepted else "delivery_failed",
            actor_user_id=account.user_id,
            request_id=request_id,
        )

    def reset_password(
        self, *, token: str, new_password: str, request_id: str | None = None
    ) -> bool:
        """Consume a reset token, set the new password and revoke all sessions."""
        return self.reset_password_detailed(token=token, new_password=new_password, request_id=request_id)[0]

    def reset_password_detailed(
        self, *, token: str, new_password: str, request_id: str | None = None
    ) -> tuple[bool, str | None]:
        """As :meth:`reset_password`, plus a bounded failure reason (``invalid`` | ``used`` | ``expired``).

        Single use is enforced by one conditional UPDATE. Every session of the account is revoked (the old password may have been
        compromised); other pending reset links die with it; OIDC identities and other accounts are untouched.
        """
        _valid_password(new_password)
        if not token:
            return False, "invalid"
        user_id, reason = self._tokens.consume_detailed(
            token_hash=tokens.hash_token(token),
            purpose=TOKEN_PURPOSE_PASSWORD_RESET,
        )
        if user_id is None:
            self._audit.record(
                event_type="account.reset_complete", result="failure", request_id=request_id,
                context={"reason": reason or "invalid"},
            )
            return False, reason
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
        return True, None

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
