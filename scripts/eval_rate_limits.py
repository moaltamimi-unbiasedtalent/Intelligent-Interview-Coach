#!/usr/bin/env python
"""Capstone P8 rate-limit evaluation (§52).

Deterministic verification of the auth + cost rate limits using an in-memory limiter with a
controllable clock — no live provider cost, no network. Covers per-bucket ceilings,
window reset, anti-enumeration (identical limit whether or not an account exists), and the
costly-capability buckets. Importable via ``run()`` for the pytest suite.
"""

from __future__ import annotations

from src.api import rate_limit as RL


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _exhaust(limiter, bucket: str, key: str) -> tuple[int, bool]:
    """Hit until blocked; return (allowed_count, blocked_seen)."""
    policy = RL.POLICIES[bucket]
    allowed = 0
    blocked = False
    for _ in range(policy.limit + 3):
        res = limiter.hit(bucket, key, policy)
        if res.allowed:
            allowed += 1
        else:
            blocked = True
    return allowed, blocked


def run() -> dict[str, tuple[bool, str]]:
    r: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        r[name] = (bool(ok), detail)

    clock = _Clock()
    limiter = RL.InMemoryRateLimiter(clock=clock)

    # 1) Every auth + cost bucket blocks after exactly `limit` events.
    for bucket in ("auth_login_ip", "auth_login_account", "auth_register_ip",
                   "auth_verify_resend", "auth_forgot_ip", "auth_forgot_account",
                   "auth_reset_ip", "cost_agent_user", "cost_realtime_user",
                   "cost_upload_user"):
        allowed, blocked = _exhaust(limiter, bucket, f"k-{bucket}")
        policy = RL.POLICIES[bucket]
        check(f"blocks_{bucket}", allowed == policy.limit and blocked,
              f"allowed={allowed} limit={policy.limit} blocked={blocked}")

    # 2) Window reset: after the window elapses, the bucket frees up.
    b = "auth_login_ip"
    pol = RL.POLICIES[b]
    limiter2 = RL.InMemoryRateLimiter(clock=clock)
    _exhaust(limiter2, b, "reset-key")
    blocked_now = not limiter2.hit(b, "reset-key", pol).allowed
    clock.advance(pol.window_seconds + 1)
    allowed_after = limiter2.hit(b, "reset-key", pol).allowed
    check("window_reset", blocked_now and allowed_after, "blocked before window, allowed after")

    # 3) Anti-enumeration: the email-derived key is identical whether or not an account exists,
    #    so the rate limit is identical (no existence signal via limits).
    k_exists = RL.email_key("real@example.com")
    k_same = RL.email_key("REAL@example.com")  # normalization → same key
    check("email_key_normalized", k_exists == k_same, "email key is case/space-normalized")
    check("email_key_hashed", "@" not in k_exists and len(k_exists) == 32,
          "email key is a hash, never the raw address")

    # 4) enforce() raises HTTP 429 with Retry-After once exceeded.
    from fastapi import HTTPException

    RL.reset_rate_limiter(RL.InMemoryRateLimiter(clock=_Clock()))
    raised = False
    retry_after_ok = False
    pol_forgot = RL.POLICIES["auth_forgot_account"]
    try:
        for _ in range(pol_forgot.limit + 2):
            RL.enforce("auth_forgot_account", "same-key")
    except HTTPException as exc:
        raised = exc.status_code == 429
        retry_after_ok = "Retry-After" in (exc.headers or {})
    check("enforce_raises_429", raised, "enforce raises 429 when exceeded")
    check("retry_after_header", retry_after_ok, "429 carries a Retry-After header")

    # 5) Distinct keys are independent (per-user / per-IP isolation).
    limiter3 = RL.InMemoryRateLimiter(clock=_Clock())
    a_allowed, _ = _exhaust(limiter3, "cost_agent_user", "user:1")
    b_first = limiter3.hit("cost_agent_user", "user:2", RL.POLICIES["cost_agent_user"]).allowed
    check("keys_independent", a_allowed == RL.POLICIES["cost_agent_user"].limit and b_first,
          "a different user/IP is not affected by another's limit")

    # 6) Unknown bucket is a loud error (never silently unlimited).
    unknown_loud = False
    try:
        RL.enforce("does_not_exist", "k")
    except KeyError:
        unknown_loud = True
    check("unknown_bucket_loud", unknown_loud, "unknown bucket raises (never unlimited)")

    return r


def main() -> int:
    print("ASK4MO — CAPSTONE P8 RATE-LIMIT EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        failed = failed or not ok
        print(f"  {name:28s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid calls: 0   Provider calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (rate-limit invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
