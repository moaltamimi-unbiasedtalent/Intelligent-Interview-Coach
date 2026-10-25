"""05D: distributed-limiter semantics against a FAKE Redis that implements the same interface (``eval`` of the shipped script).

What this proves: atomicity by construction (one script call per hit, nothing else), shared windows across replicas, window expiry and key TTL, key hygiene, and
the failure behaviour AS CURRENTLY SPECIFIED (``on_store_failure``: "local" = degrade to a bounded per-process window, "deny" = refuse). What it does NOT prove: the
Lua script on a real Redis. That is tests/test_redis_limiter_live_05d.py, which runs only with TEST_REDIS_URL and is otherwise SKIPPED; the live round trip is NOT RUN.
"""

from __future__ import annotations

import threading

import pytest

from src.api import rate_limit as rl
from tests._fake_redis import FakeRedis

POL = rl.RateLimitPolicy("t", 3, 60, "ip")


@pytest.fixture(autouse=True)
def _restore():
    yield
    rl.reset_rate_limiter()


def _pair(clock):
    store = FakeRedis(clock=lambda: clock[0])
    return store, rl.RedisRateLimiter(store, clock=lambda: clock[0]), rl.RedisRateLimiter(store, clock=lambda: clock[0])


def test_every_hit_is_exactly_one_script_call_so_atomicity_is_the_stores():
    clock = [1000.0]
    store, a, b = _pair(clock)
    for _ in range(5):
        a.hit("login", "ip", POL)
        b.hit("login", "ip", POL)
    assert store.commands == ["eval"] * 10          # no separate read/write that another replica could interleave with


