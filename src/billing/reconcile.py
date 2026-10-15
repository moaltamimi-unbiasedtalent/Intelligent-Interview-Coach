"""Provider event acceptance, durable processing and reconciliation (W12.4D-D).

Six separate steps, never collapsed: (1) webhook authentication (``stripe_events.verify_signature``, route layer); (2) ACCEPTANCE of an authenticated
event, which is only its durable storage; (3) idempotent claim and processing under a lease; (4) reconciliation of the provider's AUTHORITATIVE
subscription state into a verified local link (ownership, price mapping, environment, stale-state and terminal-state guards); (5) the subscription
facts (checkout, payment, subscription, refund, dispute: separate columns); (6) the entitlement DECISION, taken only by ``entitlement_bridge`` under an
explicit policy. The event is a trigger, not the truth: state always comes from the provider-state reader, never from the event body or its arrival order.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from src.billing import policy as P
from src.billing import stripe_events as SE
from src.billing.entitlement_bridge import EntitlementPolicy, evaluate_and_apply
from src.billing.provider_state import (
    ProviderStateError, ProviderStateInvalid, ProviderStateNotFound, ProviderStateReader, ProviderStateUnavailable, SubscriptionSnapshot,
)
from src.persistence import (
    BillingCheckoutSession as CS, BillingCommercialTerms as CT, BillingProviderEvent as EV, BillingProviderLink as LINK, BillingProviderPrice as PP,
    PROVIDER_LINK_STATES, PROVIDER_LINK_TERMINAL, utcnow,
)

_REFUND_RANK = {"none": 0, "partial": 1, "full": 2}
_FAILURE_CATEGORIES = ("concurrent_update", "provider_unavailable", "provider_timeout", "rate_limited", "provider_auth_failed", "provider_permission_denied", "invalid_request", "internal_error", "retries_exhausted", "provider_state_invalid", "provider_resource_not_found", "unknown_ownership",
                       "ownership_ambiguous", "checkout_mismatch", "customer_rebind", "customer_mismatch", "price_mismatch", "price_unverifiable",
                       "duplicate_subscription", "environment_mismatch", "unknown_provider_state", "terminal_reactivation_refused", "integrity_conflict",
                       "unsupported_event_type", "unsupported_api_version", "unexpected_account_context", "not_subscription_related", "not_enabled")


class _Quarantine(Exception):
    def __init__(self, category: str, *, review: bool = False) -> None:
        super().__init__(category)
        self.category, self.review = category, review


class RecoveryKeyConflict(Exception):
    """The Idempotency-Key was already used for a different recovery request (another action or another operator)."""


class _Retry(Exception):
    """A benign concurrency loss (another worker committed first): safe to re-run against the new state; never an operator problem."""

    def __init__(self, category: str = "concurrent_update") -> None:
        super().__init__(category)
        self.category = category


def link_by_subscription_stmt(provider: str, environment: str, subscription_id: str, *, lock: bool = False):
    """The link lookup. ``lock=True`` adds ``FOR UPDATE`` (PostgreSQL row lock; ignored by SQLite) so two workers reconciling the SAME subscription serialise
    and a slower, older observation can never commit over a newer one."""
    stmt = select(LINK).where(LINK.provider == provider, LINK.environment == environment, LINK.provider_subscription_id == subscription_id)
    return stmt.with_for_update() if lock else stmt


def _aware(dt: datetime | None, like: datetime) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=like.tzinfo)


@dataclass
class Result:
    status: str                      # processed | ignored | quarantined | needs_review | retry | skipped | failed
    category: str | None = None
    link_public_id: str | None = None
    decision: str | None = None


class ProviderEventService:
    def __init__(self, session_factory, *, environment: str, reader: ProviderStateReader, policy: EntitlementPolicy, audit: Any = None,
                 clock: Callable[[], datetime] = utcnow) -> None:
        if policy.synthetic:                         # a SYNTHETIC test policy is never an owner decision: refuse it anywhere but development and test
            import os

            from src.billing.provider import MOCK_ALLOWED_ENVS
            if (os.environ.get("API_ENV") or "development").strip().lower() not in MOCK_ALLOWED_ENVS:
                raise ValueError("A synthetic entitlement policy cannot be used outside development and test.")
        self._sf, self._env, self._reader, self._policy, self._audit, self._clock = session_factory, environment, reader, policy, audit, clock

    # ------------------------------------------------------------------ acceptance (durable storage; no reconciliation here)
    def accept(self, event: dict, *, correlation_id: str | None = None) -> dict:
        """Persist an AUTHENTICATED, environment-validated event. Returns ``{"disposition", "public_id"}``; ``disposition`` is accepted | duplicate | ignored.
        Raises on a storage failure so the route can return a retryable error instead of acknowledging an event that was not stored."""
        env = SE.require_environment(event, self._env)
        now = self._clock()
        etype = event["type"]
        status, category, norm = "received", None, {}
        if event.get("account"):
            status, category = "ignored", "unexpected_account_context"           # Connect-style context: Managed Payments does not support it
        elif event.get("api_version") not in SE.SUPPORTED_API_VERSIONS:
            status, category = "ignored", "unsupported_api_version"
        elif etype not in SE.EVENT_KINDS:
            status, category = "ignored", "unsupported_event_type"
        else:
            n = SE.normalise(event)
            norm = {"kind": n.kind, "subscription_id": n.subscription_id, **n.fields}
        obj_id = SE._id(event["data"]["object"].get("id"))
        row = EV(public_id=uuid.uuid4().hex, provider=P.PROVIDER_STRIPE_MP, environment=env, provider_event_id=event["id"], event_type=etype[:64],
                 api_version=(event.get("api_version") if isinstance(event.get("api_version"), str) else None), provider_object_id=obj_id,
                 provider_created_at=SE.created_at(event), received_at=now, status=status, failure_category=category, normalized_json=norm,
                 correlation_id=correlation_id, processed_at=now if status == "ignored" else None)
        try:
            with self._sf() as s:
                s.add(row)
                s.commit()
                public_id = row.public_id
        except IntegrityError:
            with self._sf() as s:
                existing = s.scalar(select(EV).where(EV.provider == P.PROVIDER_STRIPE_MP, EV.environment == env, EV.provider_event_id == event["id"]))
                if existing is None:
                    raise
                self._record("billing.webhook_duplicate_ignored", "success", existing.public_id, correlation_id)
                return {"disposition": "duplicate", "public_id": existing.public_id}
        self._record("billing.webhook_event_accepted" if status == "received" else "billing.webhook_event_ignored", "success", public_id, correlation_id,
                     event_type=etype if etype in SE.EVENT_KINDS else "unsupported", category=category)
        return {"disposition": "ignored" if status == "ignored" else "accepted", "public_id": public_id}

    # ------------------------------------------------------------------ processing
    def _claim(self, public_id: str, now: datetime) -> bool:
        runnable = or_(
            and_(EV.status.in_(("received", "failed")), or_(EV.next_attempt_at.is_(None), EV.next_attempt_at <= now)),
            and_(EV.status == "processing", EV.lease_until < now))
        with self._sf() as s:
            res = s.execute(update(EV).where(EV.public_id == public_id, EV.attempt_count < EV.attempt_limit, runnable).values(
                status="processing", lease_until=now + timedelta(seconds=P.EVENT_LEASE_SECONDS), attempt_count=EV.attempt_count + 1, last_attempt_at=now))
            s.commit()
            return res.rowcount == 1

    def process(self, public_id: str) -> Result:
        now = self._clock()
        if not self._claim(public_id, now):
            with self._sf() as s:
                ev = s.scalar(select(EV).where(EV.public_id == public_id))
                if ev is None:
                    return Result("skipped", "not_found")
                if ev.attempt_count >= ev.attempt_limit and ev.status in ("received", "failed", "processing"):
                    ev.status, ev.failure_category, ev.lease_until = "needs_review", "retries_exhausted", None
                    s.commit()
                    self._record("billing.webhook_processing_failed", "failure", public_id, ev.correlation_id, category="retries_exhausted")
                    return Result("needs_review", "retries_exhausted")
            return Result("skipped")                                          # already processed, ignored, or being processed by someone else
        with self._sf() as s:
            ev = s.scalar(select(EV).where(EV.public_id == public_id))
            corr = ev.correlation_id
        self._record("billing.webhook_processing_started", "success", public_id, corr)
        try:
            with self._sf() as s:
                ev = s.scalar(select(EV).where(EV.public_id == public_id))
                result = self._reconcile_event(s, ev, now)
                if result.status in ("processed", "ignored"):
                    ev.status, ev.processed_at, ev.failure_category, ev.lease_until = result.status, now, result.category, None
                s.commit()
        except ProviderStateUnavailable as exc:
            return self._finish(public_id, "retry", exc.category, now, corr)
        except ProviderStateNotFound:
            return self._finish(public_id, "quarantined", "provider_resource_not_found", now, corr)
        except ProviderStateInvalid:
            return self._finish(public_id, "needs_review", "provider_state_invalid", now, corr)
        except _Quarantine as q:
            return self._finish(public_id, "needs_review" if q.review else "quarantined", q.category, now, corr)
        except _Retry as r:
            return self._finish(public_id, "retry", r.category, now, corr)
        except IntegrityError:
            return self._finish(public_id, "retry", "concurrent_update", now, corr)     # a lost race on a unique key is retried (bounded), not quarantined
        except Exception:  # noqa: BLE001 - never surface internals; the category is bounded
            return self._finish(public_id, "retry", "internal_error", now, corr)
        self._record("billing.webhook_processing_succeeded", "success", public_id, corr, link=result.link_public_id, decision=result.decision)
        return result

    def _finish(self, public_id: str, status: str, category: str, now: datetime, corr) -> Result:
        """Persist a non-success disposition in its own transaction (the work transaction was rolled back)."""
        with self._sf() as s:
            ev = s.scalar(select(EV).where(EV.public_id == public_id))
            category = category if category in _FAILURE_CATEGORIES else "internal_error"
            ev.failure_category, ev.lease_until = category, None
            if status == "retry":
                if ev.attempt_count >= ev.attempt_limit:
                    ev.status, ev.failure_category = "needs_review", "retries_exhausted"
                    status = "needs_review"
                else:
                    ev.status = "failed"
                    ev.next_attempt_at = now + timedelta(seconds=min(P.EVENT_BACKOFF_CAP_SECONDS, P.EVENT_BACKOFF_BASE_SECONDS * 2 ** max(0, ev.attempt_count - 1)))
            else:
                ev.status = status
            s.commit()
        self._record("billing.webhook_processing_failed", "failure", public_id, corr, category=category, disposition=status)
        return Result(status, category)

    def _reconcile_event(self, s, ev: EV, now: datetime) -> Result:
        norm = dict(ev.normalized_json or {})
        sub_id = norm.get("subscription_id")
        kind = norm.get("kind")
        if sub_id is None and kind in ("refund", "dispute"):
            sub_id = self._reader.subscription_for_payment(payment_intent=norm.get("payment_intent"), charge=norm.get("charge_id"))
        if sub_id is None and kind == "checkout" and norm.get("checkout_session_id"):
            sub_id = self._reader.checkout_session(norm["checkout_session_id"]).subscription_id
        if sub_id is None:
            return Result("ignored", "not_subscription_related")
        link, info, outcome = self._reconcile_subscription(s, sub_id, ev, norm, now)
        ev.link_id = link.id
        ev.reconciliation_json = info
        return Result("processed", None, link.public_id, outcome.decision)

    # ------------------------------------------------------------------ reconciliation core (events AND periodic refresh)
    def _reconcile_subscription(self, s, sub_id: str, ev: EV | None, norm: dict, now: datetime):
        snap = self._reader.get_subscription(sub_id)
        env = ev.environment if ev is not None else self._env
        if snap.livemode != (env == "live"):
            raise _Quarantine("environment_mismatch")
        if snap.state not in PROVIDER_LINK_STATES:
            raise _Quarantine("unknown_provider_state", review=True)
        link = s.scalar(link_by_subscription_stmt(P.PROVIDER_STRIPE_MP, env, sub_id, lock=True))
        created = link is None
        if created:
            link = self._bind_new(s, snap, norm, env, now)
        else:
            self._verify_existing(s, link, snap)
        previous = link.provider_state
        info: dict = {"source": "provider_state", "observed_state": snap.state, "previous_state": None if created else previous,
                      "event_type": ev.event_type if ev is not None else "periodic_refresh", "linked": created}
        stale = (not created and link.observed_at is not None and snap.observed_at < _aware(link.observed_at, snap.observed_at))
        if stale:
            info["disposition"] = "stale_snapshot_not_applied"                       # an older read never overwrites a newer reconciled state
        elif not created and previous in PROVIDER_LINK_TERMINAL and snap.state not in PROVIDER_LINK_TERMINAL:
            # canceled is final at the provider (Stripe: "a terminal state that cannot be updated"): a later "active" reading is not believed or applied
            raise _Quarantine("terminal_reactivation_refused", review=True)
        else:
            link.provider_state, link.cancel_at_period_end = snap.state, snap.cancel_at_period_end
            link.current_period_end, link.latest_invoice_state, link.observed_at = snap.current_period_end, snap.latest_invoice_state, snap.observed_at
            link.reconcile_count += 1
            link.review_category = None
            info["disposition"] = "applied"
            implied = {"customer.subscription.deleted": "canceled", "customer.subscription.paused": "paused", "customer.subscription.resumed": "active"}.get(info["event_type"])
            if implied and implied != snap.state:
                info["conflict"] = "event_superseded_by_provider_state"              # recorded, not hidden: the provider's current state won
        self._merge_facts(link, norm)
        outcome = evaluate_and_apply(s, link, self._policy, event_id=ev.id if ev is not None else None, now=now)
        info["entitlement"] = {"decision": outcome.decision, "reason": outcome.reason, "applied": outcome.applied}
        s.flush()
        return link, info, outcome

    def _bind_new(self, s, snap: SubscriptionSnapshot, norm: dict, env: str, now: datetime) -> LINK:
        assoc = self._reader.checkout_for_subscription(snap.subscription_id)
        if assoc is None or not assoc.client_reference_id:
            raise _Quarantine("unknown_ownership")                                     # never matched by email or by a request-supplied id
        if assoc.livemode != snap.livemode:
            raise _Quarantine("environment_mismatch")
        if norm.get("client_reference_id") and norm["client_reference_id"] != assoc.client_reference_id:
            raise _Quarantine("ownership_ambiguous", review=True)
        cs = s.scalar(select(CS).where(CS.public_id == assoc.client_reference_id, CS.provider == P.PROVIDER_STRIPE_MP, CS.environment == env))
        if cs is None or cs.provider_session_id != assoc.session_id:
            raise _Quarantine("checkout_mismatch")
        mapping, terms = s.get(PP, cs.price_mapping_id), s.get(CT, cs.commercial_terms_id)
        if mapping is None or terms is None or mapping.environment != env or mapping.commercial_terms_id != terms.id:
            raise _Quarantine("price_mismatch")
        if snap.price_id != mapping.provider_price_id:
            raise _Quarantine("price_mismatch")
        if None in (snap.currency, snap.interval, snap.unit_amount):
            raise _Quarantine("price_unverifiable", review=True)
        if (snap.currency, snap.interval, snap.unit_amount) != (terms.currency, terms.billing_interval, terms.amount_minor):
            raise _Quarantine("price_mismatch")
        other = s.scalar(select(LINK.user_id).where(LINK.provider == P.PROVIDER_STRIPE_MP, LINK.environment == env, LINK.provider_customer_id == snap.customer_id,
                                                    LINK.user_id != cs.user_id).limit(1))
        if other is not None:
            raise _Quarantine("customer_rebind", review=True)                          # one provider customer, one candidate, ever
        link = LINK(public_id=uuid.uuid4().hex, provider=P.PROVIDER_STRIPE_MP, environment=env, provider_subscription_id=snap.subscription_id,
                    provider_customer_id=snap.customer_id, user_id=cs.user_id, checkout_session_id=cs.id, plan_version_id=cs.plan_version_id,
                    commercial_terms_id=terms.id, price_mapping_id=mapping.id, provider_state=snap.state, cancel_at_period_end=snap.cancel_at_period_end,
                    current_period_end=snap.current_period_end, latest_invoice_state=snap.latest_invoice_state, observed_at=None, created_at=now, updated_at=now)
        s.add(link)
        try:
            s.flush()
        except IntegrityError:
            s.rollback()
            if s.scalar(link_by_subscription_stmt(P.PROVIDER_STRIPE_MP, env, snap.subscription_id)) is not None:
                raise _Retry() from None                                              # the SAME subscription was bound a moment ago by another worker: re-run against it
            raise _Quarantine("duplicate_subscription", review=True) from None        # a second live provider subscription for the same candidate
        return link

    def _verify_existing(self, s, link: LINK, snap: SubscriptionSnapshot) -> None:
        if snap.customer_id != link.provider_customer_id:
            raise _Quarantine("customer_mismatch", review=True)
        mapping = s.get(PP, link.price_mapping_id)
        if mapping is None or snap.price_id != mapping.provider_price_id:
            raise _Quarantine("price_mismatch", review=True)

    @staticmethod
    def _merge_facts(link: LINK, norm: dict) -> None:
        """Refund and dispute facts are monotonic provider facts: a refund never un-refunds and a lost dispute never reverts."""
        if norm.get("kind") == "refund":
            amount, refunded = norm.get("amount"), norm.get("amount_refunded")
            state = "full" if norm.get("refunded") or (amount and refunded and refunded >= amount) else ("partial" if refunded else "none")
            if _REFUND_RANK[state] > _REFUND_RANK[link.refund_state]:
                link.refund_state = state
        elif norm.get("kind") == "dispute":
            status = norm.get("dispute_status") or ""
            if link.dispute_state == "lost":
                return
            if status == "lost":
                link.dispute_state = "lost"
            elif status == "won":
                link.dispute_state = "won"
            elif status == "warning_closed":
                link.dispute_state = "none"
            elif status:
                link.dispute_state = "open"

    # ------------------------------------------------------------------ periodic reconciliation (mockable; polling is not enabled in this wave)
    def sweep(self, *, limit: int = P.RECONCILE_SWEEP_BATCH) -> dict:
        now = self._clock()
        counts = {"events": 0, "exhausted": 0, "links_refreshed": 0, "checkouts_checked": 0, "unavailable": 0, "failed": 0}
        with self._sf() as s:
            due = s.scalars(select(EV.public_id).where(or_(
                and_(EV.status == "received", EV.received_at <= now - timedelta(seconds=60)),
                and_(EV.status == "failed", or_(EV.next_attempt_at.is_(None), EV.next_attempt_at <= now)),
                and_(EV.status == "processing", EV.lease_until < now))).order_by(EV.received_at).limit(limit)).all()
        for public_id in due:
            r = self.process(public_id)
            counts["exhausted" if r.category == "retries_exhausted" else "events"] += 1
        with self._sf() as s:
            stale_links = s.scalars(select(LINK.provider_subscription_id).where(
                LINK.environment == self._env, LINK.provider_state.notin_(PROVIDER_LINK_TERMINAL),
                or_(LINK.observed_at.is_(None), LINK.observed_at <= now - timedelta(seconds=P.RECONCILE_STALE_AFTER_SECONDS))).limit(limit)).all()
            pending = s.execute(select(CS.id, CS.provider_session_id).where(
                CS.environment == self._env, CS.status == "open", CS.provider_session_id.isnot(None),
                or_(CS.browser_returned_at.isnot(None), CS.created_at <= now - timedelta(seconds=P.PENDING_CHECKOUT_RECHECK_SECONDS)),
                ~select(LINK.id).where(LINK.checkout_session_id == CS.id).exists()).limit(limit)).all()
        for sub_id in stale_links:
            self._refresh(sub_id, counts, "links_refreshed")
        for _cid, session_id in pending:
            try:
                assoc = self._reader.checkout_session(session_id)
            except ProviderStateUnavailable:
                counts["unavailable"] += 1
                continue
            except ProviderStateError:
                counts["failed"] += 1
                continue
            counts["checkouts_checked"] += 1
            if assoc.subscription_id:
                self._refresh(assoc.subscription_id, counts, None)
        return counts

    def _refresh(self, sub_id: str, counts: dict, key: str | None) -> None:
        now = self._clock()
        try:
            with self._sf() as s:
                link, info, _ = self._reconcile_subscription(s, sub_id, None, {}, now)
                s.commit()
                self._record("billing.reconciliation_performed", "success", None, None, link=link.public_id, disposition=info.get("disposition"))
            if key:
                counts[key] += 1
        except ProviderStateUnavailable:
            counts["unavailable"] += 1
        except Exception:  # noqa: BLE001 - one bad subscription must not stop the sweep; the next sweep re-reads it
            counts["failed"] += 1

    # ------------------------------------------------------------------ operator recovery (W12.4D-E): bounded, idempotent, audited, fail closed
    MAX_OPERATOR_RETRIES = 3
    OPERATOR_EXTRA_ATTEMPTS = 3

    def reader_available(self) -> bool:
        """False for the runtime Null reader: no recovery action may then pretend to synchronise with a provider."""
        from src.billing.provider_state import NullStateReader
        return not isinstance(self._reader, NullStateReader)

    def recover(self, action: str, target_public_id: str, *, actor_user_id: int, reason: str, idempotency_key: str, audit: dict | None = None) -> dict:
        """Run ONE operator recovery action. Returns ``{"public_id", "action", "status", "result", "replayed"}``. A replay of the same idempotency key returns the stored
        outcome and runs nothing. Prerequisites that are missing REFUSE the action (recorded, nothing changed). The action only re-drives the existing verified
        pipeline (claim, provider-state read, ownership and price guards, entitlement policy): it cannot forge an event, edit a financial fact, delete evidence,
        grant access directly, or accept a caller-supplied provider id as ownership (the target is always one of OUR record ids)."""
        from src.persistence import BillingRecoveryAction as RA

        if action not in ("retry_event", "requeue_lease", "reconcile_link"):
            raise ValueError("unknown recovery action")
        now = self._clock()
        row = RA(public_id=uuid.uuid4().hex, action=action, actor_user_id=actor_user_id, reason=reason, idempotency_key=idempotency_key, status="requested", created_at=now)
        try:
            with self._sf() as s:
                s.add(row)
                s.commit()
                pid = row.public_id
        except IntegrityError:
            with self._sf() as s:
                prior = s.scalar(select(RA).where(RA.idempotency_key == idempotency_key))
                if prior is None or prior.action != action or prior.actor_user_id != actor_user_id:
                    raise RecoveryKeyConflict("idempotency key already used") from None
                return {"public_id": prior.public_id, "action": prior.action, "status": prior.status, "result": prior.result_category, "replayed": True}
        self._record("billing.recovery_requested", "success", target_public_id, None, action=action, actor=actor_user_id)
        status, category, prev, event_id, link_id = "refused", "unknown_error", None, None, None
        try:
            status, category, prev, event_id, link_id = self._do_recover(action, target_public_id, now)
        except Exception:  # noqa: BLE001 - bounded: the action row records a safe category, never the exception text
            status, category = "failed", "internal_error"
        with self._sf() as s:
            r = s.scalar(select(RA).where(RA.public_id == pid))
            r.status, r.result_category, r.previous_status, r.event_id, r.link_id, r.completed_at = status, category, prev, event_id, link_id, self._clock()
            if audit:                                           # the admin audit row commits in the SAME transaction as the recorded outcome
                from src.admin_repository import _stage
                _stage(s, {**audit, "result": "success" if status == "completed" else "failure"}, action=action, status=status, category=category)
            s.commit()
        self._record({"completed": "billing.recovery_completed", "failed": "billing.recovery_failed"}.get(status, "billing.recovery_refused"),
                     "success" if status == "completed" else "failure", target_public_id, None, action=action, actor=actor_user_id, category=category)
        return {"public_id": pid, "action": action, "status": status, "result": category, "replayed": False}

    def _do_recover(self, action: str, target: str, now: datetime):
        """-> (status, result category, previous event status, event id, link id)"""
        if not self.reader_available():
            return "refused", "reader_unavailable", None, None, None                  # fail closed: never report success without a provider-state reader
        if action == "reconcile_link":
            with self._sf() as s:
                link = s.scalar(select(LINK).where(LINK.public_id == target))
                if link is None or link.environment != self._env or link.provider != P.PROVIDER_STRIPE_MP:
                    return "refused", "not_found", None, None, None
                sub_id, link_id = link.provider_subscription_id, link.id
            try:
                with self._sf() as s:
                    self._reconcile_subscription(s, sub_id, None, {}, now)
                    s.commit()
            except ProviderStateUnavailable:
                return "failed", "provider_unavailable", None, None, link_id
            except ProviderStateError as exc:
                return "failed", exc.__class__.__name__.replace("ProviderState", "").lower() or "provider_error", None, None, link_id
            except _Quarantine as q:
                return "failed", q.category if q.category in _FAILURE_CATEGORIES else "internal_error", None, None, link_id
            except (_Retry, IntegrityError):
                return "failed", "concurrent_update", None, None, link_id
            return "completed", "reconciled", None, None, link_id
        with self._sf() as s:
            ev = s.scalar(select(EV).where(EV.public_id == target))
            if ev is None or ev.environment != self._env or ev.provider != P.PROVIDER_STRIPE_MP:
                return "refused", "not_found", None, None, None
            prev, event_id = ev.status, ev.id
            if action == "retry_event":
                if ev.status not in ("failed", "needs_review", "quarantined"):
                    return "refused", "event_not_retryable", prev, event_id, None
                if ev.operator_retries >= self.MAX_OPERATOR_RETRIES:
                    return "refused", "operator_retry_limit_reached", prev, event_id, None
                res = s.execute(update(EV).where(EV.id == ev.id, EV.status == prev, EV.operator_retries < self.MAX_OPERATOR_RETRIES).values(
                    status="failed", next_attempt_at=now, lease_until=None, operator_retries=EV.operator_retries + 1,
                    attempt_limit=EV.attempt_count + self.OPERATOR_EXTRA_ATTEMPTS).execution_options(synchronize_session=False))
            else:      # requeue_lease: only an ABANDONED lease (expired) of a processing event
                lease = _aware(ev.lease_until, now)
                if ev.status != "processing" or lease is None or lease >= now:
                    return "refused", "lease_not_abandoned", prev, event_id, None
                res = s.execute(update(EV).where(EV.id == ev.id, EV.status == "processing", EV.lease_until < now).values(
                    status="failed", next_attempt_at=now, lease_until=None).execution_options(synchronize_session=False))
            if res.rowcount != 1:
                s.rollback()
                return "refused", "concurrent_change", prev, event_id, None
            s.commit()
        result = self.process(target)                                                  # through the SAME claim, reader, guards and policy as any event
        category = result.category or result.status
        return ("completed" if result.status in ("processed", "ignored") else "failed"), category, prev, event_id, None

    # ------------------------------------------------------------------ audit (ids and bounded categories only; never a payload)
    def _record(self, name: str, result: str, target: str | None, correlation: str | None, **ctx: Any) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=name, result=result, target_type="billing_provider_event", target_id=target, request_id=correlation,
                               context={"environment": self._env, **{k: v for k, v in ctx.items() if v is not None}})
        except Exception:  # noqa: BLE001 - an audit write problem must not change the billing outcome
            pass

