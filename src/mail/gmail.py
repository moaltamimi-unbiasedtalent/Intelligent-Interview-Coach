"""Disabled-by-default Gmail API submission adapter.

Credential acquisition is injected; provisioning and activation are separate gates.
No provider response, address, message content, or credential is logged.
"""
from __future__ import annotations

import base64
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import httpx

from src.mail.sender import (
    EmailMessage, SendResult, STATUS_ACCEPTED, STATUS_FAILED, STATUS_NOT_CONFIGURED,
    STATUS_UNKNOWN, _valid_sender_identity,
)


class GmailTokenSource(Protocol):
    def access_token(self, *, timeout: float) -> str | None:
        """Return a mailbox-scoped OAuth token; respect the supplied timeout."""
        ...


class GmailEmailSender:
    """Submit exactly once; an accepted submission does not establish delivery."""

    ENDPOINT = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
    TIMEOUT_SECONDS = 10.0

    def __init__(self, *, sender_email: str, token_source: GmailTokenSource, transport=None):
        if not _valid_sender_identity(sender_email):
            raise ValueError('Invalid configured sender')
        self._sender_email = sender_email
        self._token_source = token_source
        self._transport = transport

    def send(self, message: EmailMessage) -> bool:
        return self.send_detailed(message).accepted

    def send_detailed(self, message: EmailMessage) -> SendResult:
        try:
            token = self._token_source.access_token(timeout=self.TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 - never expose credential-provider exception text
            return SendResult(STATUS_NOT_CONFIGURED, 'gmail', 'provider_not_configured')
        if not isinstance(token, str) or not token or any(c in token for c in '\r\n'):
            return SendResult(STATUS_NOT_CONFIGURED, 'gmail', 'provider_not_configured')
        try:
            mime = MimeMessage()
            mime['From'] = self._sender_email
            mime['To'] = message.to
            mime['Subject'] = message.subject
            mime.set_content(message.body)
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode('ascii')
        except (ValueError, TypeError):
            return SendResult(STATUS_FAILED, 'gmail', 'message_rejected')
        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS, follow_redirects=False, transport=self._transport) as client:
                response = client.post(self.ENDPOINT, headers={'Authorization': 'Bearer ' + token}, json={'raw': raw})
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            return SendResult(STATUS_FAILED, 'gmail', 'provider_unavailable')
        except Exception:  # noqa: BLE001 - submission may have started; never retry
            return SendResult(STATUS_UNKNOWN, 'gmail', 'delivery_unknown')
        code = response.status_code
        if code == 200:
            # Do not retain untrusted provider response content or identifiers.
            return SendResult(STATUS_ACCEPTED, 'gmail')
        if code == 429:
            return SendResult(STATUS_FAILED, 'gmail', 'rate_limited')
        if code == 403:
            try:
                reasons = {e.get('reason') for e in response.json().get('error', {}).get('errors', []) if isinstance(e, dict)}
            except Exception:  # noqa: BLE001 - untrusted provider content
                reasons = set()
            category = 'rate_limited' if reasons & {'rateLimitExceeded', 'userRateLimitExceeded'} else 'provider_auth_failed'
            return SendResult(STATUS_FAILED, 'gmail', category)
        if code == 401:
            return SendResult(STATUS_FAILED, 'gmail', 'provider_auth_failed')
        if code >= 500 or 300 <= code < 400:
            return SendResult(STATUS_UNKNOWN, 'gmail', 'delivery_unknown')
        return SendResult(STATUS_FAILED, 'gmail', 'message_rejected')
