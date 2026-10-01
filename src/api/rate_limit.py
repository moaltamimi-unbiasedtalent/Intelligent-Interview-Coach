"""Shared rate-limiting for hosted operation (Capstone P8).

A small, provider-neutral rate-limit seam used by both abuse-sensitive auth routes (§18) and
costly provider operations (§19). It replaces "no limits at all" with bounded, testable
controls, while staying honest about the deployment topology (§20):

- ``InMemoryRateLimiter`` is a single-process sliding-window limiter. It is correct for a
  single replica (the documented default staging topology) and for tests. It is NOT shared
  across workers/replicas — do not claim distributed safety from it.
- ``RateLimiter`` is the abstraction. ``RedisRateLimiter`` is a shared-store adapter for multi-replica
  deployments (atomic sliding window in Redis). It is OPTIONAL and OFF by default: it is selected only when
  ``RATE_LIMIT_BACKEND=redis`` (or ``shared``) AND ``REDIS_URL`` is set AND the ``redis`` package is installed.
  It has been unit-tested against a fake client only and has NOT been validated against a live Redis, so
  distributed limiting must not be claimed as live. ``build_rate_limiter`` otherwise falls back to the
  in-memory adapter and records that a shared store was requested but is not active.

Keying is privacy-safe: an email-derived key is hashed (never stored raw), and auth limits are
applied identically whether or not an account exists, so rate-limit behaviour never leaks
account existence (§18 anti-enumeration).
"""

from __future__ import annotations

import hashlib
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
    "POLICIES",
    "build_rate_limiter",
    "shared_store_active",
    "shared_store_requested",
    "get_rate_limiter",
    "reset_rate_limiter",
    "enforce",
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


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int  # seconds until the window frees a slot (0 when allowed)


# --- Auth policies (§18). Deliberately generous enough for real users, tight enough to stop
#     credential stuffing / enumeration / mail-bombing. Applied per (bucket, key). ---
AUTH_POLICIES: dict[str, RateLimitPolicy] = {
    "auth_login_ip": RateLimitPolicy("auth_login_ip", 20, 300, "ip"),
    "auth_login_account": RateLimitPolicy("auth_login_account", 8, 300, "account"),
    "auth_register_ip": RateLimitPolicy("auth_register_ip", 8, 3600, "ip"),
    "auth_verify_resend": RateLimitPolicy("auth_verify_resend", 5, 3600, "account"),
    "auth_forgot_ip": RateLimitPolicy("auth_forgot_ip", 6, 3600, "ip"),
    "auth_forgot_account": RateLimitPolicy("auth_forgot_account", 4, 3600, "account"),
    "auth_reset_ip": RateLimitPolicy("auth_reset_ip", 12, 3600, "ip"),
    "auth_oidc_start_ip": RateLimitPolicy("auth_oidc_start_ip", 30, 3600, "ip"),
    "auth_global": RateLimitPolicy("auth_global", 2000, 300, "global"),
}

# --- Cost / provider policies (§19). Per-user ceilings on costly provider operations. ---
COST_POLICIES: dict[str, RateLimitPolicy] = {
    "cost_agent_user": RateLimitPolicy("cost_agent_user", 60, 3600, "user"),
    "cost_interview_user": RateLimitPolicy("cost_interview_user", 120, 3600, "user"),
    "cost_career_user": RateLimitPolicy("cost_career_user", 60, 3600, "user"),
    "cost_research_user": RateLimitPolicy("cost_research_user", 30, 3600, "user"),
    "cost_upload_user": RateLimitPolicy("cost_upload_user", 40, 3600, "user"),
    "cost_realtime_user": RateLimitPolicy("cost_realtime_user", 12, 3600, "user"),
    "cost_global": RateLimitPolicy("cost_global", 5000, 3600, "global"),
}