def test_concurrent_replicas_cannot_exceed_the_limit():
    clock = [1000.0]
    store, a, b = _pair(clock)
    pol = rl.RateLimitPolicy("t", 10, 60, "ip")
    allowed, lock = [], threading.Lock()

    def worker(limiter):
        for _ in range(20):
            r = limiter.hit("b", "k", pol)
            with lock:
                allowed.append(r.allowed)
    threads = [threading.Thread(target=worker, args=(a if i % 2 else b,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(allowed) == 160 and sum(allowed) == 10


def test_same_instant_hits_are_all_counted_because_members_are_unique():
    clock = [1000.0]
    store, a, _ = _pair(clock)
    assert [a.hit("b", "k", POL).allowed for _ in range(4)] == [True, True, True, False]


def test_remaining_counts_down_and_retry_after_reflects_the_oldest_event():
    clock = [1000.0]
    _, a, _b = _pair(clock)
    assert [a.hit("b", "k", POL).remaining for _ in range(3)] == [2, 1, 0]
    clock[0] = 1010.0
    refused = a.hit("b", "k", POL)
    assert not refused.allowed and refused.remaining == 0 and refused.retry_after == 50      # window 60 - (1010 - 1000)


def test_window_slides_and_the_key_expires_on_the_server():
    clock = [1000.0]
    store, a, _ = _pair(clock)
    for _ in range(3):
        a.hit("b", "k", POL)
    assert not a.hit("b", "k", POL).allowed
    assert len(store._live(a.store_key("b", "k"))) == 3
    clock[0] = 1061.0
    assert a.hit("b", "k", POL).allowed                   # the old events fell out of the window
    clock[0] = 1061.0 + 60 + 2
    assert store._live(a.store_key("b", "k")) == []             # server-side TTL elapsed: the key is gone, nothing accumulates forever


def test_keys_are_namespaced_independent_and_never_contain_a_raw_email():
    clock = [1000.0]
    store, a, _ = _pair(clock)
    email = "someone.private@example.com"
    a.hit("auth_login_account", rl.email_key(email), rl.POLICIES["auth_login_account"])
    a.hit("auth_login_ip", "203.0.113.9", rl.POLICIES["auth_login_ip"])
    keys = store.keys()
    assert all(k.startswith("ask4mo:rl:") for k in keys) and len(keys) == 2
    assert not any("someone" in k or "example.com" in k for k in keys)
    assert rl.RedisRateLimiter(store, clock=lambda: clock[0]).hit("x", "203.0.113.9", POL).allowed       # another bucket is another window


def test_the_current_failure_specification_is_pinned_not_assumed():
    # Every shipped bucket currently degrades locally (bounded, never unlimited, never offline). "deny" exists but no bucket uses it. Changing this is a decision.
    assert {p.on_store_failure for p in rl.POLICIES.values()} == {"local"}
    assert rl.RateLimitPolicy("x", 1, 1, "ip").on_store_failure == "local"


def test_store_outage_with_local_policy_degrades_to_a_bounded_per_process_window_and_recovers():
    clock = [1000.0]
    store, a, _ = _pair(clock)
    store.fail = ConnectionError("down")
    results = [a.hit("b", "k", POL).allowed for _ in range(5)]
    assert results == [True, True, True, False, False]       # still limited per process: never fail-open to unlimited
    assert a.degraded is True
    store.fail = None
    assert a.hit("b", "fresh", POL).allowed and a.degraded is False        # the shared store answered: sharing is restored


def test_store_outage_with_deny_policy_fails_closed_without_touching_the_fallback():
    clock = [1000.0]
    store, a, _ = _pair(clock)
    strict = rl.RateLimitPolicy("s", 3, 60, "ip", on_store_failure="deny")
    store.fail = TimeoutError("slow")
    r = a.hit("b", "k", strict)
    assert (r.allowed, r.remaining, r.retry_after) == (False, 0, 5)
    assert a.degraded is True


def test_enforce_turns_a_refusal_into_429_with_retry_after_through_the_shared_store():
    from fastapi import HTTPException

    clock = [1000.0]
    store, a, _ = _pair(clock)
    assert rl.POLICIES["auth_verify_resend_cooldown"].limit == 1
    rl.enforce("auth_verify_resend_cooldown", "k", limiter=a)
    with pytest.raises(HTTPException) as err:
        rl.enforce("auth_verify_resend_cooldown", "k", limiter=a)
    assert err.value.status_code == 429 and int(err.value.headers["Retry-After"]) >= 1


def test_status_reports_degraded_and_never_claims_live_validation():
    clock = [1000.0]
    store, a, _ = _pair(clock)
    rl.reset_rate_limiter(a)
    store.fail = OSError("x")
    a.hit("b", "k", POL)
    st = rl.limiter_status()
    assert st["backend"] == "redis" and st["degraded"] is True and st["effectively_distributed"] is False
    from src.application.admin_command_center import rate_limit_mode
    assert rate_limit_mode()["live_validated"] is False


# --- hosted configuration guards ------------------------------------------------------------------------------------------
def _hosted(monkeypatch, env, **kw):
    from src.api.env_validation import validate_runtime_config

    for k in ("RATE_LIMIT_BACKEND", "REDIS_URL", "RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED"):
        monkeypatch.delenv(k, raising=False)
    for k, v in kw.items():
        monkeypatch.setenv(k, v)
    return validate_runtime_config(env)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_hosted_without_a_shared_store_states_the_single_process_limitation(monkeypatch, env):
    rep = _hosted(monkeypatch, env)
    assert any("per process" in w and "RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED" in w for w in rep.warnings)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_hosted_acknowledged_single_process_is_quiet_and_readiness_still_says_not_distributed(monkeypatch, env):
    rep = _hosted(monkeypatch, env, RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED="true")
    assert not any("per process" in w for w in rep.warnings)
    from src.application.admin_command_center import rate_limit_mode
    mode = rate_limit_mode()
    assert mode["single_process_acknowledged"] is True and mode["distributed"] is False and "per process" in mode["note"]


@pytest.mark.parametrize("env", ["staging", "production"])
def test_hosted_requesting_a_shared_store_without_a_url_is_critical(monkeypatch, env):
    rep = _hosted(monkeypatch, env, RATE_LIMIT_BACKEND="redis")
    assert any("REDIS_URL is not set" in c for c in rep.critical)


def test_hosted_requesting_a_shared_store_without_the_package_is_critical(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda name, *a, **k: None)
    rep = _hosted(monkeypatch, "production", RATE_LIMIT_BACKEND="redis", REDIS_URL="redis://example.invalid:6379/0")
    assert any("'redis' package is not installed" in c for c in rep.critical)


def test_hosted_with_url_and_package_has_no_rate_limit_finding(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda name, *a, **k: object())
    rep = _hosted(monkeypatch, "production", RATE_LIMIT_BACKEND="redis", REDIS_URL="rediss://limiter:ssssssssssssssssssssssssssssssss@example.invalid:6379/0", RATE_LIMIT_NAMESPACE="ask4mo:rl:test:", RATE_LIMIT_KEY_SECRET="kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")
    assert not any("shared store" in m or "per process" in m for m in rep.critical + rep.warnings)


def test_unknown_backend_value_is_critical_in_hosted_and_ignored_locally(monkeypatch):
    assert any("RATE_LIMIT_BACKEND must be" in c for c in _hosted(monkeypatch, "production", RATE_LIMIT_BACKEND="memcached").critical)
    assert _hosted(monkeypatch, "development", RATE_LIMIT_BACKEND="memcached").critical == []
