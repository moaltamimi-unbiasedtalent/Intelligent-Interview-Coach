"""Canonical product USAGE-QUOTA foundation (W12.4D-P4-A).

Three separate control layers (never conflated):

1. OPERATIONAL RATE LIMITING (``src/api/rate_limit.py``, ``ai_protection.admit``): burst and abuse protection, REQUESTS per short window.
2. PRODUCT USAGE QUOTAS (this module): the authorized consumption of a Basic or Premium candidate, in explicit PRODUCT UNITS per UTC period.
3. PROVIDER COST ACCOUNTING (``ai_operation_events``): what a logical operation actually consumed at the provider (attempts, tokens, reported cost).
   A request count is not money and a quota unit is not a billing record; quota accounting never reads or writes the provider ledger, and a released
   reservation never erases provider consumption already recorded there.

* **Default disabled.** ``USAGE_QUOTAS_ENFORCED = False`` is a code constant (like the billing gates and the other rollout gates). No setting, startup, Admin
  action, public API or frontend flag can flip it. While False nothing is reserved, counted or refused and no table is touched: existing candidate usage is
  exactly what it is today.
* **No approved numbers.** The owner has approved the feature allocation but NOT any numerical allowance, reset period or price. ``DEFAULT_POLICY`` therefore
  holds NO allowance. Tests supply synthetic policies. With enforcement on and no allowance for the caller's plan, the controlled outcome is
  ``QuotaNotConfigured`` (fail closed), never unlimited use; activation therefore REQUIRES a complete, owner-approved policy.
* **One entitlement authority.** The plan is read from ``plan_state.resolve_plan_state`` over the existing ``EntitlementService`` (an ACTIVE Premium-plan
  subscription). ``premium_preview``, client labels, expired and unknown state are never Premium; an unreadable entitlement is treated as Basic.
* **Atomic.** One database transaction inserts the reservation (unique ``op_key``: a retry or duplicate never consumes twice) and applies a conditional
  ``UPDATE ... SET used = used + 1 WHERE used < limit`` on the counter. Concurrent requests (including from several workers sharing the database) cannot
  exceed the allowance. The key is the AUTHENTICATED user id, never client input.
* **Lifecycle.** reserved -> committed (the logical operation succeeded) or released (it failed before completing; the unit is returned). An abandoned
  ``reserved`` row (a worker crash) is released by ``reap_expired``. Provider attempts inside one logical operation are never separate units.
* **Time.** Periods are UTC calendar boundaries (hour, day, month). The subscription billing period is not supported yet and is reported as not configured.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("usage.quota")

# A code constant: nothing but a reviewed, owner-approved release can enable commercial quota enforcement. Tests flip it on an isolated module attribute.
USAGE_QUOTAS_ENFORCED = False
POLICY_VERSION_UNCONFIGURED = "p4a-unconfigured"
RESERVATION_TTL = timedelta(minutes=15)       # an abandoned reservation older than this is recoverable (a provider operation is bounded well below it)
_TEST_ENVS = ("development", "dev", "local", "test", "testing")
PERIODS = ("hour", "day", "month")

__all__ = ["USAGE_QUOTAS_ENFORCED", "QUOTA_FEATURES", "QuotaFeature", "Allowance", "QuotaPolicy", "DEFAULT_POLICY", "QuotaExhausted", "QuotaNotConfigured",
           "QuotaUnavailable", "UsageQuotaService", "feature_for_operation", "period_bounds", "get_policy"]


@dataclass(frozen=True)
class QuotaFeature:
    id: str
    unit: str                      # the PRODUCT unit consumed (not interchangeable across features)
    operations: frozenset          # (workflow, operation) pairs that consume ONE unit; every other operation of the workflow consumes none


# Only the operations that genuinely need a product quota for launch. One candidate action maps to at most ONE feature; follow-up steps of an already
# started interview (answer feedback, next question, deep dive, report) consume nothing, so one action never drains several quotas.
QUOTA_FEATURES: dict[str, QuotaFeature] = {
    "practice_session": QuotaFeature("practice_session", "session_started", frozenset({("practice", "setup")})),
    "career_ai": QuotaFeature("career_ai", "ai_generation", frozenset({("career", "chat"), ("career", "job_analysis"), ("career", "questions")})),
}


def feature_for_operation(workflow: str, operation: str) -> str | None:
    for f in QUOTA_FEATURES.values():
        if (workflow, operation) in f.operations:
            return f.id
    return None


@dataclass(frozen=True)
class Allowance:
    limit: int
    period: str                    # hour | day | month (UTC)

    def __post_init__(self) -> None:
        if self.limit < 0 or self.period not in PERIODS:
            raise ValueError("invalid allowance")


@dataclass(frozen=True)
class QuotaPolicy:
    """Versioned allowances keyed by (plan, feature). A missing key means NOT CONFIGURED (never unlimited)."""

    version: str
    allowances: Mapping[tuple[str, str], Allowance] = field(default_factory=dict)

    def allowance(self, plan: str, feature: str) -> Allowance | None:
        return self.allowances.get((plan, feature))

    def complete(self) -> bool:
        return all((p, f) in self.allowances for p in ("basic", "premium") for f in QUOTA_FEATURES)


DEFAULT_POLICY = QuotaPolicy(POLICY_VERSION_UNCONFIGURED, {})      # NO owner-approved number exists: nothing is configured


def get_policy() -> QuotaPolicy:
    """The active policy. A single seam so a reviewed release (or a test) replaces it; never read from a request."""
    return DEFAULT_POLICY


class QuotaExhausted(Exception):
    """The caller's allowance for the period is used up. Carries only safe, candidate-displayable facts."""

    def __init__(self, feature: str, period: str, reset_at: datetime, now: datetime) -> None:
        super().__init__("usage_quota_exhausted")
        self.feature, self.period, self.reset_at = feature, period, reset_at
        self.retry_after = max(1, int((reset_at - now).total_seconds()))


