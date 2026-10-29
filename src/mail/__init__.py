"""Transactional email provider abstraction (Capstone P1/E1).

Two use cases only: verify-email and password-reset. The application never depends
on live email — a development/test adapter captures messages in-process so flows are
fully testable WITHOUT pretending a real send happened, and a production adapter
(Brevo) is used only when explicitly configured with credentials.

Failure is isolated: a send failure never crashes a request (the caller decides how
to surface it), and nothing here logs a raw token or a reset/verification link body.
"""

from __future__ import annotations

from src.mail.sender import (
    BrevoEmailSender,
    ConsoleEmailSender,
    EmailMessage,
    EmailSender,
    MemoryEmailSender,
    NotConfiguredEmailSender,
    SendResult,
    build_email_sender,
    send_detailed,
)

from src.mail.gmail import GmailEmailSender, GmailTokenSource

__all__ = [
    "GmailEmailSender",
    "GmailTokenSource",
    "BrevoEmailSender",
    "EmailMessage",
    "EmailSender",
    "MemoryEmailSender",
    "ConsoleEmailSender",
    "NotConfiguredEmailSender",
    "SendResult",
    "build_email_sender",
    "send_detailed",
]
