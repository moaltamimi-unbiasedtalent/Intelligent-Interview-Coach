"""Billing operations read models for Admin (W12.4D-E): overview, subscriptions, checkout diagnostics, webhook events, reconciliation, readiness.

READ-ONLY and derived exclusively from the verified local billing domain (``billing_provider_links``, ``billing_provider_events``,
``billing_checkout_sessions``, ``billing_recovery_actions``). Nothing is read from a browser or a provider. Responses carry ids, status words, integer
counts and timestamps: never a raw webhook body, signature, secret, card detail, email, name or any candidate content. Provider object ids are shown
MASKED (last six characters) so an operator can correlate without being handed a usable identifier. The readiness block reports truth only: booleans,
source kinds and fixed states; it never says healthy, validated or approved for anything that has not been validated or approved.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import func, select

from src.billing import policy as P
from src.persistence import (
    BillingCheckoutSession as CS, BillingCommercialTerms as CT, BillingProviderEvent as EV, BillingProviderLink as LINK, BillingRecoveryAction as RA,
    PlanVersion, PROVIDER_EVENT_STATUSES, PROVIDER_LINK_STATES, PROVIDER_LINK_TERMINAL, CHECKOUT_STATUSES, utcnow,
)

OPEN_COMMERCIAL_DECISIONS = (
    "Premium monthly price", "Premium annual price", "Trial policy", "Failed-payment grace period", "Cancellation policy", "Refund policy",
    "Dispute access policy", "Currency policy", "Supported countries", "B2B billing", "Tax-inclusive display", "Legal seller entity",
    "Stripe Managed Payments eligibility",
)
EVENT_FILTER_STATUSES = PROVIDER_EVENT_STATUSES
DATA_ORIGIN_NOTE = ("Values come from events and subscriptions stored locally. The provider has never been activated, no real provider-state reader has run and no "
                    "scheduler is deployed, so any records shown originate from offline or development data. No revenue is reported.")


class OpsValidationError(ValueError):
    pass


def mask(value: str | None) -> str | None:
    return None if not value else "…" + value[-6:]


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _aware(dt: datetime | None, like: datetime) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=like.tzinfo)


def _page(page: int, page_size: int) -> tuple[int, int]:
    if not (1 <= page <= 100000) or not (1 <= page_size <= 100):
        raise OpsValidationError("Invalid pagination.")
    return page, page_size


def _choice(value: str | None, allowed: tuple[str, ...], name: str) -> str | None:
    if value in (None, ""):
        return None
    if value not in allowed:
        raise OpsValidationError(f"Unknown {name}.")
    return value


class BillingOperations:
    def __init__(self, session_factory, *, environment: str | None, provider_selected: str | None, reader_available: bool, readiness: Callable[[], dict] | None = None,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self._sf, self._env, self._provider, self._reader, self._readiness, self._clock = session_factory, environment, provider_selected, reader_available, readiness, clock

    # ------------------------------------------------------------------ readiness (truth only)
    def readiness(self) -> dict:
        base = self._readiness() if self._readiness else {}
        stripe = self._provider == P.PROVIDER_STRIPE_MP
        return {
            "provider_selected": self._provider or "none", "environment": self._env or "none",
            "provider_configured": stripe, "credential_status": base.get("status", "not_configured"),
            "credentials": base.get("sandbox", {}), "eligibility": "not_confirmed", "sandbox_access": "unverified",
            "checkout": "authorized" if P.EXTERNAL_CHECKOUT_AUTHORIZED else "not_authorized",
            "webhook": "authorized" if P.STRIPE_WEBHOOK_AUTHORIZED else "not_authorized",
            "provider_state_reader": "wired" if self._reader else "not_wired_null_reader",
            # F2-A: each stage is reported separately and none implies the next. Nothing here is evidence of a working connection.
            "provider_read_stages": {
                "reader_implemented": True, "reader_selected_at_runtime": bool(self._reader),
                "credentials_configured": bool((base.get("sandbox") or {}).get("api", {}).get("configured")) if isinstance((base.get("sandbox") or {}).get("api"), dict) else False,
                "sandbox_authorized": False, "eligibility_verified": False,
                "external_reads_authorized": P.PROVIDER_READS_AUTHORIZED, "checkout_authorized": P.EXTERNAL_CHECKOUT_AUTHORIZED,
                "webhook_authorized": P.STRIPE_WEBHOOK_AUTHORIZED, "scheduler_enabled": P.RECONCILE_SCHEDULER_ENABLED,
                "entitlement_policy_approved": P.PAID_ENTITLEMENT_POLICY_APPROVED, "sandbox_qualification_passed": False, "production_approved": False,
            },
            "provider_reads": "authorized" if P.PROVIDER_READS_AUTHORIZED else "not_authorized",
            "reconciliation_scheduler": "enabled" if P.RECONCILE_SCHEDULER_ENABLED else "disabled",
            "entitlement_policy": "approved" if P.PAID_ENTITLEMENT_POLICY_APPROVED else "not_approved",
            "live_billing": "enabled" if P.LIVE_BILLING_ENABLED else "disabled",
            "kill_switches": {"live_billing_enabled": P.LIVE_BILLING_ENABLED, "external_checkout_authorized": P.EXTERNAL_CHECKOUT_AUTHORIZED,
                              "stripe_webhook_authorized": P.STRIPE_WEBHOOK_AUTHORIZED, "reconcile_scheduler_enabled": P.RECONCILE_SCHEDULER_ENABLED,
                              "paid_entitlement_policy_approved": P.PAID_ENTITLEMENT_POLICY_APPROVED,
                              "provider_reads_authorized": P.PROVIDER_READS_AUTHORIZED},
            "operational": False,
        }

    # ------------------------------------------------------------------ overview
    def overview(self) -> dict:
        now = self._clock()
        with self._sf() as s:
            links = dict(s.execute(select(LINK.provider_state, func.count()).group_by(LINK.provider_state)).all())
            total = sum(links.values())
            scheduled_cancel = s.scalar(select(func.count()).select_from(LINK).where(LINK.cancel_at_period_end.is_(True), LINK.provider_state.notin_(PROVIDER_LINK_TERMINAL))) or 0
            events = dict(s.execute(select(EV.status, func.count()).group_by(EV.status)).all())
            checkouts = dict(s.execute(select(CS.status, func.count()).group_by(CS.status)).all())
            pending_checkouts = s.scalar(select(func.count()).select_from(CS).where(CS.status.in_(("pending_creation", "open")),
                                                                                   ~select(LINK.id).where(LINK.checkout_session_id == CS.id).exists())) or 0
            stale_cut = now - timedelta(seconds=P.RECONCILE_STALE_AFTER_SECONDS)
            stale = s.scalar(select(func.count()).select_from(LINK).where(LINK.provider_state.notin_(PROVIDER_LINK_TERMINAL),
                                                                          (LINK.observed_at.is_(None)) | (LINK.observed_at <= stale_cut))) or 0
            oldest_pending = s.scalar(select(func.min(EV.received_at)).where(EV.status.in_(("received", "processing", "failed"))))
            last_ok = s.scalar(select(func.max(EV.processed_at)).where(EV.status == "processed"))
            last_attempt = s.scalar(select(func.max(EV.last_attempt_at)))
            recoveries = s.scalar(select(func.count()).select_from(RA)) or 0
        op = _aware(oldest_pending, now)
        return {
            "generated_at": _iso(now), "data_origin": DATA_ORIGIN_NOTE, "revenue_reported": False,
            "subscriptions": {"total": total, "active": links.get("active", 0), "trialing": links.get("trialing", 0), "past_due": links.get("past_due", 0),
                              "unpaid": links.get("unpaid", 0), "canceled": links.get("canceled", 0), "incomplete": links.get("incomplete", 0) + links.get("paused", 0),
                              "cancellation_scheduled": scheduled_cancel},
            "checkouts": {"pending": pending_checkouts,
                          "failed": checkouts.get("failed", 0), "canceled": checkouts.get("canceled", 0), "expired": checkouts.get("expired", 0)},
            "events": {"pending": events.get("received", 0) + events.get("processing", 0), "failed": events.get("failed", 0), "quarantined": events.get("quarantined", 0),
                       "needs_review": events.get("needs_review", 0), "processed": events.get("processed", 0), "ignored": events.get("ignored", 0),
                       "awaiting_operator": events.get("quarantined", 0) + events.get("needs_review", 0),
                       "oldest_pending_seconds": int((now - op).total_seconds()) if op else None},
            "reconciliation": {"stale_links": stale, "last_successful": _iso(last_ok), "last_attempt": _iso(last_attempt), "provider_state_reader": "wired" if self._reader else "not_wired_null_reader"},
            "recovery_actions": recoveries,
            "readiness": self.readiness(),
            "open_commercial_decisions": list(OPEN_COMMERCIAL_DECISIONS),
        }

    # ------------------------------------------------------------------ subscriptions
    def subscriptions(self, *, state: str | None, page: int, page_size: int) -> dict:
        page, page_size = _page(page, page_size)
        state = _choice(state, PROVIDER_LINK_STATES, "subscription state")
        with self._sf() as s:
            q = select(LINK, CT, PlanVersion).join(CT, CT.id == LINK.commercial_terms_id).join(PlanVersion, PlanVersion.id == LINK.plan_version_id)
            cq = select(func.count()).select_from(LINK)
            if state:
                q, cq = q.where(LINK.provider_state == state), cq.where(LINK.provider_state == state)
            rows = s.execute(q.order_by(LINK.created_at.desc(), LINK.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            total = s.scalar(cq) or 0
            items = [{
                "reference": l.public_id, "candidate_id": l.user_id, "provider": l.provider, "environment": l.environment, "plan": pv.plan_code, "state": l.provider_state,
                "cancel_at_period_end": l.cancel_at_period_end, "invoice_state": l.latest_invoice_state, "refund_state": l.refund_state, "dispute_state": l.dispute_state,
                "terms_version": ct.version, "interval": ct.billing_interval, "created_at": _iso(l.created_at), "last_verified_at": _iso(l.observed_at),
                "current_period_end": _iso(l.current_period_end), "reconcile_count": l.reconcile_count, "entitlement_decision": l.entitlement_decision,
                "review_category": l.review_category, "provider_subscription": mask(l.provider_subscription_id)} for l, ct, pv in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ------------------------------------------------------------------ checkout diagnostics
    def checkouts(self, *, status: str | None, page: int, page_size: int) -> dict:
        page, page_size = _page(page, page_size)
        status = _choice(status, CHECKOUT_STATUSES, "checkout status")
        with self._sf() as s:
            q = select(CS, PlanVersion, CT).join(PlanVersion, PlanVersion.id == CS.plan_version_id).join(CT, CT.id == CS.commercial_terms_id)
            cq = select(func.count()).select_from(CS)
            if status:
                q, cq = q.where(CS.status == status), cq.where(CS.status == status)
            rows = s.execute(q.order_by(CS.created_at.desc(), CS.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            total = s.scalar(cq) or 0
            linked = set(s.scalars(select(LINK.checkout_session_id).where(LINK.checkout_session_id.in_([r[0].id for r in rows] or [0]))).all())
            items = [{"reference": c.public_id, "candidate_id": c.user_id, "plan": pv.plan_code, "terms_version": ct.version, "provider": c.provider, "environment": c.environment,
                      "status": c.status, "created_at": _iso(c.created_at), "expires_at": _iso(c.expires_at), "browser_returned": c.browser_returned_at is not None,
                      "failure_category": c.failure_category, "provider_attempts": c.provider_attempts, "subscription_linked": c.id in linked}
                     for c, pv, ct in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ------------------------------------------------------------------ webhook events
    def events(self, *, status: str | None, event_type: str | None, environment: str | None, page: int, page_size: int) -> dict:
        page, page_size = _page(page, page_size)
        status = _choice(status, EVENT_FILTER_STATUSES, "event status")
        environment = _choice(environment, P.STRIPE_ENVIRONMENTS, "environment")
        if event_type not in (None, "") and event_type not in __import__("src.billing.stripe_events", fromlist=["x"]).ALLOWED_EVENT_TYPES:
            raise OpsValidationError("Unknown event type.")
        with self._sf() as s:
            q, cq = select(EV), select(func.count()).select_from(EV)
            for col, val in ((EV.status, status), (EV.environment, environment), (EV.event_type, event_type or None)):
                if val:
                    q, cq = q.where(col == val), cq.where(col == val)
            rows = s.scalars(q.order_by(EV.received_at.desc(), EV.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            total = s.scalar(cq) or 0
            return {"items": [self._event_row(e) for e in rows], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _event_row(e: EV) -> dict:
        return {"reference": e.public_id, "provider_event": mask(e.provider_event_id), "provider": e.provider, "environment": e.environment, "event_type": e.event_type,
                "received_at": _iso(e.received_at), "status": e.status, "attempt_count": e.attempt_count, "attempt_limit": e.attempt_limit, "last_attempt_at": _iso(e.last_attempt_at),
                "failure_category": e.failure_category, "processed_at": _iso(e.processed_at), "subscription_reference": None}

    def event_detail(self, public_id: str) -> dict | None:
        with self._sf() as s:
            e = s.scalar(select(EV).where(EV.public_id == public_id))
            if e is None:
                return None
            link = s.get(LINK, e.link_id) if e.link_id else None
            rec = e.reconciliation_json or {}
            ent = rec.get("entitlement") if isinstance(rec.get("entitlement"), dict) else {}
            row = self._event_row(e)
            row["subscription_reference"] = link.public_id if link else None
            norm = e.normalized_json or {}
            lifecycle = [{"step": "received_and_signature_verified", "at": _iso(e.received_at)}]
            if e.last_attempt_at:
                lifecycle.append({"step": "last_processing_attempt", "at": _iso(e.last_attempt_at)})
            if e.next_attempt_at and e.status == "failed":
                lifecycle.append({"step": "retry_scheduled", "at": _iso(e.next_attempt_at)})
            if e.processed_at:
                lifecycle.append({"step": e.status, "at": _iso(e.processed_at)})
            return {**row, "api_version": e.api_version, "provider_created_at": _iso(e.provider_created_at), "operator_retries": e.operator_retries,
                    "lease_until": _iso(e.lease_until), "correlation_id": e.correlation_id, "signature_verified": True, "kind": norm.get("kind"),
                    "provider_object": mask(e.provider_object_id), "lifecycle": lifecycle,
                    "reconciliation": {"disposition": rec.get("disposition"), "source": rec.get("source"), "observed_state": rec.get("observed_state"),
                                       "previous_state": rec.get("previous_state"), "conflict": rec.get("conflict"), "linked": rec.get("linked"),
                                       "entitlement_decision": ent.get("decision"), "entitlement_reason": ent.get("reason"), "entitlement_applied": ent.get("applied")} if rec else None,
                    "classification": self._classify(e), "recoverable": e.status in ("failed", "needs_review", "quarantined")}

    @staticmethod
    def _classify(e: EV) -> str:
        if e.status == "quarantined":
            return "Quarantined: the event could not be safely associated or verified; no billing state or access was changed."
        if e.status == "needs_review":
            return "Needs operator review: retries are exhausted or the provider answer was not trustworthy; no billing state or access was changed."
        if e.status == "ignored":
            return "Ignored by design: the event type, API version or account context is not supported; acknowledged and never reconciled."
        if e.status == "failed":
            return "Processing failed and is scheduled to retry with back-off."
        if e.status in ("received", "processing"):
            return "Accepted and durably stored; reconciliation has not completed."
        return "Reconciled from the provider's authoritative state."

    # ------------------------------------------------------------------ reconciliation
    def reconciliation(self) -> dict:
        now = self._clock()
        with self._sf() as s:
            problems = s.execute(select(EV.failure_category, EV.status, func.count()).where(EV.status.in_(("quarantined", "needs_review", "failed")))
                                 .group_by(EV.failure_category, EV.status)).all()
            by_cat: dict[str, int] = {}
            for cat, st, n in problems:
                by_cat[f"{st}:{cat or 'unclassified'}"] = n
            stale_cut = now - timedelta(seconds=P.RECONCILE_STALE_AFTER_SECONDS)
            stale = s.scalar(select(func.count()).select_from(LINK).where(LINK.provider_state.notin_(PROVIDER_LINK_TERMINAL),
                                                                          (LINK.observed_at.is_(None)) | (LINK.observed_at <= stale_cut))) or 0
            last_ok = s.scalar(select(func.max(EV.processed_at)).where(EV.status == "processed"))
            last_attempt = s.scalar(select(func.max(EV.last_attempt_at)))
            retry_scheduled = s.scalar(select(func.count()).select_from(EV).where(EV.status == "failed")) or 0
            attention = s.scalars(select(EV).where(EV.status.in_(("quarantined", "needs_review", "failed"))).order_by(EV.received_at.desc()).limit(25)).all()
            conflicts = [self._event_row(e) | {"classification": self._classify(e)} for e in attention]
        return {"generated_at": _iso(now), "provider_state_reader": "wired" if self._reader else "not_wired_null_reader",
                "provider_synchronization": "not_performed_no_reader" if not self._reader else "available",
                "scheduler": "enabled" if P.RECONCILE_SCHEDULER_ENABLED else "disabled", "last_successful": _iso(last_ok), "last_attempt": _iso(last_attempt),
                "stale_links": stale, "retry_scheduled": retry_scheduled, "problems_by_category": by_cat, "needs_attention": conflicts,
                "cadence_note": "Once validated, one bounded sweep every 15 to 60 minutes; no polling is enabled."}

    # ------------------------------------------------------------------ recovery history (operator audit trail)
    def recovery_actions(self, *, page: int, page_size: int) -> dict:
        page, page_size = _page(page, page_size)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(RA)) or 0
            rows = s.scalars(select(RA).order_by(RA.created_at.desc(), RA.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            items = [{"reference": r.public_id, "action": r.action, "status": r.status, "result": r.result_category, "previous_event_status": r.previous_status,
                      "actor_id": r.actor_user_id, "reason": r.reason, "created_at": _iso(r.created_at), "completed_at": _iso(r.completed_at)} for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

