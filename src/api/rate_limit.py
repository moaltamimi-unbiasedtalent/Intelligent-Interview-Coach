"""Shared request limits with explicit per-bucket outage behavior.

Development defaults to one process. Hosted shared selection requires valid,
authenticated configuration and the pinned optional client; it never silently
substitutes local configuration. Runtime outages retain each bucket's approved
local/deny behavior. Status describes observed enforcement, not qualification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit
import logging
import os
import uuid
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

__all__ = [
    "RateLimitPolicy",
    "RateLimitResult",
    "RateLimiter",
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    "AUTH_POLICIES",
    "COST_POLICIES",
    "SUPPORT_POLICIES",
    "POLICIES",
    "build_rate_limiter",
    "shared_store_active",
    "shared_store_requested",
    "get_rate_limiter",
    "reset_rate_limiter",
    "enforce",
    "check",
    "limiter_status",
    "client_ip",
    "email_key",
    "user_key",
]


@dataclass(frozen=True)
class RateLimitPolicy:
    """One named bucket: at most ``limit`` events per ``window_seconds`` per key."""

    name: str
    limit: int
    window_seconds: int
    scope: str  # "ip" | "account" | "user" | "global" — documentation of the intended key
    # What a SHARED store does when it cannot be reached (W12.4D-P2-A, explicit policy, never implicit):
    #   "local" - degrade to a bounded per-process window (never unlimited, never offline; no longer shared, and ``limiter_status`` says so)
    #   "deny"  - refuse the request (fail closed). Not used by any bucket today; available for a later approved rollout.
    # The UNIT of every bucket is REQUESTS per window (not tokens, not money, not weighted operations).
    on_store_failure: str = "local"

    def __post_init__(self):
        if self.on_store_failure not in {"local", "deny"} or self.limit <= 0 or self.window_seconds <= 0:
            raise ValueError("rate_limit_policy_invalid")


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int  # seconds until the window frees a slot (0 when allowed)
    store_failure_denied: bool = False


# --- Auth policies (§18). Deliberately generous enough for real users, tight enough to stop
#     credential stuffing / enumeration / mail-bombing. Applied per (bucket, key). ---
AUTH_POLICIES: dict[str, RateLimitPolicy] = {
    "auth_login_ip": RateLimitPolicy("auth_login_ip", 20, 300, "ip"),
    "auth_login_account": RateLimitPolicy("auth_login_account", 8, 300, "account"),
    "auth_register_ip": RateLimitPolicy("auth_register_ip", 8, 3600, "ip"),
    "auth_verify_resend": RateLimitPolicy("auth_verify_resend", 5, 3600, "account"),
    "auth_verify_resend_cooldown": RateLimitPolicy("auth_verify_resend_cooldown", 1, 60, "account"),
    "auth_forgot_ip": RateLimitPolicy("auth_forgot_ip", 6, 3600, "ip"),
    "auth_forgot_account": RateLimitPolicy("auth_forgot_account", 4, 3600, "account"),
    "auth_reset_ip": RateLimitPolicy("auth_reset_ip", 12, 3600, "ip"),
    "auth_oidc_start_ip": RateLimitPolicy("auth_oidc_start_ip", 30, 3600, "ip"),
    "auth_global": RateLimitPolicy("auth_global", 2000, 300, "global"),
    # 04E (REQ-BETA-01): bounded invitation-code attempts. Charged on EVERY registration attempt while an invitation is required (so guessing is bounded without a
    # separate "failed only" counter), in addition to auth_register_ip and auth_global. Codes are 256-bit; this bounds abuse of the endpoint, not entropy.
    "auth_invitation_ip": RateLimitPolicy("auth_invitation_ip", 10, 3600, "ip"),
    "auth_invitation_global": RateLimitPolicy("auth_invitation_global", 400, 3600, "global"),
}

# --- Cost / provider policies (§19). Per-user ceilings on costly provider operations. ---
COST_POLICIES: dict[str, RateLimitPolicy] = {
    "cost_agent_user": RateLimitPolicy("cost_agent_user", 60, 3600, "user"),
    "cost_interview_user": RateLimitPolicy("cost_interview_user", 120, 3600, "user"),
    "cost_career_user": RateLimitPolicy("cost_career_user", 60, 3600, "user"),
    "cost_research_user": RateLimitPolicy("cost_research_user", 30, 3600, "user"),
    "cost_upload_user": RateLimitPolicy("cost_upload_user", 40, 3600, "user"),
    "cost_realtime_user": RateLimitPolicy("cost_realtime_user", 12, 3600, "user"),
    # W12.4E: server-side speech (a hard per-user ceiling; the providers are not authorized in this wave).
    "cost_speech_stt_user": RateLimitPolicy("cost_speech_stt_user", 60, 3600, "user"),
    "cost_speech_tts_user": RateLimitPolicy("cost_speech_tts_user", 120, 3600, "user"),
    "cost_global": RateLimitPolicy("cost_global", 5000, 3600, "global"),
}

# --- Support policies (W10.3). Generous per-user ceilings that only stop automated flooding; per-process
# (in-memory) unless a shared store is active, exactly like every other bucket here. ---
SUPPORT_POLICIES: dict[str, RateLimitPolicy] = {
    "support_create_user": RateLimitPolicy("support_create_user", 10, 3600, "user"),
    "support_reply_user": RateLimitPolicy("support_reply_user", 60, 3600, "user"),
    # W10.10: spam protection for candidate privacy requests and legal acceptance (same in-memory/shared-store semantics as the rest).
    "privacy_request_user": RateLimitPolicy("privacy_request_user", 5, 3600, "user"),
    "legal_accept_user": RateLimitPolicy("legal_accept_user", 30, 3600, "user"),
}

# --- Security policies (W10.13). Per-Admin ceilings on step-up and role-change actions (per-process unless a shared store is active, like every bucket). ---
SECURITY_POLICIES: dict[str, RateLimitPolicy] = {
    "stepup_user": RateLimitPolicy("stepup_user", 5, 300, "user"),
    "invitation_issue_user": RateLimitPolicy("invitation_issue_user", 60, 3600, "user"),      # 04E: Admin issuing invitations (never bulk)
    "admin_bulk_user_actions": RateLimitPolicy("admin_bulk_user_actions", 10, 3600, "user"),   # 03C bulk: executed batches per administrator (previews are read-only)
    "role_request_user": RateLimitPolicy("role_request_user", 20, 3600, "user"),
    "role_approve_user": RateLimitPolicy("role_approve_user", 30, 3600, "user"),
    # W12.4C: a real provider send to the administrator's OWN address; a hard, small ceiling (never bulk mail).
    "email_test_user": RateLimitPolicy("email_test_user", 3, 3600, "user"),
    # W12.4D-C: candidate checkout. Bounded per user and per IP (the availability read is public); nothing here moves money.
    "billing_checkout_user": RateLimitPolicy("billing_checkout_user", 10, 3600, "user"),
    "billing_status_ip": RateLimitPolicy("billing_status_ip", 120, 300, "ip"),
    "billing_webhook_ip": RateLimitPolicy("billing_webhook_ip", 600, 60, "ip"),
    # 05D: Brevo delivery events (signature-authenticated, non-operational while the code gate is False). Bounded per IP like the billing webhook.
    "mail_webhook_ip": RateLimitPolicy("mail_webhook_ip", 600, 60, "ip"),
    "billing_recovery_user": RateLimitPolicy("billing_recovery_user", 20, 3600, "user"),
    "billing_summary_user": RateLimitPolicy("billing_summary_user", 120, 300, "user"),
}

POLICIES: dict[str, RateLimitPolicy] = {**AUTH_POLICIES, **COST_POLICIES, **SUPPORT_POLICIES, **SECURITY_POLICIES}


class RateLimiter(Protocol):
    """A rate limiter. Implementations must be safe for the deployment's concurrency."""

    distributed: bool

    def hit(self, bucket: str, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        ...

    def reset(self) -> None:
        ...


class InMemoryRateLimiter:
    """Single-process sliding-window limiter (dev/test/single-replica).

    Not shared across workers/replicas — ``distributed`` is False. A production multi-replica
    deployment must supply a shared-store adapter with the same interface.
    """

    distributed = False

    def __init__(self, *, clock=time.monotonic, max_keys=10000) -> None:
        self._clock = clock
        self._events: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()
        self._expiry = {}
        self._max_keys = max_keys

    def hit(self, bucket: str, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        now = self._clock()
        window = policy.window_seconds
        k = (bucket, key)
        with self._lock:
            if k not in self._events and len(self._events) >= self._max_keys:
                for expired in [x for x, deadline in self._expiry.items() if deadline <= now]:
                    self._events.pop(expired, None)
                    self._expiry.pop(expired, None)
                if len(self._events) >= self._max_keys:
                    return RateLimitResult(False, 0, 5)
            self._expiry[k] = now + window
            recent = [t for t in self._events.get(k, []) if now - t < window]
            if len(recent) >= policy.limit:
                oldest = min(recent)
                retry_after = max(1, int(window - (now - oldest)))
                self._events[k] = recent
                return RateLimitResult(allowed=False, remaining=0, retry_after=retry_after)
            recent.append(now)
            self._events[k] = recent
            return RateLimitResult(
                allowed=True, remaining=max(0, policy.limit - len(recent)), retry_after=0)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._expiry.clear()


# Atomic sliding window: trim, count, then add - all inside one Redis script so concurrent replicas
# cannot both slip under the limit. Returns {allowed(1/0), count, oldest_score}.
_REDIS_WINDOW_SCRIPT = """
local k = KEYS[1]
local ts = redis.call('TIME')
local now = tonumber(ts[1]) + tonumber(ts[2]) / 1000000
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', k, 0, now - window)
local c = redis.call('ZCARD', k)
if c >= limit then
  local o = redis.call('ZRANGE', k, 0, 0, 'WITHSCORES')
  return {0, c, o[2], tostring(now)}
end
redis.call('ZADD', k, now, ARGV[4])
redis.call('EXPIRE', k, math.ceil(window) + 1)
return {1, c + 1, 0, tostring(now)}
"""


class RedisRateLimiter:
    """Existing atomic adapter, with private keys and observed outage/recovery state."""

    distributed = True

    def __init__(self, client, *, prefix="ask4mo:rl:", clock=time.time, fallback=None, key_secret=""):
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}:", prefix):
            raise ValueError("rate_limit_namespace_invalid")
        self._client, self._prefix, self._clock = client, prefix, clock
        self._key_secret = key_secret.encode()
        self._fallback = fallback or InMemoryRateLimiter()
        self.degraded, self.reachable = False, None
        self.local_fallbacks = self.fail_closed_refusals = self.recoveries = 0
        self._failure_mode = "unknown"
        self._state_lock = threading.Lock()
        self._last_probe = float("-inf")

    def store_key(self, bucket, key):
        value = json.dumps([bucket, key], separators=(",", ":")).encode()
        hashed = hmac.new(self._key_secret, value, hashlib.sha256).hexdigest()
        return f"{self._prefix}{bucket}:{hashed}"

    def _observe(self, available):
        with self._state_lock:
            if available and self.reachable is False:
                self.recoveries += 1
                logger.info("rate-limit shared enforcement recovered")
            if not available and not self.degraded:
                logger.warning("rate-limit store unavailable; applying the per-bucket failure policy")
            self.reachable, self.degraded = available, not available

    def _evaluate(self, bucket, key, policy):
        now = self._clock()
        values = self._client.eval(_REDIS_WINDOW_SCRIPT, 1, self.store_key(bucket, key),
                                   now, policy.window_seconds, policy.limit, uuid.uuid4().hex)
        # Older injected unit stores expose the original three-value protocol;
        # actual Redis returns its authoritative server time as the fourth value.
        if len(values) not in (3, 4):
            raise ValueError("rate_limit_store_response_invalid")
        allowed, count, oldest = values[:3]
        if len(values) == 4:
            now = float(values[3])
        result = RateLimitResult(bool(int(allowed)), max(0, policy.limit - int(count)) if int(allowed) else 0,
                                 0 if int(allowed) else max(1, math.ceil(policy.window_seconds - (now - float(oldest)))))
        self._observe(True)
        return result

    def hit(self, bucket, key, policy):
        try:
            return self._evaluate(bucket, key, policy)
        except Exception:  # bounded projection only; never log client/URL/key/exception
            self._observe(False)
            with self._state_lock:
                self._failure_mode = policy.on_store_failure
                if policy.on_store_failure == "deny":
                    self.fail_closed_refusals += 1
                else:
                    self.local_fallbacks += 1
            if policy.on_store_failure == "deny":
                return RateLimitResult(False, 0, 5, store_failure_denied=True)
            return self._fallback.hit(bucket, key, policy)

    def probe(self):
        # Exercise the SAME authenticated Lua/ACL path, on one short-lived health
        # key, without charging a product bucket or applying any fallback.
        if time.monotonic() - self._last_probe < 2:
            return
        self._last_probe = time.monotonic()
        try:
            self._evaluate("health", "probe", RateLimitPolicy("health", 1000000, 60, "global"))
        except Exception:
            self._observe(False)

    def reset(self):
        self._fallback.reset()  # tests only; never clear a shared store


# Process-global limiter (single-replica default). Tests override via get/reset.
_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()
_shared_store_requested = False


class RateLimitConfigurationError(RuntimeError):
    """A bounded startup refusal; never includes supplied configuration values."""


def shared_required():
    return os.environ.get("RATE_LIMIT_SHARED_REQUIRED", "").strip().lower() in {"1", "true", "yes", "on"}


def redis_settings():
    from src.core import secrets
    url = (secrets.read_setting("REDIS_URL") or "").strip()
    key_secret = secrets.read_setting("RATE_LIMIT_KEY_SECRET") or ""
    if shared_required():
        for name, resolved in (("REDIS_URL", url), ("RATE_LIMIT_KEY_SECRET", key_secret)):
            explicit = os.environ.get(name, "").strip()
            if explicit and resolved != explicit:
                raise RateLimitConfigurationError("redis_runtime_source_conflict")
    password = None
    filename = os.environ.get("REDIS_PASSWORD_FILE", "").strip()
    if filename:
        try:
            password = Path(filename).read_text().strip()
        except Exception:
            raise RateLimitConfigurationError("redis_credential_file_unavailable") from None
    return url, password, key_secret


def redis_configuration_errors(*, hosted=False):
    """No connection; the same configuration rules used at selection and startup."""
    errors = []
    if os.environ.get("RATE_LIMIT_SHARED_REQUIRED", "").strip().lower() not in {"", "0", "1", "true", "false", "yes", "no", "on", "off"}:
        errors.append("RATE_LIMIT_SHARED_REQUIRED must be a boolean.")
    backend = os.environ.get("RATE_LIMIT_BACKEND", "").strip().lower()
    required = shared_required()
    try:
        url, password, key_secret = redis_settings()
    except RateLimitConfigurationError:
        return ["Shared Redis credential resolution refused."]
    requested = backend in {"redis", "shared"} or bool(url) or required
    if backend not in {"", "in_memory", "redis", "shared"}:
        errors.append("RATE_LIMIT_BACKEND must be 'in_memory', 'redis' or 'shared'.")
    if not requested:
        return errors
    if not url:
        errors.append("Shared store requested but REDIS_URL is not set.")
    try:
        import importlib.util
        if importlib.util.find_spec("redis") is None:
            errors.append("Shared store requested but the 'redis' package is not installed.")
    except (ImportError, ValueError):
        errors.append("Shared store requested but the 'redis' package is not installed.")
    try:
        u = urlsplit(url)
        valid = (u.scheme in {"redis", "rediss"} and u.hostname and not u.query and not u.fragment and
                 (u.path in ("", "/") or bool(re.fullmatch(r"/[0-9]{1,2}", u.path))))
        if u.port is not None and not 1 <= u.port <= 65535:
            valid = False
        if not valid:
            errors.append("Redis URL must use redis/rediss with a host, database number and no query overrides.")
        if hosted or required:
            if backend == "in_memory":
                errors.append("Shared store cannot be combined with an in_memory backend.")
            internal = u.hostname == "redis" and os.environ.get("REDIS_ALLOW_INTERNAL_PLAINTEXT") == "true"
            if u.scheme != "rediss" and not internal:
                errors.append("Hosted Redis requires TLS or explicitly selected internal-only Redis.")
            from urllib.parse import unquote
            if len(password or unquote(u.password or "")) < 32:
                errors.append("Hosted Redis requires a credential of at least 32 characters.")
            if len(key_secret) < 32:
                errors.append("Hosted Redis requires RATE_LIMIT_KEY_SECRET of at least 32 characters.")
            namespace = os.environ.get("RATE_LIMIT_NAMESPACE", "")
            if not re.fullmatch(r"ask4mo:rl:[A-Za-z0-9_.:-]{1,72}:", namespace):
                errors.append("Hosted Redis requires an explicit isolated RATE_LIMIT_NAMESPACE.")
    except (ValueError, TypeError):
        errors.append("Redis URL is invalid.")
    return errors


def make_redis_client(url, *, password=None):
    import redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    return redis.Redis.from_url(url, password=password, socket_timeout=1.0, socket_connect_timeout=1.0,
                                retry=Retry(NoBackoff(), 0), max_connections=16, protocol=2)


def configured_redis_client():
    if redis_configuration_errors(hosted=True):
        raise RateLimitConfigurationError("shared_rate_limit_configuration_invalid")
    url, credential, _key_secret = redis_settings()
    return make_redis_client(url, password=credential)


def build_rate_limiter():
    global _shared_store_requested
    backend = os.environ.get("RATE_LIMIT_BACKEND", "").strip().lower()
    hosted = os.environ.get("API_ENV", "development").strip().lower() not in {"development", "dev", "local", "test", "testing"}
    _shared_store_requested = backend in {"redis", "shared"} or shared_required() or bool(os.environ.get("REDIS_PASSWORD_FILE"))
    try:
        url, password, key_secret = redis_settings()
        _shared_store_requested = backend in {"redis", "shared"} or bool(url) or shared_required()
        if _shared_store_requested:
            errors = redis_configuration_errors(hosted=hosted)
            if errors:
                raise RateLimitConfigurationError("shared_rate_limit_configuration_invalid")
            client = make_redis_client(url, password=password)
            return RedisRateLimiter(client, prefix=os.environ.get("RATE_LIMIT_NAMESPACE", "ask4mo:rl:"), key_secret=key_secret)
    except Exception:
        if hosted or shared_required():
            raise RateLimitConfigurationError("shared_rate_limit_configuration_invalid") from None
        logger.warning("shared rate-limit store requested but unavailable; development uses in-memory limiter")
    return InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                _limiter = build_rate_limiter()
    return _limiter


def reset_rate_limiter(limiter: RateLimiter | None = None) -> None:
    """Test seam: install a fresh limiter (or a supplied one)."""
    global _limiter, _shared_store_requested
    _limiter = limiter if limiter is not None else build_rate_limiter()
    if limiter is not None:
        _shared_store_requested = isinstance(limiter, RedisRateLimiter)


def shared_store_active() -> bool:
    """Whether a shared (distributed) rate-limit store is actually in use right now."""
    lim = get_rate_limiter()
    return isinstance(lim, RedisRateLimiter) and lim.reachable is True and not lim.degraded


def shared_store_requested() -> bool:
    """Whether a shared rate-limit store was requested (for hosting-readiness reporting)."""
    return _shared_store_requested


def client_ip(request: Request) -> str:
    """Best-effort client IP. Honours ``X-Forwarded-For`` ONLY when ``TRUST_PROXY`` is set
    (behind a known reverse proxy); otherwise uses the socket peer (spoof-resistant)."""
    if os.environ.get("TRUST_PROXY", "").strip().lower() in {"1", "true", "yes", "on"}:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def email_key(email: str | None) -> str:
    """A privacy-safe, stable key derived from an email (never the raw address). Identical for
    a given email whether or not an account exists — so limits never leak account existence."""
    normalized = (email or "").strip().lower()
    return hashlib.sha256(f"acct:{normalized}".encode()).hexdigest()[:32]


def user_key(user_id: int) -> str:
    return f"user:{user_id}"


def limiter_status(*, probe=False):
    """Secret-free process observation, not cross-process totals or hosted approval."""
    lim = get_rate_limiter()
    distributed = isinstance(lim, RedisRateLimiter)
    if probe and distributed:
        lim.probe()
    reachable = lim.reachable if distributed else None
    active = distributed and reachable is True and not lim.degraded
    state = "process_local"
    if distributed:
        state = ("recovered_shared" if lim.recoveries else "shared") if active else "configured_unverified"
        if lim.degraded:
            state = {"local": "degraded_local", "deny": "fail_closed"}.get(lim._failure_mode, "unreachable")
    return {"backend": "redis" if distributed else "in_memory", "shared_store_requested": shared_store_requested(),
            "shared_store_active": active, "configured": distributed, "reachable": reachable,
            "degraded": bool(getattr(lim, "degraded", False)), "effectively_distributed": active, "state": state,
            "local_fallbacks": getattr(lim, "local_fallbacks", 0), "fail_closed_refusals": getattr(lim, "fail_closed_refusals", 0),
            "recoveries": getattr(lim, "recoveries", 0)}


def check(bucket: str, key: str, *, limiter: RateLimiter | None = None) -> RateLimitResult:
    """Apply one bucket to one key WITHOUT raising (the caller decides what to do with the answer). Unknown buckets raise KeyError, like ``enforce``."""
    return (limiter or get_rate_limiter()).hit(bucket, key, POLICIES[bucket])


def enforce(bucket: str, key: str, *, limiter: RateLimiter | None = None) -> None:
    """Apply one bucket to one key; raise HTTP 429 (with Retry-After) when exceeded.

    Unknown buckets are a programming error and raise KeyError (fail loud in tests, never
    silently unlimited)."""
    policy = POLICIES[bucket]
    lim = limiter or get_rate_limiter()
    result = lim.hit(bucket, key, policy)
    if not result.allowed:
        raise HTTPException(
            status_code=503 if result.store_failure_denied else 429,
            detail=("Request protection is temporarily unavailable. Please try again." if result.store_failure_denied else
                    "Too many requests. Please wait a moment and try again."),
            headers={"Retry-After": str(result.retry_after)},
        )
