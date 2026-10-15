"""Account closure aware of unresolved subscriptions (W12.4D-F1R, owner decision A). The platform never silently destroys the account/subscription relationship while a
provider-managed recurring subscription is unresolved, and it never lets that obligation postpone a valid personal-data erasure.

Separate obligations, separate fields (never one boolean): (A) closure requested, (B) subscription resolution, (C) provider cancellation, (D) personal-data
erasure. ``assess`` is LOCAL and read-only: a link whose state is not terminal (``canceled`` or ``incomplete_expired``, which only authenticated reconciliation can
set), a state outside the known vocabulary (fail closed) or a checkout that can still be completed at the provider blocks the self-service closure. A cancellation
REQUEST is never treated as a cancellation, ``cancel_at_period_end`` is not termination, and nothing here claims or assumes that future charges have stopped.

Provider cancellation boundary (PROVIDER CONTRACT VALIDATION REQUIRED): Stripe's Managed Payments documentation says Link customers cancel or update
subscriptions on Link's own site and that Stripe cancels a customer's subscriptions when the customer requests data deletion; whether and how a SELLER may cancel
on a candidate's behalf under Managed Payments is not established. Ask4Mo therefore makes NO provider call: it guides the candidate (``provider_cancellation =
guided``) and waits for verified reconciliation evidence (``confirmed``). With the Null provider-state reader the resolution is ``unavailable`` (reported, never
invented).

Erasure independence: ``begin_retained_erasure`` lets the privacy-request deletion proceed regardless of the provider: personal and content data are erased, and
ONLY the minimum billing reference needed to finish the obligation (an anonymised ``deletion_requested`` account shell, its subscription links and linked checkout
attempts) is retained, recorded with a basis code and flagged for legal review. It is purged automatically when reconciliation shows every link terminal. No
retention period is invented here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import (
    ACCOUNT_STATUS_DELETION_REQUESTED, BillingAccountClosure as AC, BillingCheckoutSession as CS, BillingEntitlementDecision as ED, BillingProviderEvent as EV,
    BillingProviderLink as LINK, BillingRecoveryAction as RA, PROVIDER_LINK_STATES, PROVIDER_LINK_TERMINAL, CLOSURE_ACTIVE, User, utcnow,
)

RETENTION_BASIS = "unresolved_provider_obligation"
FAILURE_STATE_UNKNOWN = "state_unknown"


@dataclass
class Assessment:
    blocking: bool
    reasons: list[str] = field(default_factory=list)
    scheduled_only: bool = False          # every blocking link is merely scheduled to end: waiting, not acting
    link_ids: list[int] = field(default_factory=list)


def assess(s, user_id: int, now: datetime | None = None) -> Assessment:
    """LOCAL, read-only. Blocking reasons: ``live_subscription``, ``cancellation_scheduled``, ``payment_unresolved``, ``state_unknown``, ``checkout_in_progress``."""
    now = now or utcnow()
    reasons: list[str] = []
    ids: list[int] = []
    scheduled = True
    for link in s.scalars(select(LINK).where(LINK.user_id == user_id)).all():
        if link.provider_state in PROVIDER_LINK_TERMINAL:
            continue
        ids.append(link.id)
        if link.provider_state not in PROVIDER_LINK_STATES:
            reasons.append(FAILURE_STATE_UNKNOWN)
            scheduled = False
        elif link.provider_state in ("past_due", "unpaid"):
            reasons.append("payment_unresolved")
            scheduled = False
        elif link.cancel_at_period_end and link.provider_state == "active":
            reasons.append("cancellation_scheduled")
        else:
            reasons.append("live_subscription")
            scheduled = False
    for cs in s.scalars(select(CS).where(CS.user_id == user_id, CS.status.in_(("pending_creation", "open")))).all():
        linked = s.scalar(select(LINK.id).where(LINK.checkout_session_id == cs.id).limit(1)) is not None
        exp = cs.expires_at
        elapsed = exp is not None and (exp if exp.tzinfo else exp.replace(tzinfo=now.tzinfo)) <= now
        if not linked and not elapsed:
            reasons.append("checkout_in_progress")           # the hosted checkout can still be completed at the provider: wait for its expiry
            scheduled = False
    return Assessment(blocking=bool(reasons), reasons=sorted(set(reasons)), scheduled_only=bool(reasons) and scheduled, link_ids=ids)


def _fields(a: Assessment, reader_available: bool) -> dict:
    if not a.blocking:
        return {"status": "resolved", "subscription_resolution": "confirmed", "provider_cancellation": "confirmed", "failure_category": None, "review_required": False}
    if FAILURE_STATE_UNKNOWN in a.reasons:
        return {"status": "needs_review", "subscription_resolution": "unavailable", "provider_cancellation": "contract_unverified", "failure_category": FAILURE_STATE_UNKNOWN,
                "review_required": True}
    if a.scheduled_only:
        return {"status": "awaiting_provider", "subscription_resolution": "pending_confirmation", "provider_cancellation": "guided", "failure_category": None, "review_required": False}
    return {"status": "requested", "subscription_resolution": "required" if reader_available else "unavailable", "provider_cancellation": "guided",
            "failure_category": None if reader_available else "provider_reader_unavailable", "review_required": False}


def view(case: AC | None) -> dict | None:
    if case is None:
        return None
    return {"status": case.status, "subscription_resolution": case.subscription_resolution, "provider_cancellation": case.provider_cancellation,
            "erasure_status": case.erasure_status, "review_required": case.review_required,
            "requested_at": case.requested_at.isoformat() if case.requested_at else None}


def active_case(s, user_id: int) -> AC | None:
    return s.scalar(select(AC).where(AC.user_id == user_id, AC.status.in_(CLOSURE_ACTIVE)))


def refresh(s, user_id: int, *, reader_available: bool, now: datetime | None = None) -> AC | None:
    """Recompute an ACTIVE case from verified local state (called inside the caller's transaction). A retained-erasure case whose subscriptions are all terminal is
    purged here (the minimum billing reference has served its purpose)."""
    now = now or utcnow()
    case = active_case(s, user_id)
    if case is None:
        return None
    a = assess(s, user_id, now)
    case.last_checked_at = now
    if case.status == "erased_reference_retained":
        if not a.blocking:
            purge_retained(s, user_id, case, now)
        return case
    for k, v in _fields(a, reader_available).items():
        setattr(case, k, v)
    return case


def purge_retained(s, user_id: int, case: AC, now: datetime) -> None:
    """Remove the retained shell (anonymised account, links, linked checkouts) once every subscription is terminal; the case row keeps states and timestamps only."""
    link_ids = [i for (i,) in s.execute(select(LINK.id).where(LINK.user_id == user_id)).all()]
    if link_ids:
        s.execute(update(EV).where(EV.link_id.in_(link_ids)).values(link_id=None))
        s.execute(update(RA).where(RA.link_id.in_(link_ids)).values(link_id=None))
        for d in s.scalars(select(ED).where(ED.link_id.in_(link_ids))).all():
            s.delete(d)
        for link in s.scalars(select(LINK).where(LINK.id.in_(link_ids))).all():
            s.delete(link)
    for cs in s.scalars(select(CS).where(CS.user_id == user_id)).all():
        s.delete(cs)
    s.execute(update(RA).where(RA.actor_user_id == user_id).values(actor_user_id=None))
    shell = s.get(User, user_id)
    case.status, case.erasure_status, case.subscription_resolution, case.provider_cancellation = "completed", "fulfilled", "confirmed", "confirmed"
    case.completed_at, case.review_required, case.retention_basis, case.user_id = now, False, None, None
    s.flush()
    if shell is not None and shell.status == ACCOUNT_STATUS_DELETION_REQUESTED and shell.provider == "closed":
        s.delete(shell)


class ClosureService:
    def __init__(self, session_factory, *, reader_available: bool = False, audit: object | None = None, clock: Callable[[], datetime] = utcnow) -> None:
        self._sf, self._reader, self._audit, self._clock = session_factory, reader_available, audit, clock

    def request(self, user_id: int) -> dict:
        """Self-service closure request. Returns ``{"proceed": True}`` when nothing is unresolved (the caller performs the normal deletion, which completes any case);
        otherwise records ONE durable case (idempotent; concurrent requests share it) and returns it with ``proceed = False``."""
        now = self._clock()
        with self._sf() as s:
            a = assess(s, user_id, now)
            case = active_case(s, user_id)
            if not a.blocking:
                if case is not None and case.status != "erased_reference_retained":
                    refresh(s, user_id, reader_available=self._reader, now=now)
                    s.commit()
                return {"proceed": True, "blocking": False, "reasons": [], "case": view(active_case(s, user_id))}
            if case is None:
                case = AC(public_id=uuid.uuid4().hex, user_id=user_id, requested_at=now, **_fields(a, self._reader))
                s.add(case)
                try:
                    s.commit()
                    self._record("billing.account_closure_requested", user_id, case.public_id, reasons=",".join(a.reasons))
                except IntegrityError:                      # a concurrent request created it first: share that case
                    s.rollback()
                    case = active_case(s, user_id)
            else:
                refresh(s, user_id, reader_available=self._reader, now=now)
                s.commit()
            return {"proceed": False, "blocking": True, "reasons": a.reasons, "case": view(active_case(s, user_id))}

    def status(self, user_id: int) -> dict | None:
        with self._sf() as s:
            return view(active_case(s, user_id))

    def begin_retained_erasure(self, user_id: int, privacy_request_public_id: str | None = None) -> bool:
        """For the privacy-request deletion path. Returns True when the erasure must RETAIN the minimum billing reference (a subscription is unresolved); the erasure itself
        is never postponed. Records the restriction with a basis code and flags it for legal review."""
        now = self._clock()
        with self._sf() as s:
            a = assess(s, user_id, now)
            if not a.blocking:
                return False
            case = active_case(s, user_id)
            if case is None:
                case = AC(public_id=uuid.uuid4().hex, user_id=user_id, requested_at=now, **_fields(a, self._reader))
                s.add(case)
            case.status, case.erasure_status, case.retention_basis, case.review_required = "erased_reference_retained", "restricted", RETENTION_BASIS, True
            case.privacy_request_public_id = privacy_request_public_id
            case.last_checked_at = now
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
            self._record("billing.erasure_reference_retained", user_id, case.public_id, basis=RETENTION_BASIS)
            return True

    def _record(self, name: str, user_id: int, case_ref: str, **ctx) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=name, result="success", actor_user_id=user_id, target_type="billing_account_closure", target_id=case_ref, context=ctx or None)
        except Exception:  # noqa: BLE001 - an audit write problem never changes the closure outcome
            pass
