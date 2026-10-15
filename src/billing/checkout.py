"""Candidate checkout application service (W12.4D-C). Server-controlled, owner-scoped, idempotent. MONEY NEVER MOVES HERE.

The candidate only chooses a purchasable plan code. The server alone decides the price (approved, active commercial terms plus an active provider
price mapping), the currency and interval (read from those immutable terms), the provider and environment (the validated billing mode), the return
URLs (built from the trusted application origin, never the Host header) and the idempotency (a stable provider key per local record). A browser
return is recorded as a fact ("the browser came back") and can never complete a payment, create a subscription or change an entitlement: those need
authenticated provider evidence (W12.4D-D), and the states for them do not exist in this module.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.billing import lifecycle as L
from src.billing import policy as P
from src.billing.entitlement_bridge import provider_grant_exists
from src.billing.provider import CheckoutRequest, ProviderRejected, ProviderRetryable
from src.persistence import (
    BillingCheckoutSession as CS, BillingCommercialTerms as CT, BillingEntitlementDecision as ED, BillingProviderLink as LINK, BillingProviderPrice as PP, PlanVersion, PLAN_STATUS_ACTIVE, PROVIDER_LINK_TERMINAL, utcnow,
)

MAX_PROVIDER_ATTEMPTS = 5
_KEY = re.compile(P.CHECKOUT_IDEMPOTENCY_PATTERN)
# Reasons are bounded codes. INTERNAL reasons guide Admin and logs; candidates and the public only ever see ``not_enabled``.
UNAVAILABLE_REASONS = ("provider_not_selected", "live_disabled", "provider_not_ready", "checkout_not_authorized", "plan_not_purchasable",
                       "no_active_terms", "no_price_mapping", "origin_not_trusted", "environment_mismatch")


class CheckoutUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CheckoutValidationError(Exception):
    pass


class CheckoutConflict(Exception):
    pass


class CheckoutNotFound(Exception):
    pass


class CheckoutProviderError(Exception):
    """The provider could not start the checkout. ``retryable`` says whether the same Idempotency-Key may be retried."""

    def __init__(self, category: str, retryable: bool) -> None:
        super().__init__(category)
        self.category, self.retryable = category, retryable


def _iso(dt):
    return dt.isoformat() if dt else None


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


@dataclass
class _Purchasable:
    plan_version: PlanVersion
    terms: CT
    mapping: PP


class CheckoutService:
    def __init__(self, session_factory, *, provider: Any = None, mode: Any = None, app_base_url: str = "", api_env: str = "development",
                 readiness: Callable[[], str] | None = None, audit: Any = None, clock: Callable = utcnow) -> None:
        self._sf = session_factory
        self._provider = provider
        self._mode = mode
        self._origin = (app_base_url or "").rstrip("/")
        self._api_env = (api_env or "development").strip().lower()
        self._readiness = readiness
        self._audit = audit
        self._clock = clock

    # ------------------------------------------------------------------ availability (never contacts a provider)
    def _provider_reason(self) -> str | None:
        m, p = self._mode, self._provider
        if m is None or getattr(m, "provider", None) != P.PROVIDER_STRIPE_MP or p is None or getattr(p, "name", None) != P.PROVIDER_STRIPE_MP:
            return "provider_not_selected"
        if getattr(m, "environment", None) != "sandbox" or getattr(p, "live", False):
            return "live_disabled"
        if getattr(p, "environment", "sandbox") != getattr(m, "environment", None):
            return "environment_mismatch"
        if self._readiness is not None and self._readiness() != "sandbox_access_unverified":
            return "provider_not_ready"          # credentials missing, malformed, or for the wrong environment
        if not p.capabilities().get("checkout"):
            return "checkout_not_authorized"     # the provider itself does not report checkout as operational
        return None

    def _origin_ok(self) -> bool:
        u = urlparse(self._origin)
        if not u.netloc or u.path not in ("", "/") or u.scheme not in ("https", "http"):
            return False
        return u.scheme == "https" or (self._api_env in ("development", "dev", "local", "test", "testing") and u.hostname in ("localhost", "127.0.0.1"))

    def _purchasable(self, s, plan_code: str) -> _Purchasable:
        if plan_code not in P.PURCHASABLE_PLAN_CODES:
            raise CheckoutUnavailable("plan_not_purchasable")
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == plan_code, PlanVersion.status == PLAN_STATUS_ACTIVE))
        if pv is None:
            raise CheckoutUnavailable("plan_not_purchasable")
        terms = s.scalar(select(CT).where(CT.plan_version_id == pv.id, CT.state == "active"))
        if terms is None:
            raise CheckoutUnavailable("no_active_terms")            # "no terms" is unconfigured: never free, never purchasable
        mapping = s.scalar(select(PP).where(PP.commercial_terms_id == terms.id, PP.provider == P.PROVIDER_STRIPE_MP,
                                            PP.environment == getattr(self._mode, "environment", None), PP.status == "active"))
        if mapping is None or (mapping.amount_minor, mapping.currency, mapping.billing_interval) != (terms.amount_minor, terms.currency, terms.billing_interval):
            raise CheckoutUnavailable("no_price_mapping")           # an old or mismatched mapping never becomes the price
        return _Purchasable(pv, terms, mapping)

    def availability(self, plan_code: str) -> dict:
        """``{"available": bool, "reason": code|None}`` for INTERNAL use. Public callers get ``public_availability``."""
        reason = self._provider_reason()
        if reason is None and not self._origin_ok():
            reason = "origin_not_trusted"
        if reason is None:
            try:
                with self._sf() as s:
                    self._purchasable(s, plan_code)
            except CheckoutUnavailable as exc:
                reason = exc.reason
        return {"available": reason is None, "reason": reason}

    def public_availability(self, plan_code: str) -> dict:
        a = self.availability(plan_code)
        return {"plan": plan_code, "available": a["available"], "reason": None if a["available"] else "not_enabled"}

    # ------------------------------------------------------------------ create (idempotent, owner-scoped)
    def create(self, user_id: int, plan_code: str, idempotency_key: str, *, request_id: str | None = None) -> dict:
        if not isinstance(idempotency_key, str) or not _KEY.match(idempotency_key):
            raise CheckoutValidationError("An Idempotency-Key of 8 to 64 letters, digits, underscores or hyphens is required.")
        reason = self._provider_reason() or (None if self._origin_ok() else "origin_not_trusted")
        if reason:
            raise CheckoutUnavailable(reason)
        now = self._clock()
        with self._sf() as s:
            p = self._purchasable(s, plan_code)
            row = s.scalar(select(CS).where(CS.user_id == user_id, CS.idempotency_key == idempotency_key))
            if row is not None:
                if row.plan_version_id != p.plan_version.id:
                    raise CheckoutConflict("This Idempotency-Key was used for a different purchase.")
            else:
                # A candidate with a LIVE provider subscription must not start a second purchase (it would be charged twice and the duplicate quarantined).
                # A canceled or expired provider subscription is terminal for ITS OWN provider id only: it never blocks a genuinely new purchase.
                if s.scalar(select(LINK.id).where(LINK.user_id == user_id, LINK.environment == p.mapping.environment,
                                                  LINK.provider_state.notin_(PROVIDER_LINK_TERMINAL)).limit(1)) is not None:
                    raise CheckoutConflict("You already have a subscription.")
                live = s.scalar(select(CS).where(CS.user_id == user_id, CS.plan_version_id == p.plan_version.id,
                                                 CS.status.in_(("pending_creation", "open"))))
                if live is not None and live.status == "open" and s.scalar(select(LINK.id).where(LINK.checkout_session_id == live.id).limit(1)) is not None:
                    self._expire(live)                               # that checkout was already consumed by a subscription: its session can never be reused
                    s.flush()
                    live = None
                if live is not None and not (live.status == "open" and live.expires_at and _aware(live.expires_at) <= now):
                    row = live                                       # the same logical purchase is already in flight: join it, never duplicate
                else:
                    if live is not None:
                        self._expire(live)                           # an elapsed open attempt makes room for a new one
                        s.flush()
                    row = CS(public_id=uuid.uuid4().hex, user_id=user_id, plan_version_id=p.plan_version.id, commercial_terms_id=p.terms.id,
                             price_mapping_id=p.mapping.id, provider=P.PROVIDER_STRIPE_MP, environment=p.mapping.environment, status="pending_creation",
                             idempotency_key=idempotency_key, created_at=now)
                    s.add(row)
                    try:
                        s.commit()
                    except IntegrityError:                           # a concurrent identical request won: return ITS record
                        s.rollback()
                        row = s.scalar(select(CS).where(CS.user_id == user_id, CS.plan_version_id == p.plan_version.id,
                                                        CS.status.in_(("pending_creation", "open")))) or \
                            s.scalar(select(CS).where(CS.user_id == user_id, CS.idempotency_key == idempotency_key))
                        if row is None:
                            raise CheckoutConflict("Another checkout request is being processed. Please retry.") from None
            self._expire_if_due(s, row, now)
            s.commit()
            if row.status == "open" and row.checkout_url:
                return self._view(row)
            if row.status in ("canceled", "expired"):
                raise CheckoutConflict("That checkout attempt has ended. Start a new one.")
            if row.status == "failed" and not self._retryable(row):
                raise CheckoutProviderError(row.failure_category or "unknown", retryable=False)
            return self._start_at_provider(s, row, p, request_id)

    def _retryable(self, row) -> bool:
        return row.failure_category in ("provider_timeout", "provider_unavailable", "rate_limited") and row.provider_attempts < MAX_PROVIDER_ATTEMPTS

    def _start_at_provider(self, s, row, p: _Purchasable, request_id) -> dict:
        row.provider_attempts += 1
        s.commit()
        req = CheckoutRequest(
            idempotency_key=f"ask4mo-checkout-{row.public_id}",       # stable per local record: a retry after a timeout cannot create a second session
            provider_price_id=p.mapping.provider_price_id,
            success_url=f"{self._origin}/billing/return?session={row.public_id}&outcome=success",
            cancel_url=f"{self._origin}/billing/return?session={row.public_id}&outcome=cancel",
            client_reference_id=row.public_id,
            expires_at=int((self._clock() + timedelta(seconds=P.CHECKOUT_SESSION_TTL_SECONDS + P.CHECKOUT_PROVIDER_EXPIRY_MARGIN_SECONDS)).timestamp()))
        try:
            result = self._provider.create_checkout_session(req)
        except ProviderRetryable as exc:
            return self._fail(s, row, str(exc) or "provider_unavailable", True, request_id)
        except ProviderRejected as exc:
            return self._fail(s, row, str(exc) or "unknown", False, request_id)
        except Exception:  # noqa: BLE001 - never surface provider internals
            return self._fail(s, row, "unknown", False, request_id)
        L.require_checkout_transition("pending_creation" if row.status != "failed" else "failed", "open")
        row.status, row.provider_session_id, row.checkout_url, row.failure_category = "open", result.provider_session_id, result.url, None
        row.expires_at = self._clock() + timedelta(seconds=P.CHECKOUT_SESSION_TTL_SECONDS)
        row.last_synced_at = self._clock()
        s.commit()
        self._record("billing.checkout_created", row, request_id)
        return self._view(row)

    def _fail(self, s, row, category: str, retryable: bool, request_id):
        category = category if category in ("provider_timeout", "provider_unavailable", "rate_limited", "provider_auth_failed", "invalid_request",
                                            "live_disabled", "checkout_not_authorized", "managed_payments_not_enabled", "not_configured",
                                            "credential_environment_mismatch", "credential_format", "capability_unavailable") else "unknown"
        row.status, row.failure_category, row.checkout_url = "failed", category, None
        s.commit()
        self._record("billing.checkout_failed", row, request_id, category=category)
        raise CheckoutProviderError(category, retryable=retryable and self._retryable(row))

    # ------------------------------------------------------------------ browser return (a FACT, never proof of payment)
    def record_return(self, user_id: int, public_id: str, outcome: str, *, request_id: str | None = None) -> dict:
        if outcome not in ("success", "cancel"):
            raise CheckoutValidationError("Unknown return outcome.")
        with self._sf() as s:
            row = s.scalar(select(CS).where(CS.public_id == public_id, CS.user_id == user_id))      # another user's id is indistinguishable from unknown
            if row is None:
                raise CheckoutNotFound(public_id)
            self._expire_if_due(s, row, self._clock())
            if outcome == "cancel":
                if row.status == "open":
                    L.require_checkout_transition("open", "canceled")
                    row.status, row.checkout_url = "canceled", None
                    self._record("billing.checkout_canceled", row, request_id)
            elif row.browser_returned_at is None:
                row.browser_returned_at = self._clock()               # recorded once; refresh and replay change nothing and create no payment
            s.commit()
            return self._view(row)

    # ------------------------------------------------------------------ status
    def status(self, user_id: int, plan_code: str) -> dict:
        with self._sf() as s:
            row = s.scalar(select(CS).where(CS.user_id == user_id).order_by(CS.created_at.desc(), CS.id.desc()).limit(1))
            if row is not None:
                self._expire_if_due(s, row, self._clock())
                s.commit()
            link = s.scalar(select(LINK).where(LINK.user_id == user_id).order_by(LINK.created_at.desc(), LINK.id.desc()).limit(1))
            granted = provider_grant_exists(s, user_id)
            view = L.candidate_view(checkout_status=row.status if row else None, browser_returned=bool(row and row.browser_returned_at), plan_code=plan_code)
            if link is not None:                      # AUTHENTICATED provider evidence, reconciled server-side: the only source of subscription and payment words
                sub, pay = L.from_verified_link(provider_state=link.provider_state, cancel_at_period_end=link.cancel_at_period_end,
                                                latest_invoice_state=link.latest_invoice_state, refund_state=link.refund_state, dispute_state=link.dispute_state)
                view.update(subscription=sub, payment=pay, confirmation="not_applicable" if sub not in ("confirmation_pending",) else "pending")
            view["entitlement"] = {**view["entitlement"], "changed_by_billing": granted}
            return view | {
                "checkout_id": row.public_id if row else None,
                "created_at": _iso(row.created_at) if row else None,
                "expires_at": _iso(row.expires_at) if row and row.status == "open" else None,
            }

    # ------------------------------------------------------------------ candidate billing summary (W12.4D-E)
    def summary(self, user_id: int, plan_code: str) -> dict:
        """The candidate's OWN billing overview, from verified local state only. Management and receipts are Link's (the seller of record): no URL is
        invented, and no invoice, price or payment is shown unless it is verified locally."""
        base = self.status(user_id, plan_code)
        with self._sf() as s:
            row = s.scalar(select(CS).where(CS.user_id == user_id).order_by(CS.created_at.desc(), CS.id.desc()).limit(1))
            link = s.scalar(select(LINK).where(LINK.user_id == user_id).order_by(LINK.created_at.desc(), LINK.id.desc()).limit(1))
            terms = s.get(CT, link.commercial_terms_id) if link else None
            view = None if link is None else {"provider_state": link.provider_state, "latest_invoice_state": link.latest_invoice_state, "cancel_at_period_end": link.cancel_at_period_end,
                                              "refund_state": link.refund_state, "dispute_state": link.dispute_state}
            state = L.overview_state(checkout_status=row.status if row else None, browser_returned=bool(row and row.browser_returned_at), link=view)
            timeline: list[dict] = []
            for c in s.scalars(select(CS).where(CS.user_id == user_id).order_by(CS.created_at.desc()).limit(5)).all():
                timeline.append({"kind": "checkout_started", "at": _iso(c.created_at)})
            if link is not None:
                timeline.append({"kind": "subscription_linked", "at": _iso(link.created_at)})
                for d in s.scalars(select(ED).where(ED.link_id == link.id, ED.applied.is_(True)).order_by(ED.created_at.desc()).limit(10)).all():
                    timeline.append({"kind": {"grant": "access_granted", "revoke": "access_ended"}.get(d.decision, "access_reviewed"), "at": _iso(d.created_at)})
            timeline.sort(key=lambda e: e["at"] or "", reverse=True)
            end = link.current_period_end if link else None
            return {
                "state": state, "subscription": base["subscription"], "payment": base["payment"], "entitlement": base["entitlement"], "plan_code": plan_code,
                "interval": terms.billing_interval if terms else None, "current_period_end": _iso(end),
                "cancel_at_period_end": bool(link and link.cancel_at_period_end and link.provider_state not in PROVIDER_LINK_TERMINAL),
                "cancellation_effective_at": _iso(end) if link and link.cancel_at_period_end and link.provider_state not in PROVIDER_LINK_TERMINAL else None,
                "refund_state": link.refund_state if link else "none", "dispute_state": link.dispute_state if link else "none",
                "verified_at": _iso(link.observed_at) if link else None,
                "management": {"where": "link", "url": None, "url_verified": False},
                "receipts": {"shown_here": False, "where": "link_email"},
                "timeline": timeline[:15],
            }

    # ------------------------------------------------------------------ helpers
    def _expire(self, row) -> None:
        L.require_checkout_transition("open", "expired")
        row.status, row.checkout_url = "expired", None

    def _expire_if_due(self, s, row, now) -> None:
        if row.status == "open" and row.expires_at and _aware(row.expires_at) <= now:
            self._expire(row)

    def _view(self, row) -> dict:
        return {"checkout_id": row.public_id, "status": row.status, "redirect_url": row.checkout_url if row.status == "open" else None,
                "expires_at": _iso(row.expires_at) if row.status == "open" else None, "browser_returned": row.browser_returned_at is not None}

    def _record(self, event: str, row, request_id, **ctx) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=event, result="failure" if event.endswith("failed") else "success", actor_user_id=row.user_id, target_type="checkout",
                               target_id=row.public_id, request_id=request_id, context={"environment": row.environment, **ctx})
        except Exception:  # noqa: BLE001 - an audit write problem must not change the checkout outcome
            pass
