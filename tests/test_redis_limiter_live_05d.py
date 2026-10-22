"""05D: the Redis rate limiter against a REAL Redis. Runs ONLY when ``TEST_REDIS_URL`` is set (a throw-away Redis the operator provides); otherwise every test is
SKIPPED with an explicit reason. Nothing here installs or starts Redis, and no Docker is used. Keys live under a unique prefix and exactly those are deleted.

    TEST_REDIS_URL=redis://127.0.0.1:6379/15 "<venv>/bin/python" -m pytest -p no:cacheprovider tests/test_redis_limiter_live_05d.py -q

Status in this repository: NOT RUN (no Redis available; live validation waits for staging, OD-HOSTED)."""

from __future__ import annotations

import os
import time
import uuid

import pytest

from src.api import rate_limit as rl

URL = os.environ.get("TEST_REDIS_URL", "").strip()
pytestmark = pytest.mark.skipif(not URL, reason="TEST_REDIS_URL is not set: live Redis limiter integration NOT RUN (no Redis is installed or started by the test suite)")


@pytest.fixture()
def client():
    redis = pytest.importorskip("redis", reason="the optional 'redis' package is not installed: live Redis limiter integration NOT RUN")
    c = redis.Redis.from_url(URL, socket_timeout=2.0, socket_connect_timeout=2.0)
    try:
        c.ping()
    except Exception:
        pytest.skip("TEST_REDIS_URL is set but Redis did not answer PING: live Redis limiter integration NOT RUN")
    prefix = f"ask4mo:test:{uuid.uuid4().hex[:12]}:"
    yield c, prefix
    for key in c.scan_iter(match=f"{prefix}*"):
        c.delete(key)


def test_real_redis_shares_one_window_across_two_replicas(client):
    c, prefix = client
    pol = rl.RateLimitPolicy("live", 2, 30, "ip")
    a, b = rl.RedisRateLimiter(c, prefix=prefix), rl.RedisRateLimiter(c, prefix=prefix)
    assert a.hit("b", "k", pol).allowed and b.hit("b", "k", pol).allowed
    refused = a.hit("b", "k", pol)
    assert not refused.allowed and refused.retry_after >= 1 and a.degraded is False
    assert b.hit("b", "other", pol).allowed


def test_real_redis_window_expires_and_key_gets_a_ttl(client):
    c, prefix = client
    pol = rl.RateLimitPolicy("live", 1, 1, "ip")
    lim = rl.RedisRateLimiter(c, prefix=prefix)
    assert lim.hit("b", "k", pol).allowed and not lim.hit("b", "k", pol).allowed
    assert 0 < c.ttl(f"{prefix}b:k") <= 3
    time.sleep(1.2)
    assert lim.hit("b", "k", pol).allowed


def test_real_redis_unreachable_store_degrades_per_the_bucket_policy():
    redis = pytest.importorskip("redis")
    dead = redis.Redis(host="127.0.0.1", port=1, socket_timeout=0.2, socket_connect_timeout=0.2)
    lim = rl.RedisRateLimiter(dead, prefix="ask4mo:test:dead:")
    pol = rl.RateLimitPolicy("live", 1, 30, "ip")
    assert lim.hit("b", "k", pol).allowed and not lim.hit("b", "k", pol).allowed and lim.degraded is True
    assert not lim.hit("b", "k2", rl.RateLimitPolicy("s", 1, 30, "ip", on_store_failure="deny")).allowed
