"""D1-INT01C synthetic OAuth qualification; no live network or credentials."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from src.mail.gmail_oauth import GMAIL_SEND_SCOPE, GmailOAuthCredentials, GmailOAuthTokenSource

SENDER = "sender@example.test"
CLIENT_ID = "synthetic-client-id"
CLIENT_SECRET = "synthetic-client-secret"
REFRESH = "synthetic-refresh-token"
TOKEN = "synthetic-access-token"


def credentials(**overrides):
    values = dict(client_id=SecretStr(CLIENT_ID), client_secret=SecretStr(CLIENT_SECRET),
                  refresh_token=SecretStr(REFRESH))
    values.update(overrides)
    return GmailOAuthCredentials(**values)


def source(handler, **overrides):
    options = dict(credentials=credentials(), sender_email=SENDER, authorized_mailbox=SENDER,
                   granted_scopes=(GMAIL_SEND_SCOPE,), synthetic_authorized=True,
                   transport=httpx.MockTransport(handler))
    options.update(overrides)
    return GmailOAuthTokenSource(**options)


def valid_response(**values):
    return httpx.Response(200, json={"token_type": "Bearer", "access_token": TOKEN,
                                     "expires_in": 3600, "scope": GMAIL_SEND_SCOPE, **values})


def test_refresh_posts_exact_send_only_scope_no_redirect_and_no_retry(caplog):
    requests = []
    caplog.set_level(logging.DEBUG)
    def handler(request):
        requests.append(request)
        return valid_response()
    got = source(handler).access_token(timeout=10.0)
    assert got == TOKEN and len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://oauth2.googleapis.com/token"
    assert request.method == "POST"
    assert parse_qs(request.content.decode()) == {"client_id": [CLIENT_ID], "client_secret": [CLIENT_SECRET],
                                                    "refresh_token": [REFRESH], "grant_type": ["refresh_token"]}
    for value in (CLIENT_ID, CLIENT_SECRET, REFRESH, TOKEN, SENDER):
        assert value not in caplog.text


def test_no_activation_no_transport_no_grant_no_mailbox_never_calls_transport():
    for overrides in (
        {"synthetic_authorized": False}, {"transport": None}, {"granted_scopes": ()},
        {"granted_scopes": (GMAIL_SEND_SCOPE, "https://mail.google.com/")},
        {"authorized_mailbox": None}, {"authorized_mailbox": "other@example.test"},
        {"sender_email": "unsafe\naddress@example.test"},
    ):
        s = source(lambda _: pytest.fail("token endpoint must not be called"), **overrides)
        assert s.access_token(timeout=10.0) is None


@pytest.mark.parametrize("missing", ["client_id", "client_secret", "refresh_token"])
def test_missing_secret_fails_closed_without_request(missing):
    assert source(lambda _: pytest.fail("must refuse"), credentials=credentials(**{missing: None})).access_token(timeout=10.0) is None


@pytest.mark.parametrize("timeout", [0, -1, 10.01, True, "10"])
def test_invalid_timeout_fails_closed(timeout):
    assert source(lambda _: pytest.fail("must refuse")).access_token(timeout=timeout) is None


@pytest.mark.parametrize("response", [httpx.Response(400, json={"error": "invalid_grant"}),
                                        httpx.Response(401), httpx.Response(403)])
def test_invalid_grant_latches_until_explicit_reset(response):
    calls = []
    def handler(req):
        calls.append(req)
        return response if len(calls) == 1 else valid_response()
    s = source(handler)
    assert s.access_token(timeout=10.0) is None
    assert s.access_token(timeout=10.0) is None and len(calls) == 1
    s.invalidate()
    assert s.access_token(timeout=10.0) == TOKEN and len(calls) == 2


@pytest.mark.parametrize("response", [httpx.Response(500), httpx.Response(429),
                                        httpx.Response(302, headers={"location": "https://example.invalid"}),
                                        httpx.ReadTimeout("secret error")])
def test_transient_failure_is_unknown_without_automatic_retry(response):
    calls = []
    def handler(req):
        calls.append(req)
        if isinstance(response, Exception):
            raise response
        return response
    assert source(handler).access_token(timeout=10.0) is None
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [
    {"token_type": "bearer", "access_token": TOKEN, "expires_in": 3600, "scope": "https://mail.google.com/"},
    {"token_type": "MAC", "access_token": TOKEN, "expires_in": 3600},
    {"token_type": "Bearer", "access_token": TOKEN, "expires_in": False},
    {"token_type": "Bearer", "access_token": TOKEN, "expires_in": 30},
    {"token_type": "Bearer", "access_token": "unsafe\nsecret", "expires_in": 3600},
    {"token_type": "Bearer", "access_token": TOKEN, "expires_in": 3600, "scope": GMAIL_SEND_SCOPE + " https://mail.google.com/"},
    ["not-a-dict"],
])
def test_invalid_token_response_refused(payload):
    assert source(lambda _: httpx.Response(200, json=payload)).access_token(timeout=10) is None


def test_cache_single_refresh_and_expiry():
    now = [100.0]
    calls = []
    def handler(req):
        calls.append(req)
        return valid_response()
    s = source(handler, clock=lambda: now[0])
    assert s.access_token(timeout=10) == TOKEN
    now[0] = 1000
    assert s.access_token(timeout=10) == TOKEN and len(calls) == 1
    now[0] = 3700
    assert s.access_token(timeout=10) == TOKEN and len(calls) == 2


def test_parallel_refresh_is_single_flight():
    calls = []
    def handler(request):
        calls.append(request)
        return valid_response()
    s = source(handler)
    with ThreadPoolExecutor(max_workers=8) as workers:
        tokens = list(workers.map(lambda _: s.access_token(timeout=10), range(16)))
    assert tokens == [TOKEN] * 16 and len(calls) == 1


def test_generic_secret_store_cannot_be_substituted():
    class Store:
        def get_for_runtime(self, name):
            pytest.fail("generic secret store must not be accessed")
    assert source(lambda _: pytest.fail("must refuse"), credentials=Store()).access_token(timeout=10) is None


@pytest.mark.parametrize("field", ["client_id", "client_secret", "refresh_token"])
def test_only_secretstr_accepted(field):
    assert source(lambda _: pytest.fail("must refuse"), credentials=credentials(**{field: "raw-secret"})).access_token(timeout=10) is None


def test_credentials_are_immutable_and_redacted():
    from dataclasses import FrozenInstanceError
    bundle = credentials()
    with pytest.raises(FrozenInstanceError):
        bundle.client_id = SecretStr("other")
    assert CLIENT_ID not in repr(bundle) and CLIENT_SECRET not in repr(bundle) and REFRESH not in repr(bundle)


def test_broken_secret_wrapper_fails_closed_without_leaking(caplog):
    class BrokenSecret(SecretStr):
        def get_secret_value(self):
            raise RuntimeError('synthetic-secret-canary')
    caplog.set_level(logging.DEBUG)
    s = source(lambda _: pytest.fail('must refuse'), credentials=credentials(client_secret=BrokenSecret('canary')))
    assert s.access_token(timeout=10) is None
    assert 'synthetic-secret-canary' not in caplog.text
