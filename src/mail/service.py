"""Transactional email boundary and bounded delivery diagnostics (W12.4C).

``EmailService`` is the ONE place identity services submit mail: they hand over a message and receive a ``SendResult`` that says what
the provider answered at submission time. It records a minimal ``EmailAttempt`` (no recipient, token, link, subject or body) and never
raises into the caller, so a provider problem can neither crash a request nor be reported as success.

Truth model: ``provider_accepted`` means the provider took the message, not that it was delivered, opened or acted on. No delivery or
bounce event is collected (no webhook is implemented), so this system never reports ``delivered``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from src.mail.sender import EmailMessage, EmailSender, SendResult, send_detailed
from src.persistence import EmailAttempt, utcnow

log = logging.getLogger("mail.service")

RETENTION_DAYS = 30          # technical default for operational delivery evidence; not a legal period
IDENTITY_TYPES = ("email_verification", "password_reset")


class EmailAttemptRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def record(self, *, message_type: str, result: SendResult, locale: str | None, request_id: str | None, user_id: int | None) -> None:
        """Best effort: a diagnostics write failure never affects the request. Old rows are purged opportunistically."""
        try:
            with self._sf() as s:
                s.add(EmailAttempt(
                    message_type=message_type, provider=result.provider[:16], status=result.status,
                    failure_category=result.failure_category, provider_message_ref=result.provider_message_ref,
                    locale=locale, request_id=(request_id or None) and request_id[:64], user_id=user_id))
                s.execute(delete(EmailAttempt).where(EmailAttempt.created_at < utcnow() - timedelta(days=RETENTION_DAYS)))
                s.commit()
        except Exception:  # noqa: BLE001
            log.warning("email attempt record failed")

    def summary(self) -> dict:
        """Bounded aggregates and the last few attempts. No recipient, user id, token, link or message content exists to return."""
        now = utcnow()
        day = now - timedelta(hours=24)
        with self._sf() as s:
            def last(*where):
                return s.scalar(select(EmailAttempt).where(*where).order_by(EmailAttempt.created_at.desc(), EmailAttempt.id.desc()).limit(1))

            def view(a):
                return None if a is None else {"at": a.created_at.isoformat(), "message_type": a.message_type, "status": a.status,
                                               "failure_category": a.failure_category}
            counts = {st: n for st, n in s.execute(select(EmailAttempt.status, func.count()).where(EmailAttempt.created_at >= day)
                                                   .group_by(EmailAttempt.status)).all()}
            id_last = last(EmailAttempt.message_type.in_(IDENTITY_TYPES))
            recent = s.scalars(select(EmailAttempt).order_by(EmailAttempt.created_at.desc(), EmailAttempt.id.desc()).limit(10)).all()
            return {
                "retention_days": RETENTION_DAYS,
                "last_attempt": view(last()),
                "last_accepted": view(last(EmailAttempt.status == "provider_accepted")),
                "last_failure": view(last(EmailAttempt.status.in_(("failed", "not_configured", "delivery_unknown")))),
                "last_identity_attempt": view(id_last),
                "last_24h": {"provider_accepted": counts.get("provider_accepted", 0), "failed": counts.get("failed", 0) + counts.get("not_configured", 0),
                             "delivery_unknown": counts.get("delivery_unknown", 0), "captured": counts.get("captured", 0)},
                "recent": [view(a) for a in recent],
            }


class EmailService:
    def __init__(self, sender: EmailSender, attempts: EmailAttemptRepository | None = None) -> None:
        self._sender = sender
        self._attempts = attempts

    @property
    def sender(self) -> EmailSender:
        return self._sender

    def deliver(self, message: EmailMessage, *, locale: str | None = None, request_id: str | None = None, user_id: int | None = None) -> SendResult:
        try:
            result = send_detailed(self._sender, message)
        except Exception:  # noqa: BLE001 - an adapter bug must not become a 500 or a false success
            result = SendResult("failed", "unknown", "provider_unavailable")
        if self._attempts is not None:
            self._attempts.record(message_type=message.category, result=result, locale=locale, request_id=request_id, user_id=user_id)
        return result