class QuotaNotConfigured(Exception):
    """Enforcement is on but no allowance exists for this plan and feature (or the period is unsupported). Fail closed."""


class QuotaUnavailable(Exception):
    """The quota store could not be read or written. Fail closed for the quota-gated operation only."""


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def period_bounds(period: str, now: datetime) -> tuple[datetime, datetime]:
    """UTC calendar ``[start, reset)`` containing ``now``. Server clock only; never a browser clock."""
    now = _utc(now).astimezone(timezone.utc)
    if period == "hour":
        start = now.replace(minute=0, second=0, microsecond=0)
        return start, start + timedelta(hours=1)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        nxt = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
        return start, nxt
    raise ValueError("unsupported quota period")


class UsageQuotaService:
    """Stateless per request: every decision reads the entitlement and the durable counters fresh, so a plan change applies on the next call."""

    def __init__(self, session_factory, entitlements, *, policy: QuotaPolicy | None = None, now: Callable[[], datetime] | None = None,
                 override: Callable[[int], str] | None = None) -> None:
        if override is not None and (os.environ.get("API_ENV") or "development").strip().lower() not in _TEST_ENVS:
            raise ValueError("A synthetic quota plan decision cannot be used outside development and test.")
        self._sf, self._entitlements = session_factory, entitlements
        self._policy, self._now, self._override = policy, now or (lambda: datetime.now(timezone.utc)), override

    @classmethod
    def from_session_factory(cls, session_factory) -> "UsageQuotaService":
        """The production wiring: the canonical ``EntitlementService`` over the same database (the one entitlement authority; no second reader or writer)."""
        from src.entitlements import EntitlementService

        return cls(session_factory, EntitlementService(session_factory))

    # ------------------------------------------------------------------------------------------------ decision
    def policy(self) -> QuotaPolicy:
        return self._policy or get_policy()

    def plan_for(self, user_id: int) -> str:
        if self._override is not None:
            return "premium" if self._override(int(user_id)) == "premium" else "basic"
        from src.application.plan_state import PREMIUM, resolve_plan_state

        return "premium" if resolve_plan_state(self._entitlements, user_id) == PREMIUM else "basic"      # unresolved/unknown/expired/preview -> basic

    def _allowance(self, user_id: int, feature: str) -> tuple[str, Allowance]:
        plan = self.plan_for(user_id)
        allowance = self.policy().allowance(plan, feature)
        if allowance is None:
            raise QuotaNotConfigured(feature)
        return plan, allowance

    # ------------------------------------------------------------------------------------------------ admission
    def reserve(self, user_id: int, feature: str, op_key: str) -> bool:
        """Reserve ONE unit for the logical operation ``op_key``. Returns False when enforcement is disabled (nothing recorded) and True when a unit is held
        (a duplicate or retry of the same ``op_key`` holds the SAME unit). Raises ``QuotaExhausted`` / ``QuotaNotConfigured`` / ``QuotaUnavailable``.
        Must be called BEFORE any provider work."""
        if not USAGE_QUOTAS_ENFORCED:
            return False
        if feature not in QUOTA_FEATURES:
            raise QuotaNotConfigured(feature)
        from src.persistence import UsageQuotaCounter, UsageQuotaReservation

        now = _utc(self._now())
        _, allowance = self._allowance(user_id, feature)
        start, reset = period_bounds(allowance.period, now)
        version = self.policy().version[:24]
        try:
            with self._sf() as s:
                existing = s.scalar(select(UsageQuotaReservation).where(UsageQuotaReservation.op_key == op_key))
                if existing is not None:
                    if existing.user_id != int(user_id):
                        raise QuotaNotConfigured(feature)                          # an op_key is never shared across users
                    if existing.state != "released":
                        return True                                                  # retry/duplicate of a held or finished operation: no second unit
                    existing.state, existing.period_start, existing.expires_at, existing.finalized_at = "reserved", start, now + RESERVATION_TTL, None
                else:
                    s.add(UsageQuotaReservation(op_key=op_key, user_id=int(user_id), feature=feature, period_start=start, state="reserved",
                                                policy_version=version, created_at=now, expires_at=now + RESERVATION_TTL))
                    try:
                        s.flush()                                                    # the unique op_key arbitrates a concurrent duplicate
                    except IntegrityError:
                        s.rollback()
                        return True
                counter = self._ensure_counter(s, user_id, feature, start, version, now)
                took = s.execute(update(UsageQuotaCounter).where(UsageQuotaCounter.id == counter, UsageQuotaCounter.used < allowance.limit)
                                 .values(used=UsageQuotaCounter.used + 1, updated_at=now, policy_version=version)).rowcount
                if took != 1:
                    s.rollback()                                                     # the reservation row is discarded with it
                    raise QuotaExhausted(feature, allowance.period, reset, now)
                s.commit()
                return True
        except (QuotaExhausted, QuotaNotConfigured):
            raise
        except Exception as exc:  # noqa: BLE001 - an unreadable or unwritable store never grants
            log.warning("usage quota store unavailable")
            raise QuotaUnavailable("quota_store_unavailable") from exc

    @staticmethod
    def _ensure_counter(s, user_id: int, feature: str, start: datetime, version: str, now: datetime) -> int:
        from src.persistence import UsageQuotaCounter

        q = select(UsageQuotaCounter.id).where(UsageQuotaCounter.user_id == int(user_id), UsageQuotaCounter.feature == feature,
                                               UsageQuotaCounter.period_start == start)
        found = s.scalar(q)
        if found is not None:
            return found
        try:
            with s.begin_nested():
                s.add(UsageQuotaCounter(user_id=int(user_id), feature=feature, period_start=start, used=0, policy_version=version, updated_at=now))
        except IntegrityError:
            pass                                                                    # another worker created it first
        return s.scalar(q)

    # ------------------------------------------------------------------------------------------------ finalization
    def commit(self, op_key: str) -> bool:
        """reserved -> committed (the logical operation succeeded). Idempotent; False when nothing was reserved."""
        if not USAGE_QUOTAS_ENFORCED:
            return False
        return self._finish(op_key, "committed", give_back=False)

    def release(self, op_key: str) -> bool:
        """reserved -> released and the unit is returned (the logical operation failed). Never touches the provider ledger. Idempotent."""
        if not USAGE_QUOTAS_ENFORCED:
            return False
        return self._finish(op_key, "released", give_back=True)

    def _finish(self, op_key: str, state: str, *, give_back: bool) -> bool:
        from src.persistence import UsageQuotaCounter, UsageQuotaReservation

        now = _utc(self._now())
        try:
            with self._sf() as s:
                row = s.scalar(select(UsageQuotaReservation).where(UsageQuotaReservation.op_key == op_key))
                if row is None:
                    return False
                moved = s.execute(update(UsageQuotaReservation).where(UsageQuotaReservation.id == row.id, UsageQuotaReservation.state == "reserved")
                                  .values(state=state, finalized_at=now)).rowcount
                if moved != 1:
                    return False                                                     # already finished: the transition is single-use
                if give_back:
                    s.execute(update(UsageQuotaCounter).where(UsageQuotaCounter.user_id == row.user_id, UsageQuotaCounter.feature == row.feature,
                                                              UsageQuotaCounter.period_start == row.period_start, UsageQuotaCounter.used > 0)
                              .values(used=UsageQuotaCounter.used - 1, updated_at=now))
                s.commit()
                return True
        except Exception:  # noqa: BLE001
            log.warning("usage quota finalization failed")
            return False

    def reap_expired(self) -> int:
        """Release every reservation still ``reserved`` past its expiry (a crashed worker). Returns how many were recovered."""
        from src.persistence import UsageQuotaReservation

        now = _utc(self._now())
        with self._sf() as s:
            keys = list(s.scalars(select(UsageQuotaReservation.op_key).where(UsageQuotaReservation.state == "reserved", UsageQuotaReservation.expires_at < now)))
        return sum(1 for k in keys if self._finish(k, "released", give_back=True))

    # ------------------------------------------------------------------------------------------------ presentation
    def snapshot(self, user_id: int) -> dict:
        """Server-authored, caller-scoped view for a candidate UI. Fabricates nothing: a feature with no configured allowance is ``not_configured`` and
        carries no number; while enforcement is off the view says so and carries no allowance at all."""
        if not USAGE_QUOTAS_ENFORCED:
            return {"enforcement_active": False, "policy_version": None, "features": []}
        from src.persistence import UsageQuotaCounter

        now, plan, out = _utc(self._now()), self.plan_for(user_id), []
        policy = self.policy()
        for f in QUOTA_FEATURES.values():
            a = policy.allowance(plan, f.id)
            if a is None:
                out.append({"feature": f.id, "unit": f.unit, "status": "not_configured"})
                continue
            start, reset = period_bounds(a.period, now)
            try:
                with self._sf() as s:
                    used = s.scalar(select(UsageQuotaCounter.used).where(UsageQuotaCounter.user_id == int(user_id), UsageQuotaCounter.feature == f.id,
                                                                         UsageQuotaCounter.period_start == start)) or 0
            except Exception:  # noqa: BLE001
                out.append({"feature": f.id, "unit": f.unit, "status": "unavailable"})
                continue
            out.append({"feature": f.id, "unit": f.unit, "status": "exhausted" if used >= a.limit else "available", "period": a.period, "allowance": a.limit,
                        "used": used, "remaining": max(0, a.limit - used), "reset_at": reset.isoformat()})
        return {"enforcement_active": True, "policy_version": policy.version, "features": out}
