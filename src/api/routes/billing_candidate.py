"""Candidate billing routes (W12.4D-C). Authenticated, owner-scoped. NOTHING here moves money or grants an entitlement.

The request body carries ONLY a plan code. Price, currency, interval, provider, environment, return URLs and entitlement are server decisions; any
extra field is rejected. There is deliberately no "payment succeeded" endpoint: the browser return records that the browser came back, nothing more.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from src.api.dependencies import get_checkout_service, get_current_user_id, get_entitlement_service, get_request_id
from src.api.rate_limit import client_ip, enforce, user_key
from src.billing.checkout import (
    CheckoutConflict, CheckoutNotFound, CheckoutProviderError, CheckoutUnavailable, CheckoutValidationError,
)

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: Literal["premium"]


class CheckoutReturnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkout_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    outcome: Literal["success", "cancel"]


class Availability(BaseModel):
    plan: str
    available: bool
    reason: Literal["not_enabled"] | None = None


class CheckoutCreated(BaseModel):
    checkout_id: str
    status: str
    redirect_url: str | None = None
    expires_at: str | None = None
    browser_returned: bool = False


class EntitlementFacet(BaseModel):
    plan_code: str
    source: str
    changed_by_billing: bool


class CheckoutStatus(BaseModel):
    checkout: str
    subscription: str
    payment: str
    confirmation: str
    entitlement: EntitlementFacet
    checkout_id: str | None = None
    created_at: str | None = None
    expires_at: str | None = None


@router.get("/checkout/availability", response_model=Availability, summary="Is checkout enabled for a plan? (coarse, public-safe)")
def availability(plan: str, request: Request, checkout=Depends(get_checkout_service)) -> Availability:
    enforce("billing_status_ip", client_ip(request))
    return Availability(**checkout.public_availability(plan[:32]))


@router.post("/checkout-sessions", response_model=CheckoutCreated, status_code=201, summary="Start a checkout attempt (idempotent)")
def create_checkout(body: CheckoutCreateRequest, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                    user_id: int = Depends(get_current_user_id), checkout=Depends(get_checkout_service)) -> CheckoutCreated:
    enforce("billing_checkout_user", user_key(user_id))
    try:
        return CheckoutCreated(**checkout.create(user_id, body.plan, idempotency_key or "", request_id=get_request_id(request)))
    except CheckoutValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except CheckoutUnavailable:
        raise HTTPException(status_code=503, detail="Checkout is not enabled yet.")                 # reasons stay internal
    except CheckoutConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CheckoutProviderError as exc:
        raise HTTPException(status_code=502 if exc.retryable else 503,
                            detail="The payment provider could not start checkout. Nothing was charged." if exc.retryable else "Checkout is not available right now.")


@router.post("/checkout-returns", response_model=CheckoutCreated, summary="Record that the browser returned (never proof of payment)")
def record_return(body: CheckoutReturnRequest, request: Request, user_id: int = Depends(get_current_user_id),
                  checkout=Depends(get_checkout_service)) -> CheckoutCreated:
    enforce("billing_status_ip", client_ip(request))
    try:
        return CheckoutCreated(**checkout.record_return(user_id, body.checkout_id, body.outcome, request_id=get_request_id(request)))
    except CheckoutNotFound:
        raise HTTPException(status_code=404, detail="Checkout not found.")


@router.get("/checkout/status", response_model=CheckoutStatus, summary="My checkout / subscription / entitlement state")
def my_status(user_id: int = Depends(get_current_user_id), checkout=Depends(get_checkout_service),
              ents=Depends(get_entitlement_service)) -> CheckoutStatus:
    plan = ents.plan_summary(user_id)["plan_code"]
    return CheckoutStatus(**checkout.status(user_id, plan))
