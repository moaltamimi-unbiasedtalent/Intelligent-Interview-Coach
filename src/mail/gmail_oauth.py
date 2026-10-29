"""Synthetic-only, mailbox-bound Gmail OAuth refresh token source (D1-INT01C).

The production sender factory remains disabled. This implementation requires an
explicit synthetic opt-in and httpx.MockTransport; it cannot contact Google.
Mailbox and real credential provisioning, custody approval, and live activation
remain separate release gates. Secrets are read via SecretStore runtime reads.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Protocol

import httpx
from pydantic import SecretStr

from src.mail.sender import _valid_sender_identity

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_CLIENT_ID = "GMAIL_OAUTH_CLIENT_ID"
_CLIENT_SECRET = "GMAIL_OAUTH_CLIENT_SECRET"
_REFRESH_TOKEN = "GMAIL_OAUTH_REFRESH_TOKEN"


class RuntimeSecretReader(Protocol):
    """The existing SecretStore read interface; never an Admin secret-read API."""

    def get_for_runtime(self, secret_name: str) -> SecretStr | None: ...


class GmailOAuthTokenSource:
    """One bounded synthetic refresh at a time; no real transport or live activation.

    granted_scopes is trusted authorization evidence provided by the caller,
    not an unverified claim made by the refresh response. A future live adapter
    must qualify the OAuth grant and mailbox identity independently.
    """

    TIMEOUT_MAX_SECONDS = 10.0

    def __init__(
        self,
        *,
        secrets: RuntimeSecretReader,
        sender_email: str,
        authorized_mailbox: str | None = None,
        granted_scopes: tuple[str, ...] = (),
        synthetic_authorized: bool = False,
        transport: httpx.MockTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._secrets = secrets
        self._sender_email = sender_email
        self._authorized_mailbox = authorized_mailbox
        self._scopes = granted_scopes
        self._synthetic_authorized = synthetic_authorized
        self._transport = transport
        self._clock = clock
        self._lock = threading.Lock()
        self._token: str | None = None
        self._valid_until = 0.0
        self._reauthorization_required = False

    def invalidate(self) -> None:
        """Drop cached token after explicit synthetic rotation or revocation."""
        with self._lock:
            self._token = None
            self._valid_until = 0.0
            self._reauthorization_required = False

    def _eligible(self) -> bool:
        return (
            self._synthetic_authorized is True
            and type(self._transport) is httpx.MockTransport
            and _valid_sender_identity(self._sender_email)
            and isinstance(self._authorized_mailbox, str)
            and _valid_sender_identity(self._authorized_mailbox)
            and self._sender_email.casefold() == self._authorized_mailbox.casefold()
            and self._scopes == (GMAIL_SEND_SCOPE,)
        )

    def _read_secret(self, name: str) -> str | None:
        try:
            secret = self._secrets.get_for_runtime(name)
            if not isinstance(secret, SecretStr):
                return None
            raw = secret.get_secret_value()
            if not raw or len(raw) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in raw):
                return None
            return raw
        except Exception:  # noqa: BLE001 - secret-store failures never reach logs
            return None

    def access_token(self, *, timeout: float) -> str | None:
        """Return a cached token or perform exactly one synthetic refresh.

        Never returns secrets or raw OAuth errors in exceptions/logging. Invalid
        grants latch closed until explicit invalidation following reauthorization.
        """
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not 0 < timeout <= self.TIMEOUT_MAX_SECONDS
            or not self._eligible()
        ):
            return None
        with self._lock:
            if self._reauthorization_required:
                return None
            now = self._clock()
            if self._token is not None and now < self._valid_until:
                return self._token
            self._token = None
            self._valid_until = 0.0
            client_id = self._read_secret(_CLIENT_ID)
            client_secret = self._read_secret(_CLIENT_SECRET)
            refresh_token = self._read_secret(_REFRESH_TOKEN)
            if not all((client_id, client_secret, refresh_token)):
                return None
            try:
                with httpx.Client(timeout=timeout, follow_redirects=False, transport=self._transport) as client:
                    response = client.post(
                        _TOKEN_ENDPOINT,
                        data={"client_id": client_id, "client_secret": client_secret,
                              "refresh_token": refresh_token, "grant_type": "refresh_token"},
                    )
                if response.status_code in (400, 401, 403):
                    # A rejected grant requires explicit remediation, not retries.
                    self._reauthorization_required = True
                    return None
                if response.status_code != 200:
                    return None
                data = response.json()
                if not isinstance(data, dict) or data.get("token_type", "").lower() != "bearer":
                    return None
                if "scope" in data and (
                    not isinstance(data["scope"], str)
                    or tuple(data["scope"].split()) != (GMAIL_SEND_SCOPE,)
                ):
                    return None
                access = data.get("access_token")
                expires = data.get("expires_in")
                if (
                    not isinstance(access, str) or not access or len(access) > 4096
                    or any(ord(c) < 33 or ord(c) > 126 for c in access)
                    or type(expires) is not int or not 120 <= expires <= 86400
                ):
                    return None
                self._token = access
                self._valid_until = self._clock() + expires - min(60, expires // 10)
                return access
            except Exception:  # noqa: BLE001 - never expose OAuth or credential text
                return None
