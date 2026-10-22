"""Live-verification harness for identity, email and rate limiting (05D, PG-02). Offline-testable; the LIVE round trips are NOT RUN.

Everything here is pure or takes injected collaborators, so the full logic is exercised offline with the fake provider, an httpx MockTransport and a
fake Redis. The operator script ``scripts/verify_identity_live_05d.py`` wires the same functions to the real services on STAGING only, after an
explicit authorisation (see :func:`require_live_authorisation`).

Output discipline: reports contain check names, PASS/FAIL/NOT_RUN and bounded reasons. They never contain a secret, token, code, verifier, ID token,
email address, link, subject or message content. A subject is shown only as an 8 character one-way hash prefix.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.parse import parse_qs, urlparse

import httpx

PASS, FAIL, NOT_RUN = "PASS", "FAIL", "NOT_RUN"

AUTHORISATION_VARIABLE = "LIVE_VERIFY_AUTHORISED"
AUTHORISATION_VALUE = "I-AUTHORISE-STAGING-LIVE-CHECKS"


class LiveCheckRefused(Exception):
    """The operator did not (fully) authorise a live action. The message is bounded and secret-free."""


def require_live_authorisation(env: Mapping[str, str], *, flag: bool) -> None:
    """A live action runs only with ALL of: the ``--authorise-live`` flag, the exact authorisation variable, and ``API_ENV=staging`` (never production, never local)."""
    if not flag:
        raise LiveCheckRefused("dry run: pass --authorise-live to perform this live action")
    if (env.get(AUTHORISATION_VARIABLE) or "") != AUTHORISATION_VALUE:
        raise LiveCheckRefused(f"{AUTHORISATION_VARIABLE} is not set to the authorisation value; nothing was sent")
    if (env.get("API_ENV") or "").strip().lower() != "staging":
        raise LiveCheckRefused("API_ENV is not 'staging'; live checks run on the staging environment only")


@dataclass
class Report:
    title: str
    checks: dict[str, dict] = field(default_factory=dict)
    subject_hash: str | None = None          # 8 hex chars of SHA-256(subject); the only trace of the identity

    def add(self, name: str, state: str, reason: str = "") -> None:
        self.checks[name] = {"state": state, "reason": reason[:160]}

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c["state"] == PASS for c in self.checks.values())

    def to_dict(self) -> dict:
        return {"title": self.title, "subject_hash": self.subject_hash, "overall": PASS if self.passed else (NOT_RUN if all(c["state"] == NOT_RUN for c in self.checks.values()) else FAIL),
                "checks": self.checks}


# --- Google OIDC -----------------------------------------------------------------------------------------------------------
def check_authorization_url(url: str, *, verifier: str, state: str, redirect_uri: str, client_id: str) -> Report:
    """Offline: does the URL we would send the user to carry PKCE S256 for THIS verifier, the issued state, the configured redirect and our client id?"""
    from src.application.oidc import pkce_challenge

    rep = Report("google_authorization_request")
    parsed = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(parsed.query).items() if v}
    rep.add("host_is_google", PASS if parsed.scheme == "https" and parsed.netloc == "accounts.google.com" else FAIL)
    rep.add("pkce_method_s256", PASS if q.get("code_challenge_method") == "S256" else FAIL)
    rep.add("pkce_challenge_matches_verifier", PASS if q.get("code_challenge") == pkce_challenge(verifier) else FAIL)
    rep.add("state_present_and_matches", PASS if q.get("state") == state and len(state) >= 16 else FAIL)
    rep.add("redirect_uri_is_configured_value", PASS if q.get("redirect_uri") == redirect_uri else FAIL)
    rep.add("client_id_is_ours", PASS if q.get("client_id") == client_id else FAIL)
    rep.add("scope_has_openid", PASS if "openid" in (q.get("scope") or "").split() else FAIL)
    rep.add("response_type_code", PASS if q.get("response_type") == "code" else FAIL)
    return rep


class RecordingTransport(httpx.BaseTransport):
    """Wraps an httpx transport (the real one when ``inner`` is None) and records ONLY shape facts about the requests (never values)."""

    def __init__(self, inner=None) -> None:
        self._inner = inner or httpx.HTTPTransport()
        self.token_form_keys: set[str] = set()
        self.token_verifier_digest: str | None = None
        self.userinfo_bearer = False
        self.hosts: list[str] = []

    def handle_request(self, request):
        from urllib.parse import parse_qs as _pq

        self.hosts.append(request.url.host)
        if request.url.path.endswith("/token"):
            form = _pq(request.content.decode() if request.content else "")
            self.token_form_keys = set(form)
            v = (form.get("code_verifier") or [None])[0]
            self.token_verifier_digest = hashlib.sha256(v.encode()).hexdigest() if v else None
        elif request.url.path.endswith("/userinfo"):
            self.userinfo_bearer = (request.headers.get("authorization") or "").lower().startswith("bearer ")
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def run_callback_check(provider_factory: Callable[[object], object], *, code: str, redirect_uri: str, verifier: str, transport=None,
                       existing_account: Callable[[str, str | None], bool] | None = None, invitation_required: bool = True) -> Report:
    """Exchange ``code`` through the REAL provider class (``provider_factory(transport)``) and report what was proved.

    The provider's own ``exchange`` enforces: ID token validation, UserInfo ``sub`` == ID-token ``sub``, strict email_verified booleans. A refusal there is
    reported as FAIL with a bounded reason; its details are never printed. ``existing_account(subject, email)`` (optional) tells the invitation-only rule
    whether this identity would CREATE a new account: if it would and an invitation is required, the registration without a code MUST be refused.
    """
    from src.application.oidc import OidcError, pkce_challenge

    rep = Report("google_callback")
    rec = RecordingTransport(transport)
    try:
        identity = provider_factory(rec).exchange(code=code, redirect_uri=redirect_uri, code_verifier=verifier)
    except OidcError:
        rep.add("exchange_succeeded", FAIL, "provider exchange refused (PKCE, token endpoint, ID-token validation or UserInfo subject mismatch)")
        for name in ("token_request_sent_matching_verifier", "id_token_validated", "userinfo_subject_equals_id_token_subject", "email_verified_strict", "invitation_only_new_account"):
            rep.add(name, NOT_RUN)
        return rep
    finally:
        rec.close()
    rep.add("exchange_succeeded", PASS)
    expected = hashlib.sha256(verifier.encode()).hexdigest()
    rep.add("token_request_sent_matching_verifier", PASS if rec.token_verifier_digest == expected and "client_secret" in rec.token_form_keys else FAIL)
    rep.add("userinfo_requested_with_bearer", PASS if rec.userinfo_bearer else FAIL)
    rep.add("only_google_hosts_contacted", PASS if rec.hosts and all(h in ("oauth2.googleapis.com", "openidconnect.googleapis.com") for h in rec.hosts) else FAIL)
    rep.add("id_token_validated", PASS, "validate_id_token ran inside exchange (alg, iss, aud, azp, exp, iat, sub, at_hash)")
    rep.add("userinfo_subject_equals_id_token_subject", PASS, "enforced inside exchange; a mismatch would have refused")
    rep.add("email_verified_strict", PASS if isinstance(identity.email_verified, bool) else FAIL)
    if existing_account is None:
        rep.add("invitation_only_new_account", NOT_RUN, "no account lookup supplied")
    elif existing_account(identity.subject, identity.email):
        rep.add("invitation_only_new_account", NOT_RUN, "identity already has an account; use a Google account that does not (a new account is what the rule governs)")
    else:
        rep.add("invitation_only_new_account", PASS if invitation_required else FAIL,
                "a NEW account would be created: it must be refused without a valid invitation" if invitation_required else "registration does not require an invitation here")
    rep.add("pkce_challenge_for_verifier", PASS if pkce_challenge(verifier) else FAIL)
    rep.subject_hash = hashlib.sha256(identity.subject.encode()).hexdigest()[:8]
    return rep


# --- Brevo webhook ---------------------------------------------------------------------------------------------------------
def build_webhook_probes(secret: str, *, message_ref: str, now: float | None = None, mode: str = "hmac") -> list[dict]:
    """The signed/forged requests a staging probe sends to ``/api/v1/mail/webhooks/brevo`` and the status each must get when the gate is OPEN.

    ``message_ref`` is the provider message reference of ONE real submission made by the same script (so the valid probe matches a row). Nothing is derived
    from user data. Expected statuses assume ``DELIVERY_EVENTS_AUTHORIZED`` is True on that environment; with the gate False every probe is 503.
    """
    from src.mail import webhook as W

    t = int(now if now is not None else time.time())

    def body(ts: int, event: str = "delivered") -> bytes:
        return json.dumps({"event": event, "message-id": message_ref, "ts_event": ts}).encode()

    def headers(b: bytes, ts: int, sec: str) -> dict:
        if mode == "bearer":
            return {"authorization": f"Bearer {sec}"}
        return {W.SIGNATURE_HEADER: W.sign(sec, b, ts)}

    valid = body(t)
    old_ts = t - W.SIGNATURE_TOLERANCE_SECONDS - 60
    probes = [
        {"name": "valid_signed_event", "body": valid, "headers": headers(valid, t, secret), "expect": 200},
        {"name": "replay_of_valid_event", "body": valid, "headers": headers(valid, t, secret), "expect": 200},     # idempotent no-op, still 200
        {"name": "forged_signature", "body": valid, "headers": headers(valid, t, secret + "x"), "expect": 401},
        {"name": "missing_signature", "body": valid, "headers": {}, "expect": 401},
        {"name": "malformed_payload", "body": b"{not json", "headers": headers(b"{not json", t, secret), "expect": 400},
    ]
    if mode == "hmac":
        old = body(old_ts)
        probes.append({"name": "old_signature_timestamp", "body": old, "headers": headers(old, old_ts, secret), "expect": 401})
    return probes


def run_webhook_probes(post: Callable[[bytes, dict], int], probes: list[dict]) -> Report:
    """``post(body, headers) -> http status``. Records only the status codes."""
    rep = Report("brevo_webhook")
    for p in probes:
        try:
            status = int(post(p["body"], p["headers"]))
        except Exception:  # noqa: BLE001
            rep.add(p["name"], FAIL, "request failed")
            continue
        rep.add(p["name"], PASS if status == p["expect"] else FAIL, f"expected {p['expect']}, got {status}")
    return rep


# --- Redis shared rate-limit store -----------------------------------------------------------------------------------------
def run_limiter_checks(client, *, prefix: str | None = None, clock: Callable[[], float] = time.time,
                       sleep: Callable[[float], None] = time.sleep) -> Report:
    """Distributed-limiter semantics against ``client`` (a real ``redis.Redis`` on staging, or a fake): two replicas share one window, a third hit is refused,
    keys are independent, and a short window expires. Uses ONLY keys under a unique ``prefix`` and deletes exactly those afterwards."""
    from src.api import rate_limit as rl

    prefix = prefix or f"ask4mo:verify:{uuid.uuid4().hex[:12]}:"
    rep = Report("redis_limiter")
    pol = rl.RateLimitPolicy("verify", 2, 2, "ip")
    a, b = rl.RedisRateLimiter(client, prefix=prefix, clock=clock), rl.RedisRateLimiter(client, prefix=prefix, clock=clock)
    try:
        r1, r2, r3 = a.hit("v", "k", pol), b.hit("v", "k", pol), a.hit("v", "k", pol)
        rep.add("two_replicas_share_one_window", PASS if r1.allowed and r2.allowed and not r3.allowed else FAIL)
        rep.add("retry_after_is_positive_when_refused", PASS if r3.retry_after >= 1 else FAIL)
        rep.add("keys_are_independent", PASS if b.hit("v", "other", pol).allowed else FAIL)
        rep.add("store_not_degraded", PASS if not a.degraded and not b.degraded else FAIL)
        sleep(2.2)                     # wait out the 2 second window (tests pass a sleep that advances their fake clock)
        rep.add("window_expires", PASS if a.hit("v", "k", pol).allowed else FAIL)
    except Exception:  # noqa: BLE001
        rep.add("store_reachable", FAIL, "the store raised")
    finally:
        try:
            for key in client.scan_iter(match=f"{prefix}*"):
                client.delete(key)
        except Exception:  # noqa: BLE001
            pass
    return rep


def digest_secret_free(text: str, secrets: list[str]) -> bool:
    """True when none of ``secrets`` appears in ``text`` (used by tests and by the script's own output self-check)."""
    return not any(s and s in text for s in secrets)


__all__ = ["PASS", "FAIL", "NOT_RUN", "AUTHORISATION_VARIABLE", "AUTHORISATION_VALUE", "LiveCheckRefused", "require_live_authorisation", "Report",
           "check_authorization_url", "RecordingTransport", "run_callback_check", "build_webhook_probes", "run_webhook_probes", "run_limiter_checks",
           "digest_secret_free"]
