"""Email sender adapters and the selection factory (Capstone P1/E1)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol
from src.core import secrets as _secrets

logger = logging.getLogger("mail")

__all__ = [
    "EmailMessage",
    "EmailSender",
    "SendResult",
    "MemoryEmailSender",
    "ConsoleEmailSender",
    "BrevoEmailSender",
    "NotConfiguredEmailSender",
    "build_email_sender",
    "send_detailed",
]

# What the PROVIDER told us at submission time. ``provider_accepted`` is NOT delivery: no delivery or bounce evidence is collected,
# so "delivered" and "bounced" are deliberately not states of this system. ``captured`` is a development/test adapter (nothing was sent).
STATUS_ACCEPTED = "provider_accepted"
STATUS_FAILED = "failed"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_UNKNOWN = "delivery_unknown"
STATUS_CAPTURED = "captured"


@dataclass(frozen=True)
class SendResult:
    """The bounded outcome of one submission. Never carries a body, token, link, header or raw provider text."""

    status: str
    provider: str
    failure_category: str | None = None
    provider_message_ref: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status in (STATUS_ACCEPTED, STATUS_CAPTURED)


@dataclass(frozen=True)
class EmailMessage:
    """A minimal transactional message. ``category`` classifies it for safe logging."""

    to: str
    subject: str
    body: str
    category: str  # "email_verification" | "password_reset" | "account_notice" | "admin_test"


class EmailSender(Protocol):
    """The one method the application depends on."""

    def send(self, message: EmailMessage) -> bool:  # pragma: no cover - protocol
        ...


def _log_safe(message: EmailMessage, *, delivered: bool) -> None:
    """Log ONLY non-sensitive metadata — never the body (which carries the token)."""
    logger.info(
        "email %s category=%s to=%s delivered=%s",
        "sent" if delivered else "captured",
        message.category,
        _mask_email(message.to),
        delivered,
    )


def _mask_email(addr: str) -> str:
    """Mask an address for logs: ``a***@example.com`` (never the full local part)."""
    try:
        local, _, domain = addr.partition("@")
        if not domain:
            return "***"
        head = local[:1]
        return f"{head}***@{domain}"
    except Exception:  # noqa: BLE001
        return "***"


class MemoryEmailSender:
    """Test/dev adapter: captures messages in-process (no external call).

    Tests read :attr:`sent` to assert a message was produced and to extract the link
    it would carry — WITHOUT any real delivery, and without the code pretending a
    real send occurred.
    """

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> bool:
        self.sent.append(message)
        _log_safe(message, delivered=False)
        return True

    def send_detailed(self, message: EmailMessage) -> SendResult:
        self.send(message)
        return SendResult(STATUS_CAPTURED, "memory")

    def last_for(self, category: str) -> EmailMessage | None:
        for msg in reversed(self.sent):
            if msg.category == category:
                return msg
        return None


class ConsoleEmailSender:
    """Local-development adapter: prints the link to STDOUT so a developer can click it.

    Explicitly development-only (never selected in production). It writes to stdout,
    not the application logger, so verification/reset links are not persisted in logs.
    """

    def send(self, message: EmailMessage) -> bool:
        # Deliberately to stdout (developer convenience), not the logger.
        print(f"\n[dev-email:{message.category}] to={message.to}\n{message.body}\n")
        _log_safe(message, delivered=False)
        return True

    def send_detailed(self, message: EmailMessage) -> SendResult:
        self.send(message)
        return SendResult(STATUS_CAPTURED, "console")


class NotConfiguredEmailSender:
    """Used where a real provider is required but not (validly) configured, so mail is NEVER printed or silently dropped as success."""

    def __init__(self, category: str = "provider_not_configured") -> None:
        self._category = category

    def send(self, message: EmailMessage) -> bool:
        return self.send_detailed(message).accepted

    def send_detailed(self, message: EmailMessage) -> SendResult:
        logger.warning("email not sent category=%s reason=%s", message.category, self._category)
        return SendResult(STATUS_NOT_CONFIGURED, "none", self._category)


class BrevoEmailSender:
    """Production adapter for Brevo (transactional email).

    Makes a live HTTPS call ONLY when constructed with an API key and invoked. It is never selected unless
    ``EMAIL_PROVIDER=brevo`` AND a Brevo credential AND a valid ``EMAIL_SENDER`` resolve, so CI/tests never reach a live provider.
    The HTTP status is reduced to a bounded category and the provider's response text is never stored, logged or returned. There
    is no automatic retry: a request that timed out AFTER it was sent has an UNKNOWN outcome and is reported as such (re-sending
    could duplicate a recovery email), while a refused connection is a clean ``provider_unavailable``. The API key is resolved when
    this object is built, so a rotated credential reaches it only after the process restarts (``credential_matches`` says whether it did).
    """

    _ENDPOINT = "https://api.brevo.com/v3/smtp/email"
    TIMEOUT_SECONDS = 10.0

    def __init__(self, *, api_key: str, sender_email: str, sender_name: str = "Ask4Mo",
                 transport=None) -> None:
        if not api_key:
            raise ValueError("BrevoEmailSender requires an API key")
        self._api_key = api_key
        self._sender_email = sender_email
        self._sender_name = sender_name
        self._transport = transport     # tests inject an httpx MockTransport; production leaves it None

    def credential_matches(self, current: str | None) -> bool:
        """True when this client was built with the credential that resolves NOW (constant-time; never returns a value)."""
        import hmac

        return bool(current) and hmac.compare_digest(self._api_key, current or "")

    @property
    def sender_email(self) -> str:
        return self._sender_email

    def send(self, message: EmailMessage) -> bool:
        return self.send_detailed(message).accepted

    def send_detailed(self, message: EmailMessage) -> SendResult:
        import httpx

        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS, follow_redirects=False, transport=self._transport) as client:
                resp = client.post(
                    self._ENDPOINT,
                    headers={"api-key": self._api_key, "content-type": "application/json", "accept": "application/json"},
                    json={
                        "sender": {"email": self._sender_email, "name": self._sender_name},
                        "to": [{"email": message.to}],
                        "subject": message.subject,
                        "textContent": message.body,
                    },
                )
        except httpx.ReadTimeout:
            result = SendResult(STATUS_UNKNOWN, "brevo", "delivery_unknown")           # sent, no answer: outcome unknown
        except httpx.TimeoutException:
            result = SendResult(STATUS_FAILED, "brevo", "provider_timeout")            # never reached the provider
        except Exception:  # noqa: BLE001 - isolate provider failure; the exception text may embed the credential
            result = SendResult(STATUS_FAILED, "brevo", "provider_unavailable")
        else:
            result = _classify_brevo(resp)
        _log_safe(message, delivered=result.accepted)
        if not result.accepted:
            logger.warning("email provider submission not accepted category=%s status=%s reason=%s",
                           message.category, result.status, result.failure_category)
        return result


def _classify_brevo(resp) -> SendResult:
    code = resp.status_code
    if code in (200, 201, 202):
        ref = None
        try:
            mid = resp.json().get("messageId")
            if isinstance(mid, str) and 0 < len(mid) <= 80 and mid.isprintable():
                ref = mid
        except Exception:  # noqa: BLE001
            ref = None
        return SendResult(STATUS_ACCEPTED, "brevo", None, ref)
    if code in (401, 403):
        return SendResult(STATUS_FAILED, "brevo", "provider_auth_failed")
    if code == 429:
        return SendResult(STATUS_FAILED, "brevo", "rate_limited")
    if code >= 500:
        return SendResult(STATUS_FAILED, "brevo", "provider_unavailable")
    if code == 400:
        try:
            blob = str(resp.json().get("message", "")).lower()      # read only to classify; never stored or returned
        except Exception:  # noqa: BLE001
            blob = ""
        return SendResult(STATUS_FAILED, "brevo", "invalid_sender" if "sender" in blob else "message_rejected")
    return SendResult(STATUS_FAILED, "brevo", "message_rejected")


def send_detailed(sender: EmailSender, message: EmailMessage) -> SendResult:
    """Submit through any adapter. Adapters that only know ``send() -> bool`` (older fakes) are mapped without inventing evidence."""
    fn = getattr(sender, "send_detailed", None)
    if callable(fn):
        return fn(message)
    try:
        ok = bool(sender.send(message))
    except Exception:  # noqa: BLE001
        return SendResult(STATUS_FAILED, "unknown", "provider_unavailable")
    return SendResult(STATUS_CAPTURED if ok else STATUS_FAILED, "unknown", None if ok else "provider_unavailable")


def _is_dev_env() -> bool:
    return (os.environ.get("API_ENV", "development") or "development").strip().lower() in {"development", "dev", "local", "test", "testing"}


def _valid_sender_identity(value: str) -> bool:
    """Structural check only. The sender is deployment configuration, never user input; real verification happens at Brevo."""
    v = (value or "").strip()
    return bool(v) and " " not in v and v.count("@") == 1 and "." in v.partition("@")[2] and len(v) <= 254 and not any(c in v for c in "\r\n<>,;")


def build_email_sender() -> EmailSender:
    """Select an adapter from the environment (safe defaults; never live by accident, never a token on stdout in a hosted environment).

    * ``EMAIL_PROVIDER=brevo`` + a Brevo credential (Admin-managed first, then environment) + a valid ``EMAIL_SENDER`` -> Brevo.
    * ``EMAIL_PROVIDER=memory`` -> in-memory capture (tests).
    * development/test with nothing selected -> console (prints the link for a developer).
    * any hosted environment (staging, production) that cannot use Brevo -> ``NotConfiguredEmailSender``: nothing is printed and
      every submission is reported honestly as not configured.
    """
    provider = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower()
    dev = _is_dev_env()
    if provider == "gmail":
        # OAuth credentials and live activation require a separate readiness decision.
        return NotConfiguredEmailSender("provider_not_configured")
    if provider == "brevo":
        api_key = (_secrets.read_setting("BREVO_API_KEY") or "").strip()
        sender = os.environ.get("EMAIL_SENDER", "").strip()
        if api_key and sender and _valid_sender_identity(sender):
            return BrevoEmailSender(api_key=api_key, sender_email=sender)
        if not dev:
            return NotConfiguredEmailSender("invalid_sender" if api_key and sender else "provider_not_configured")
        logger.warning("EMAIL_PROVIDER=brevo but credentials missing; using console sender")
        return ConsoleEmailSender()
    if provider == "memory":
        return MemoryEmailSender()
    return ConsoleEmailSender() if dev else NotConfiguredEmailSender()