POLICIES: dict[str, RateLimitPolicy] = {**AUTH_POLICIES, **COST_POLICIES}


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

    def __init__(self, *, clock=time.monotonic) -> None:
        self._clock = clock
        self._events: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()

    def hit(self, bucket: str, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        now = self._clock()
        window = policy.window_seconds
        k = (bucket, key)
        with self._lock:
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


# Atomic sliding window: trim, count, then add - all inside one Redis script so concurrent replicas
# cannot both slip under the limit. Returns {allowed(1/0), count, oldest_score}.
_REDIS_WINDOW_SCRIPT = """
local k = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', k, 0, now - window)
local c = redis.call('ZCARD', k)
if c >= limit then
  local o = redis.call('ZRANGE', k, 0, 0, 'WITHSCORES')
  return {0, c, o[2]}
end
redis.call('ZADD', k, now, ARGV[4])
redis.call('EXPIRE', k, math.ceil(window) + 1)
return {1, c + 1, 0}
"""


class RedisRateLimiter:
    """Shared sliding-window limiter over Redis (multi-replica). NOT validated against a live Redis.

    ``client`` is any object exposing ``eval(script, numkeys, *keys_and_args)`` (the ``redis`` client).
    If Redis errors at runtime the limiter degrades to a per-process in-memory limiter (logged), so an
    infrastructure fault never takes sign-in or the product offline; while degraded it is no longer shared.
    """

    distributed = True

    def __init__(self, client, *, prefix: str = "ask4mo:rl:", clock=time.time,
                 fallback: "RateLimiter | None" = None) -> None:
        self._client = client
        self._prefix = prefix
        self._clock = clock
        self._fallback = fallback or InMemoryRateLimiter()
        self.degraded = False

    def hit(self, bucket: str, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        now = self._clock()
        try:
            allowed, count, oldest = self._client.eval(
                _REDIS_WINDOW_SCRIPT, 1, f"{self._prefix}{bucket}:{key}",
                now, policy.window_seconds, policy.limit, f"{now}:{uuid.uuid4().hex}")
        except Exception:  # noqa: BLE001 - never let the limiter backend take the product down
            if not self.degraded:
                logger.warning("rate-limit store unavailable; degrading to per-process limiting")
            self.degraded = True
            return self._fallback.hit(bucket, key, policy)
        if int(allowed) == 1:
            return RateLimitResult(allowed=True, remaining=max(0, policy.limit - int(count)), retry_after=0)
        retry = max(1, int(policy.window_seconds - (now - float(oldest))))
        return RateLimitResult(allowed=False, remaining=0, retry_after=retry)

    def reset(self) -> None:  # test seam only; a shared store is never bulk-cleared in production
        self._fallback.reset()


# Process-global limiter (single-replica default). Tests override via get/reset.
_limiter: RateLimiter | None = None
_shared_store_requested = False
_shared_store_active = False


def build_rate_limiter() -> RateLimiter:
    """Select the rate limiter for this deployment.

    Default: the in-memory adapter (correct for one replica and for tests). A shared store is used only
    when explicitly requested (``RATE_LIMIT_BACKEND=redis|shared``, or a ``REDIS_URL``) AND a ``REDIS_URL``
    is configured AND the optional ``redis`` package is importable; otherwise the request is recorded
    (surfaced by hosting-readiness) and the in-memory adapter is used. Distributed limiting is only live when
    :func:`shared_store_active` is True, and even then the adapter has not been validated against a live Redis.
    """
    global _shared_store_requested, _shared_store_active
    backend = (os.environ.get("RATE_LIMIT_BACKEND", "") or "").strip().lower()
    url = os.environ.get("REDIS_URL", "").strip()
    _shared_store_requested = backend in {"redis", "shared"} or bool(url)
    _shared_store_active = False
    if _shared_store_requested and url:
        try:
            import redis  # optional dependency, not installed by default

            limiter = RedisRateLimiter(redis.Redis.from_url(url, socket_timeout=1.0, socket_connect_timeout=1.0))
            _shared_store_active = True
            return limiter
        except Exception:  # noqa: BLE001 - missing package or bad URL: stay on the safe default
            logger.warning("shared rate-limit store requested but unavailable; using in-memory limiter")
    return InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = build_rate_limiter()
    return _limiter


def reset_rate_limiter(limiter: RateLimiter | None = None) -> None:
    """Test seam: install a fresh limiter (or a supplied one)."""
    global _limiter
    _limiter = limiter if limiter is not None else build_rate_limiter()


def shared_store_active() -> bool:
    """Whether a shared (distributed) rate-limit store is actually in use right now."""
    return _shared_store_active


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


def enforce(bucket: str, key: str, *, limiter: RateLimiter | None = None) -> None:
    """Apply one bucket to one key; raise HTTP 429 (with Retry-After) when exceeded.

    Unknown buckets are a programming error and raise KeyError (fail loud in tests, never
    silently unlimited)."""
    policy = POLICIES[bucket]
    lim = limiter or get_rate_limiter()
    result = lim.hit(bucket, key, policy)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(result.retry_after)},
        )
