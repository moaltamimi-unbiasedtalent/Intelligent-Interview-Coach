"""BillingService (P10B-W10.5). MOCK BILLING: NOT LIVE BILLING.

THE INVARIANT: billing state is not entitlement state. Nothing in this module reads or writes ``subscriptions``, ``product_entitlements``,
plan entitlements or the compatibility tier. A price change, a failed payment, a past-due invoice, a refund or a provider-side cancellation
changes billing metadata only; product access stays with the W10.4 plans/subscriptions and EntitlementService.

* Money is integer minor units plus a currency code. No card, payment-instrument, bank, tax or raw provider data is ever stored.
* Commercial terms are versioned and immutable; "no terms" means UNCONFIGURED (never free). No price is seeded.
* Price changes and refunds need a SECOND, different, active administrator holding the specific permission (no override).
* Provider interaction (refund) is replay-safe through a stable idempotency key; events are idempotent on (provider, provider_event_id).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from src.admin_repository import _page, _stage
from src.application import admin_permissions as perm
from src.billing import policy as P
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE, BillingApprovalRequest as AR, BillingCommercialTerms as CT, BillingCustomer as CU, BillingEvent as EV,
    BillingInvoice as INV, BillingPayment as PAY, BillingProviderSubscription as PS, BillingRefund as RF, PlanVersion, User, Workspace, utcnow,
)

_CUR = re.compile(r"^[A-Z]{3}$")


class BillingNotFound(Exception):
    pass


class BillingValidationError(Exception):
    pass


class BillingConflict(Exception):
    pass


class BillingForbidden(Exception):
    """Self-approval or a missing second-approver qualification."""


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def validate_amount(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BillingValidationError("The amount must be a whole number of minor units (for example cents).")
    if value < 0 or value > P.MAX_AMOUNT_MINOR:
        raise BillingValidationError("The amount is outside the allowed range.")
    return value


def validate_currency(value: Any) -> str:
    if not isinstance(value, str) or not _CUR.match(value):
        raise BillingValidationError("The currency must be a three-letter uppercase code. (This is metadata only: no live provider supports it.)")
    return value


def _when(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        raise BillingValidationError("A date is not valid.")


# normalised event field allowlists (anything else is rejected, so a raw provider body can never be smuggled in)
_EVENT_FIELDS = {
    "customer_created": ({"customer_ref"}, {"user_id", "workspace_id"}),
    "subscription_updated": ({"subscription_ref", "customer_ref", "plan_version_id", "state"}, {"period_start", "period_end", "grace_until"}),
    "invoice_opened": ({"invoice_ref", "customer_ref", "amount_due_minor", "currency"}, {"subscription_ref", "period_start", "period_end", "due_at"}),
    "invoice_paid": ({"invoice_ref"}, set()),
    "payment_succeeded": ({"payment_ref", "invoice_ref", "amount_minor", "currency"}, set()),
    "payment_failed": ({"payment_ref", "invoice_ref", "amount_minor", "currency", "failure_category"}, set()),
}


def validate_event(event_type: str, data: Any) -> dict:
    if event_type not in _EVENT_FIELDS or not isinstance(data, dict):
        raise BillingValidationError("Unknown billing event.")
    required, optional = _EVENT_FIELDS[event_type]
    if not required <= set(data) or set(data) - required - optional:
        raise BillingValidationError("The billing event has missing or unexpected fields.")
    for k, v in data.items():
        if isinstance(v, (dict, list)) or (isinstance(v, str) and len(v) > 80):
            raise BillingValidationError("A billing event field is not valid.")
    return dict(data)


class BillingService:
    def __init__(self, session_factory, *, provider: Any = None, mode: Any = None, jobs: Any = None,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._provider = provider
        self._mode = mode
        self._jobs = jobs
        self._clock = clock

    # ------------------------------------------------------------------ mode
    def mode(self) -> dict:
        if self._mode is not None:
            return self._mode.as_dict()
        from src.billing.provider import safe_mode
        return safe_mode().as_dict()

    # ------------------------------------------------------------------ commercial terms
    @staticmethod
    def _terms_view(t: CT) -> dict:
        return {"public_id": t.public_id, "version": t.version, "amount_minor": t.amount_minor, "currency": t.currency, "interval": t.billing_interval,
                "trial_days": t.trial_days, "visibility": t.visibility, "state": t.state, "activated_at": _iso(t.activated_at),
                "retired_at": _iso(t.retired_at), "approval_id": t.approval_public_id}

    def list_terms(self) -> dict:
        with self._sf() as s:
            versions = s.scalars(select(PlanVersion).order_by(PlanVersion.plan_code, PlanVersion.version.desc())).all()
            items = []
            for pv in versions:
                terms = s.scalars(select(CT).where(CT.plan_version_id == pv.id).order_by(CT.version.desc())).all()
                if pv.status == "retired" and not terms:
                    continue
                current = next((t for t in terms if t.state == "active"), None)
                pending = s.scalar(select(AR).where(AR.action_type == "price_change", AR.target_ref == f"plan_version:{pv.id}", AR.status == "pending"))
                items.append({"plan_version_id": pv.id, "plan_code": pv.plan_code, "plan_version": pv.version, "plan_name": pv.display_name,
                              "plan_status": pv.status, "current": self._terms_view(current) if current else None,
                              "configured": current is not None, "history": [self._terms_view(t) for t in terms],
                              "pending_approval_id": pending.public_id if pending else None})
            return {"items": items, "note": "No commercial terms means unconfigured, not free. Terms are mock metadata: they charge no one and change no entitlement."}

    @staticmethod
    def validate_terms(*, amount_minor, currency, interval, trial_days, visibility) -> dict:
        if interval not in P.INTERVALS:
            raise BillingValidationError("Choose a billing interval (month or year).")
        if visibility not in P.VISIBILITIES:
            raise BillingValidationError("Choose a visibility (public, private or internal).")
        if trial_days is not None and (isinstance(trial_days, bool) or not isinstance(trial_days, int) or not 1 <= trial_days <= P.MAX_TRIAL_DAYS):
            raise BillingValidationError("Trial days must be a whole number from 1 to 365, or empty.")
        return {"amount_minor": validate_amount(amount_minor), "currency": validate_currency(currency), "interval": interval,
                "trial_days": trial_days, "visibility": visibility}

    @staticmethod
    def _reason(reason: Any) -> str:
        r = (reason or "").strip() if isinstance(reason, str) else ""
        if not r or len(r) > P.MAX_REASON or "\x00" in r:
            raise BillingValidationError("A reason is required (up to 300 characters).")
        return r

    # ------------------------------------------------------------------ approvals (second approver)
    def _approver_ok(self, s, actor_user_id: int, required_permission: str) -> None:
        u = s.get(User, actor_user_id)
        if u is None or u.status != ACCOUNT_STATUS_ACTIVE or required_permission not in perm.permissions_for_role(u.platform_role):
            raise BillingForbidden("The approver must be an active administrator with the required permission.")

    def _approval_view(self, a: AR, s=None) -> dict:
        def email(uid):
            if uid is None:
                return None
            u = (s.get(User, uid) if s is not None else None)
            return u.email if u else None
        return {"public_id": a.public_id, "action_type": a.action_type, "target_ref": a.target_ref, "proposed": dict(a.proposed_json or {}),
                "reason": a.reason, "status": a.status, "requested_by_user_id": a.requested_by_user_id, "requested_by_email": email(a.requested_by_user_id),
                "requested_at": _iso(a.requested_at), "decided_by_user_id": a.decided_by_user_id, "decided_at": _iso(a.decided_at),
                "executed_at": _iso(a.executed_at), "execution_ref": a.execution_ref, "failure_category": a.failure_category}

    def list_approvals(self, *, action: str | None = None, status: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if action:
            if action not in P.APPROVAL_ACTIONS:
                raise BillingValidationError("Unknown action.")
            conds.append(AR.action_type == action)
        if status:
            if status not in P.APPROVAL_STATUSES:
                raise BillingValidationError("Unknown status.")
            conds.append(AR.status == status)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(AR).where(*conds)) or 0
            rows = s.scalars(select(AR).where(*conds).order_by(AR.requested_at.desc(), AR.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._approval_view(a, s) for a in rows], "total": total, "page": page, "page_size": page_size}

    def _new_request(self, s, action: str, target: str, proposed: dict, reason: str, actor: int, audit: dict | None, **ctx) -> AR:
        a = AR(public_id=uuid.uuid4().hex, action_type=action, target_ref=target, proposed_json=proposed, reason=reason, status="pending",
               requested_by_user_id=actor, requested_at=self._clock())
        s.add(a)
        try:
            s.flush()
        except IntegrityError:
            s.rollback()
            raise BillingConflict("A request for this target is already awaiting a second approver.")
        _stage(s, {**audit, "target_id": a.public_id} if audit else None, approval_public_id=a.public_id, new_state="pending", **ctx)
        return a

    def request_price_change(self, plan_version_id: int, *, amount_minor, currency, interval, trial_days, visibility, reason, actor_user_id: int,
                             audit: dict | None = None) -> dict:
        fields = self.validate_terms(amount_minor=amount_minor, currency=currency, interval=interval, trial_days=trial_days, visibility=visibility)
        reason = self._reason(reason)
        with self._sf() as s:
            pv = s.get(PlanVersion, plan_version_id)
            if pv is None:
                raise BillingNotFound("plan version")
            if pv.status == "retired":
                raise BillingConflict("A retired plan version cannot receive new commercial terms.")
            a = self._new_request(s, "price_change", f"plan_version:{pv.id}", {"plan_version_id": pv.id, **fields}, reason, actor_user_id, audit,
                                  plan_version_id=pv.id, amount_minor=fields["amount_minor"], currency=fields["currency"])
            s.commit()
            return self._approval_view(a, s)

    def _decidable(self, s, public_id: str, action: str, actor: int, permission: str) -> AR:
        a = s.scalar(select(AR).where(AR.public_id == public_id))
        if a is None or a.action_type != action:
            raise BillingNotFound(public_id)
        if a.status != "pending":
            raise BillingConflict("This request has already been decided.")
        if a.requested_by_user_id is not None and a.requested_by_user_id == actor:
            raise BillingForbidden("A different administrator must decide this request: you cannot approve your own.")
        self._approver_ok(s, actor, permission)
        return a

    def decide_price_change(self, public_id: str, *, approve: bool, actor_user_id: int, audit_decision: dict | None = None,
                            audit_activation: dict | None = None) -> dict:
        now = self._clock()
        with self._sf() as s:
            a = self._decidable(s, public_id, "price_change", actor_user_id, perm.PRICE_CHANGE)
            if not approve:
                a.status, a.decided_by_user_id, a.decided_at = "rejected", actor_user_id, now
                _stage(s, {**audit_decision, "target_id": public_id} if audit_decision else None, approval_public_id=public_id, old_state="pending", new_state="rejected")
                s.commit()
                return self._approval_view(a, s)
            p = a.proposed_json
            pv = s.get(PlanVersion, p["plan_version_id"])
            if pv is None or pv.status == "retired":
                raise BillingConflict("The plan version is no longer eligible for new commercial terms.")
            prior = s.scalar(select(CT).where(CT.plan_version_id == pv.id, CT.state == "active"))
            if prior is not None:
                prior.state, prior.retired_at = "retired", now
                s.flush()                                              # retire first so the one-active index never conflicts
            nxt = (s.scalar(select(func.max(CT.version)).where(CT.plan_version_id == pv.id)) or 0) + 1
            t = CT(public_id=uuid.uuid4().hex, plan_version_id=pv.id, version=nxt, amount_minor=p["amount_minor"], currency=p["currency"],
                   billing_interval=p["interval"], trial_days=p.get("trial_days"), visibility=p["visibility"], state="active",
                   approval_public_id=a.public_id, created_at=now, activated_at=now)
            s.add(t)
            a.status, a.decided_by_user_id, a.decided_at, a.executed_at, a.execution_ref = "executed", actor_user_id, now, now, t.public_id
            _stage(s, {**audit_decision, "target_id": public_id} if audit_decision else None, approval_public_id=public_id, plan_version_id=pv.id,
                   old_state="pending", new_state="approved")
            _stage(s, {**audit_activation, "target_id": t.public_id} if audit_activation else None, approval_public_id=public_id, plan_version_id=pv.id,
                   terms_version=nxt, amount_minor=t.amount_minor, currency=t.currency, old_state="retired" if prior else "none", new_state="active")
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise BillingConflict("The commercial terms changed while this ran; reload and retry.")
            return self._approval_view(a, s)

    # ------------------------------------------------------------------ refunds
    def _refunded(self, s, payment_id: int) -> int:
        return int(s.scalar(select(func.coalesce(func.sum(RF.amount_minor), 0)).where(RF.payment_id == payment_id, RF.state.in_(("pending", "succeeded")))) or 0)

    def _check_refundable(self, s, payment: PAY | None, amount: Any, currency_hint: str | None = None) -> int:
        if payment is None:
            raise BillingNotFound("payment")
        amount = validate_amount(amount)
        if amount <= 0:
            raise BillingValidationError("The refund amount must be greater than zero.")
        if payment.provider != P.PROVIDER_MOCK:
            raise BillingConflict("Only mock payments can be refunded here.")
        if payment.status != "succeeded":
            raise BillingConflict("Only a succeeded payment can be refunded.")
        if currency_hint is not None and currency_hint != payment.currency:
            raise BillingValidationError("The refund currency must match the payment.")
        if amount > payment.amount_minor - self._refunded(s, payment.id):
            raise BillingValidationError("The refund exceeds the amount still refundable.")
        return amount

    def request_refund(self, payment_public_id: str, *, amount_minor, reason, actor_user_id: int, audit: dict | None = None) -> dict:
        reason = self._reason(reason)
        with self._sf() as s:
            pay = s.scalar(select(PAY).where(PAY.public_id == payment_public_id))
            amount = self._check_refundable(s, pay, amount_minor)
            a = self._new_request(s, "refund", f"payment:{pay.id}", {"payment_public_id": pay.public_id, "amount_minor": amount, "currency": pay.currency},
                                  reason, actor_user_id, audit, payment_public_id=pay.public_id, amount_minor=amount, currency=pay.currency)
            s.commit()
            return self._approval_view(a, s)

    def decide_refund(self, public_id: str, *, approve: bool, actor_user_id: int, audit: dict | None = None) -> dict:
        now = self._clock()
        refund_public = None
        with self._sf() as s:
            a = self._decidable(s, public_id, "refund", actor_user_id, perm.BILLING_REFUND)
            if not approve:
                a.status, a.decided_by_user_id, a.decided_at = "rejected", actor_user_id, now
                _stage(s, {**audit, "target_id": public_id} if audit else None, approval_public_id=public_id, old_state="pending", new_state="rejected")
                s.commit()
                return self._approval_view(a, s)
            p = a.proposed_json
            pay = s.scalar(select(PAY).where(PAY.public_id == p["payment_public_id"]))
            amount = self._check_refundable(s, pay, p["amount_minor"], p["currency"])     # re-checked at approval time
            rf = RF(public_id=uuid.uuid4().hex, provider=pay.provider, payment_id=pay.id, amount_minor=amount, currency=pay.currency, state="pending",
                    approval_request_id=a.id, idempotency_key=f"refund:{a.public_id}", created_at=now)
            s.add(rf)
            a.status, a.decided_by_user_id, a.decided_at, a.execution_ref = "approved", actor_user_id, now, rf.public_id
            _stage(s, {**audit, "target_id": public_id} if audit else None, approval_public_id=public_id, payment_public_id=pay.public_id,
                   refund_public_id=rf.public_id, amount_minor=amount, currency=pay.currency, old_state="pending", new_state="approved")
            s.commit()
            refund_public = rf.public_id
        try:
            self._enqueue_refund(refund_public, actor_user_id)
        except Exception:
            with self._sf() as s:    # compensate: no approved refund without a job
                s.execute(update(AR).where(AR.public_id == public_id, AR.status == "approved").values(status="failed", failure_category="enqueue_failed"))
                s.execute(update(RF).where(RF.public_id == refund_public, RF.state == "pending").values(state="failed"))
                s.commit()
            raise BillingConflict("The refund could not be queued. Nothing was refunded.")
        with self._sf() as s:
            return self._approval_view(s.scalar(select(AR).where(AR.public_id == public_id)), s)

    def _enqueue_refund(self, refund_public_id: str, actor: int | None) -> None:
        if self._jobs is None:
            raise RuntimeError("jobs unavailable")
        self._jobs.enqueue(P.JOB_REFUND, {"refund_id": refund_public_id}, idempotency_key=f"refund-job:{refund_public_id}", actor_user_id=actor)

    def execute_refund(self, refund_public_id: str, *, last_attempt: bool = False, audit_repository_stage: Callable | None = None) -> str:
        """Run one approved refund through the provider. Idempotent: the provider receives a stable key, a replay after a crash returns the SAME
        provider refund id, and the local update is guarded, so the refund counts once. Returns the resulting refund state."""
        from src.billing.provider import ProviderRejected, ProviderRetryable

        with self._sf() as s:
            rf = s.scalar(select(RF).where(RF.public_id == refund_public_id))
            if rf is None:
                raise BillingNotFound(refund_public_id)
            if rf.state != "pending":
                return rf.state                                          # already executed (or failed): replay is a no-op
            pay = s.get(PAY, rf.payment_id)
            args = dict(idempotency_key=rf.idempotency_key, provider_payment_id=pay.provider_payment_id, amount_minor=rf.amount_minor, currency=rf.currency)
            approval = s.get(AR, rf.approval_request_id) if rf.approval_request_id else None
            approval_pid, payment_pid = (approval.public_id if approval else None), pay.public_id
        if self._provider is None:
            self._finish_refund(refund_public_id, None, False, "configuration_error", approval_pid, payment_pid)
            raise ProviderRejected("billing provider is not enabled")
        try:
            result = self._provider.refund(**args)
        except ProviderRetryable:
            if last_attempt:
                self._finish_refund(refund_public_id, None, False, "unavailable", approval_pid, payment_pid)
            raise
        except ProviderRejected:
            self._finish_refund(refund_public_id, None, False, "rejected", approval_pid, payment_pid)
            raise
        return self._finish_refund(refund_public_id, result.provider_refund_id, True, None, approval_pid, payment_pid)

    def _finish_refund(self, refund_public_id: str, provider_refund_id: str | None, ok: bool, category: str | None, approval_pid, payment_pid) -> str:
        from src.billing.audit_hook import build_execution_audit

        now = self._clock()
        with self._sf() as s:
            res = s.execute(update(RF).where(RF.public_id == refund_public_id, RF.state == "pending").values(
                state="succeeded" if ok else "failed", provider_refund_id=provider_refund_id, executed_at=now))
            if res.rowcount != 1:
                return s.scalar(select(RF.state).where(RF.public_id == refund_public_id)) or "failed"
            rf = s.scalar(select(RF).where(RF.public_id == refund_public_id))
            if rf.approval_request_id:
                s.execute(update(AR).where(AR.id == rf.approval_request_id).values(
                    status="executed" if ok else "failed", executed_at=now, failure_category=category))
            _stage(s, build_execution_audit(ok, refund_public_id, approval_pid, payment_pid, rf.amount_minor, rf.currency), )
            s.commit()
            return "succeeded" if ok else "failed"

    # ------------------------------------------------------------------ events (normalised, idempotent)
    def record_event(self, provider: str, provider_event_id: str, event_type: str, data: dict) -> tuple[dict, bool]:
        if provider not in P.PROVIDERS:
            raise BillingValidationError("Unknown billing provider.")
        if not isinstance(provider_event_id, str) or not (1 <= len(provider_event_id) <= 64):
            raise BillingValidationError("A provider event id is required.")
        clean = validate_event(event_type, data)
        now = self._clock()
        try:
            with self._sf() as s:
                existing = s.scalar(select(EV).where(EV.provider == provider, EV.provider_event_id == provider_event_id))
                if existing is not None:
                    return {"public_id": existing.public_id, "state": existing.state}, False
                ev = EV(public_id=uuid.uuid4().hex, provider=provider, provider_event_id=provider_event_id, event_type=event_type,
                        normalized_json=clean, state="received", received_at=now)
                s.add(ev)
                s.commit()
                return {"public_id": ev.public_id, "state": ev.state}, True
        except IntegrityError:
            with self._sf() as s:     # lost a concurrent duplicate ingest: same result
                ex = s.scalar(select(EV).where(EV.provider == provider, EV.provider_event_id == provider_event_id))
                return {"public_id": ex.public_id, "state": ex.state}, False

    def ingest_event(self, event: dict, *, process_inline: bool = False) -> tuple[dict, bool]:
        """record + enqueue. ``event`` is a normalised ``{provider, provider_event_id, event_type, data}``."""
        view, created = self.record_event(event["provider"], event["provider_event_id"], event["event_type"], event["data"])
        if created and self._jobs is not None and not process_inline:
            self._jobs.enqueue(P.JOB_PROCESS_EVENT, {"event_id": view["public_id"]}, idempotency_key=f"bevent:{view['public_id']}")
        elif process_inline:
            self.process_event(view["public_id"])
        return view, created

    def process_event(self, event_public_id: str) -> str:
        now = self._clock()
        with self._sf() as s:
            ev = s.scalar(select(EV).where(EV.public_id == event_public_id))
            if ev is None:
                raise BillingNotFound(event_public_id)
            if ev.state == "processed":
                return "processed"                                       # replay: nothing to do
            try:
                self._apply(s, ev.provider, ev.event_type, dict(ev.normalized_json), now)
            except BillingValidationError:
                s.rollback()
                with self._sf() as s2:
                    s2.execute(update(EV).where(EV.public_id == event_public_id).values(state="failed", failure_category="invalid_event"))
                    s2.commit()
                raise
            ev.state, ev.processed_at, ev.failure_category = "processed", now, None
            s.commit()
            return "processed"

    def _customer(self, s, provider: str, ref: str) -> CU:
        c = s.scalar(select(CU).where(CU.provider == provider, CU.provider_customer_id == ref))
        if c is None:
            raise BillingValidationError("Unknown customer reference.")
        return c

    def _apply(self, s, provider: str, kind: str, d: dict, now: datetime) -> None:
        if kind == "customer_created":
            uid, wid = d.get("user_id"), d.get("workspace_id")
            if (uid is None) == (wid is None):
                raise BillingValidationError("A customer belongs to exactly one subject.")
            if uid is not None and s.get(User, uid) is None or wid is not None and s.get(Workspace, wid) is None:
                raise BillingValidationError("Unknown subject.")
            if s.scalar(select(CU).where(CU.provider == provider, CU.provider_customer_id == d["customer_ref"])) is None:
                dup = s.scalar(select(CU).where(CU.provider == provider, CU.user_id == uid)) if uid is not None else \
                    s.scalar(select(CU).where(CU.provider == provider, CU.workspace_id == wid))
                if dup is None:
                    s.add(CU(public_id=uuid.uuid4().hex, provider=provider, provider_customer_id=d["customer_ref"], user_id=uid, workspace_id=wid,
                             state="active", created_at=now, updated_at=now))
        elif kind == "subscription_updated":
            if d["state"] not in P.PROVIDER_SUB_STATES:
                raise BillingValidationError("Unknown provider subscription state.")
            cust = self._customer(s, provider, d["customer_ref"])
            if s.get(PlanVersion, d["plan_version_id"]) is None:
                raise BillingValidationError("Unknown plan version.")
            terms = s.scalar(select(CT).where(CT.plan_version_id == d["plan_version_id"], CT.state == "active"))
            row = s.scalar(select(PS).where(PS.provider == provider, PS.provider_subscription_id == d["subscription_ref"]))
            vals = dict(customer_id=cust.id, plan_version_id=d["plan_version_id"], commercial_terms_id=terms.id if terms else None,
                        provider_state=d["state"], current_period_start=_when(d.get("period_start")), current_period_end=_when(d.get("period_end")),
                        grace_until=_when(d.get("grace_until")), updated_at=now)
            if row is None:
                s.add(PS(public_id=uuid.uuid4().hex, provider=provider, provider_subscription_id=d["subscription_ref"], created_at=now, **vals))
            else:
                for k, v in vals.items():
                    setattr(row, k, v)                                   # INFORMATIONAL: the W10.4 product subscription is never touched
        elif kind == "invoice_opened":
            cust = self._customer(s, provider, d["customer_ref"])
            amount, cur = validate_amount(d["amount_due_minor"]), validate_currency(d["currency"])
            sub = s.scalar(select(PS).where(PS.provider == provider, PS.provider_subscription_id == d["subscription_ref"])) if d.get("subscription_ref") else None
            if s.scalar(select(INV).where(INV.provider == provider, INV.provider_invoice_id == d["invoice_ref"])) is None:
                s.add(INV(public_id=uuid.uuid4().hex, provider=provider, provider_invoice_id=d["invoice_ref"], customer_id=cust.id,
                          provider_subscription_id=sub.id if sub else None, amount_due_minor=amount, amount_paid_minor=0, currency=cur, state="open",
                          period_start=_when(d.get("period_start")), period_end=_when(d.get("period_end")), due_at=_when(d.get("due_at")),
                          created_at=now, updated_at=now))
        elif kind == "invoice_paid":
            inv = self._invoice(s, provider, d["invoice_ref"])
            inv.state, inv.amount_paid_minor, inv.updated_at = "paid", inv.amount_due_minor, now
        elif kind in ("payment_succeeded", "payment_failed"):
            inv = self._invoice(s, provider, d["invoice_ref"])
            amount, cur = validate_amount(d["amount_minor"]), validate_currency(d["currency"])
            if cur != inv.currency:
                raise BillingValidationError("The payment currency does not match the invoice.")
            failed = kind == "payment_failed"
            cat = d.get("failure_category") if failed else None
            if failed and cat not in P.PAYMENT_FAILURE_CATEGORIES:
                raise BillingValidationError("Unknown failure category.")
            pay = s.scalar(select(PAY).where(PAY.provider == provider, PAY.provider_payment_id == d["payment_ref"]))
            if pay is None:
                s.add(PAY(public_id=uuid.uuid4().hex, provider=provider, provider_payment_id=d["payment_ref"], invoice_id=inv.id, amount_minor=amount,
                          currency=cur, status="failed" if failed else "succeeded", failure_category=cat, created_at=now, updated_at=now))
            if failed and inv.state != "paid":
                inv.state, inv.updated_at = "past_due", now              # billing metadata only: no access change, no suspension policy
        else:
            raise BillingValidationError("Unknown billing event.")

    def _invoice(self, s, provider: str, ref: str) -> INV:
        inv = s.scalar(select(INV).where(INV.provider == provider, INV.provider_invoice_id == ref))
        if inv is None:
            raise BillingValidationError("Unknown invoice reference.")
        return inv

    # ------------------------------------------------------------------ reads
    def _subject(self, s, c: CU) -> dict:
        if c.user_id is not None:
            u = s.get(User, c.user_id)
            return {"type": "user", "id": c.user_id, "label": u.email if u else None}
        w = s.get(Workspace, c.workspace_id)
        return {"type": "workspace", "id": c.workspace_id, "label": w.name if w else None}

    def list_invoices(self, *, state: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if state:
            if state not in P.INVOICE_STATES:
                raise BillingValidationError("Unknown state.")
            conds.append(INV.state == state)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(INV).where(*conds)) or 0
            rows = s.scalars(select(INV).where(*conds).order_by(INV.created_at.desc(), INV.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._invoice_view(s, i) for i in rows], "total": total, "page": page, "page_size": page_size}

    def _invoice_view(self, s, i: INV) -> dict:
        c = s.get(CU, i.customer_id)
        return {"public_id": i.public_id, "provider": i.provider, "provider_invoice_id": i.provider_invoice_id, "mock": True, "state": i.state,
                "amount_due_minor": i.amount_due_minor, "amount_paid_minor": i.amount_paid_minor, "currency": i.currency, "subject": self._subject(s, c),
                "period_start": _iso(i.period_start), "period_end": _iso(i.period_end), "due_at": _iso(i.due_at), "created_at": _iso(i.created_at)}

    def invoice_detail(self, public_id: str) -> dict:
        with self._sf() as s:
            i = s.scalar(select(INV).where(INV.public_id == public_id))
            if i is None:
                raise BillingNotFound(public_id)
            pays = s.scalars(select(PAY).where(PAY.invoice_id == i.id).order_by(PAY.id)).all()
            return {**self._invoice_view(s, i), "payments": [self._payment_view(s, p) for p in pays]}

    def _payment_view(self, s, p: PAY) -> dict:
        refunded = self._refunded(s, p.id)
        inv = s.get(INV, p.invoice_id)
        return {"public_id": p.public_id, "provider": p.provider, "provider_payment_id": p.provider_payment_id, "mock": True, "invoice_public_id": inv.public_id,
                "amount_minor": p.amount_minor, "currency": p.currency, "status": p.status, "failure_category": p.failure_category,
                "refunded_minor": refunded, "refundable_minor": max(0, p.amount_minor - refunded) if p.status == "succeeded" else 0,
                "created_at": _iso(p.created_at)}

    def list_payments(self, *, status: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if status:
            if status not in P.PAYMENT_STATUSES:
                raise BillingValidationError("Unknown status.")
            conds.append(PAY.status == status)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(PAY).where(*conds)) or 0
            rows = s.scalars(select(PAY).where(*conds).order_by(PAY.created_at.desc(), PAY.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._payment_view(s, p) for p in rows], "total": total, "page": page, "page_size": page_size}

    def payment_detail(self, public_id: str) -> dict:
        with self._sf() as s:
            p = s.scalar(select(PAY).where(PAY.public_id == public_id))
            if p is None:
                raise BillingNotFound(public_id)
            refunds = s.scalars(select(RF).where(RF.payment_id == p.id).order_by(RF.id)).all()
            return {**self._payment_view(s, p), "refunds": [self._refund_view(s, r) for r in refunds]}

    def _refund_view(self, s, r: RF) -> dict:
        pay = s.get(PAY, r.payment_id)
        return {"public_id": r.public_id, "provider": r.provider, "provider_refund_id": r.provider_refund_id, "mock": True, "payment_public_id": pay.public_id,
                "amount_minor": r.amount_minor, "currency": r.currency, "state": r.state, "created_at": _iso(r.created_at), "executed_at": _iso(r.executed_at)}

    def list_refunds(self, *, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(RF)) or 0
            rows = s.scalars(select(RF).order_by(RF.created_at.desc(), RF.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._refund_view(s, r) for r in rows], "total": total, "page": page, "page_size": page_size}

    def list_customers(self, *, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(CU)) or 0
            rows = s.scalars(select(CU).order_by(CU.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            out = []
            for c in rows:
                subs = s.scalars(select(PS).where(PS.customer_id == c.id).order_by(PS.id)).all()
                out.append({"public_id": c.public_id, "provider": c.provider, "provider_customer_id": c.provider_customer_id, "mock": True,
                            "subject": self._subject(s, c), "state": c.state,
                            "provider_subscriptions": [{"public_id": x.public_id, "provider_subscription_id": x.provider_subscription_id, "provider_state": x.provider_state,
                                                        "plan_version_id": x.plan_version_id, "current_period_end": _iso(x.current_period_end),
                                                        "grace_until": _iso(x.grace_until)} for x in subs]})
            return {"items": out, "total": total, "page": page, "page_size": page_size}

    def stats(self) -> dict:
        with self._sf() as s:
            return {"mock": True, "label": P.MODE_LABEL,
                    "open_invoices": s.scalar(select(func.count()).select_from(INV).where(INV.state == "open")) or 0,
                    "past_due_invoices": s.scalar(select(func.count()).select_from(INV).where(INV.state == "past_due")) or 0,
                    "failed_payments": s.scalar(select(func.count()).select_from(PAY).where(PAY.status == "failed")) or 0,
                    "pending_approvals": s.scalar(select(func.count()).select_from(AR).where(AR.status == "pending")) or 0,
                    "configured_plan_versions": s.scalar(select(func.count()).select_from(CT).where(CT.state == "active")) or 0}

    # ------------------------------------------------------------------ privacy integration (candidate-owned MOCK records)
    def export_for_user(self, user_id: int) -> dict:
        with self._sf() as s:
            custs = s.scalars(select(CU).where(CU.user_id == user_id)).all()
            ids = [c.id for c in custs]
            invs = s.scalars(select(INV).where(INV.customer_id.in_(ids))).all() if ids else []
            pays = s.scalars(select(PAY).where(PAY.invoice_id.in_([i.id for i in invs]))).all() if invs else []
            rfs = s.scalars(select(RF).where(RF.payment_id.in_([p.id for p in pays]))).all() if pays else []
            return {"simulated": True, "note": "MOCK billing records. No live payments are processed.",
                    "customers": [{"provider": c.provider, "state": c.state} for c in custs],
                    "invoices": [{"state": i.state, "amount_due_minor": i.amount_due_minor, "amount_paid_minor": i.amount_paid_minor, "currency": i.currency,
                                  "created_at": _iso(i.created_at)} for i in invs],
                    "payments": [{"status": p.status, "amount_minor": p.amount_minor, "currency": p.currency, "created_at": _iso(p.created_at)} for p in pays],
                    "refunds": [{"state": r.state, "amount_minor": r.amount_minor, "currency": r.currency} for r in rfs]}


def delete_billing_for(s, *, user_id: int | None = None, workspace_id: int | None = None) -> int:
    """Child-first explicit deletion of MOCK billing mirrors for a deleted subject (SQLite does not enforce cascades). Plan and terms stay."""
    cond = CU.user_id == user_id if user_id is not None else CU.workspace_id == workspace_id
    n = 0
    for c in s.scalars(select(CU).where(cond)).all():
        invs = s.scalars(select(INV).where(INV.customer_id == c.id)).all()
        for i in invs:
            for p in s.scalars(select(PAY).where(PAY.invoice_id == i.id)).all():
                for r in s.scalars(select(RF).where(RF.payment_id == p.id)).all():
                    s.delete(r)
                    n += 1
                s.delete(p)
                n += 1
            s.delete(i)
            n += 1
        for sub in s.scalars(select(PS).where(PS.customer_id == c.id)).all():
            s.delete(sub)
            n += 1
        s.delete(c)
        n += 1
    return n
