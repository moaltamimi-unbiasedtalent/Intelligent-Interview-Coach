"""P10B-W9.12 - rate-limiter abstraction: in-memory default, optional shared (Redis) adapter, honest reporting.

The Redis adapter is exercised against a fake client that emulates the window script in Python. The Lua script
itself has NOT been run against a live Redis in CI, so distributed limiting is never claimed as live here.
"""

from __future__ import annotations

import sys
import types

import pytest

from src.api import rate_limit as rl

POLICY = rl.RateLimitPolicy(name="t", limit=2, window_seconds=60, scope="ip")


class FakeRedis:
    """Emulates the sliding-window script semantics (trim, count, add) per key, in Python."""

    def __init__(self, fail: bool = False):
        self.zsets: dict[str, list[float]] = {}
        self.fail = fail
        self.calls = 0

    def eval(self, script, numkeys, key, now, window, limit, member):
        self.calls += 1
        if self.fail:
            raise ConnectionError("redis down")
        z = [t for t in self.zsets.get(key, []) if t > now - window]
        if len(z) >= limit:
            self.zsets[key] = z
            return [0, len(z), min(z)]
        z.append(now)
        self.zsets[key] = z
        return [1, len(z), 0]


def test_in_memory_limiter_is_the_default_and_not_distributed():
    lim = rl.build_rate_limiter()
    assert isinstance(lim, rl.InMemoryRateLimiter) and lim.distributed is False
    assert rl.shared_store_active() is False


def test_in_memory_window_blocks_after_the_limit():
    clock = [0.0]
    lim = rl.InMemoryRateLimiter(clock=lambda: clock[0])
    assert lim.hit("b", "k", POLICY).allowed and lim.hit("b", "k", POLICY).allowed
    denied = lim.hit("b", "k", POLICY)
    assert not denied.allowed and denied.retry_after >= 1
    clock[0] = 61
    assert lim.hit("b", "k", POLICY).allowed  # window slid


def test_redis_adapter_enforces_a_shared_window_across_two_replicas():
    store = FakeRedis()
    now = [100.0]
    replica_a = rl.RedisRateLimiter(store, clock=lambda: now[0])
    replica_b = rl.RedisRateLimiter(store, clock=lambda: now[0])
    assert replica_a.distributed is True
    assert replica_a.hit("login", "ip1", POLICY).allowed
    assert replica_b.hit("login", "ip1", POLICY).allowed          # counted in the SAME shared window
    blocked = replica_a.hit("login", "ip1", POLICY)
    assert not blocked.allowed and blocked.retry_after >= 1       # a third hit on either replica is refused
    assert replica_b.hit("login", "other-ip", POLICY).allowed     # keys are independent


def test_redis_adapter_degrades_to_in_memory_when_the_store_fails():
    lim = rl.RedisRateLimiter(FakeRedis(fail=True))
    assert lim.hit("b", "k", POLICY).allowed and lim.hit("b", "k", POLICY).allowed
    assert not lim.hit("b", "k", POLICY).allowed     # still limited (per process), never fails open or crashes
    assert lim.degraded is True


def test_shared_store_request_without_url_or_package_stays_in_memory_and_is_reported(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    lim = rl.build_rate_limiter()
    assert isinstance(lim, rl.InMemoryRateLimiter)
    assert rl.shared_store_requested() is True and rl.shared_store_active() is False

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setitem(sys.modules, "redis", None)    # package not installed -> import fails
    lim = rl.build_rate_limiter()
    assert isinstance(lim, rl.InMemoryRateLimiter) and rl.shared_store_active() is False


def test_shared_store_is_active_only_when_requested_configured_and_installed(monkeypatch):
    fake = types.ModuleType("redis")

    class _Redis:
        @staticmethod
        def from_url(url, **_kw):
            return FakeRedis()

    fake.Redis = _Redis
    monkeypatch.setitem(sys.modules, "redis", fake)
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    lim = rl.build_rate_limiter()
    assert isinstance(lim, rl.RedisRateLimiter) and rl.shared_store_active() is True


@pytest.fixture(autouse=True)
def _restore_limiter():
    yield
    rl.reset_rate_limiter()
