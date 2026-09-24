"""Email sender adapters and the selection factory (Capstone P1/E1)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("mail")

__all__ = [
    "EmailMessage",
    "EmailSender",
    "MemoryEmailSender",
    "ConsoleEmailSender",
    "BrevoEmailSender",
    "build_email_sender",
]


@dataclass(frozen=True)
class EmailMessage:
    """A minimal transactional message. ``category`` classifies it for safe logging."""

    to: str
    subject: str
    body: str
    category: str  # "email_verification" | "password_reset"


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


class BrevoEmailSender:
    """Production adapter for Brevo (transactional email).

    Makes a live HTTPS call ONLY when constructed with an API key and invoked. It is
    never selected unless ``EMAIL_PROVIDER=brevo`` AND ``BREVO_API_KEY`` are set, so
    CI/tests never reach a live provider. Failure is isolated (returns False).
    """

    _ENDPOINT = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, *, api_key: str, sender_email: str, sender_name: str = "Ask4Mo") -> None:
        if not api_key:
            raise ValueError("BrevoEmailSender requires an API key")
        self._api_key = api_key
        self._sender_email = sender_email
        self._sender_name = sender_name

    def send(self, message: EmailMessage) -> bool:  # pragma: no cover - live path
        try:
            import httpx

            resp = httpx.post(
                self._ENDPOINT,
                headers={"api-key": self._api_key, "content-type": "application/json"},
                json={
                    "sender": {"email": self._sender_email, "name": self._sender_name},
                    "to": [{"email": message.to}],
                    "subject": message.subject,
                    "textContent": message.body,
                },
                timeout=10.0,
            )
            delivered = resp.status_code in (200, 201, 202)
            _log_safe(message, delivered=delivered)
            return delivered
        except Exception:  # noqa: BLE001 - isolate provider failure from the request
            logger.warning("email provider send failed category=%s", message.category)
            return False


def build_email_sender() -> EmailSender:
    """Select an adapter from the environment (safe defaults; never live by accident).

    * ``EMAIL_PROVIDER=brevo`` + ``BREVO_API_KEY`` + ``EMAIL_SENDER`` → Brevo (prod).
    * ``EMAIL_PROVIDER=memory`` → in-memory capture (tests).
    * otherwise → console (local development).
    """
    provider = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower()
    if provider == "brevo":
        api_key = os.environ.get("BREVO_API_KEY", "").strip()
        sender = os.environ.get("EMAIL_SENDER", "").strip()
        if api_key and sender:
            return BrevoEmailSender(api_key=api_key, sender_email=sender)
        logger.warning("EMAIL_PROVIDER=brevo but credentials missing; using console sender")
        return ConsoleEmailSender()
    if provider == "memory":
        return MemoryEmailSender()
    return ConsoleEmailSender()
