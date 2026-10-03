"""Admin MOCK billing (P10B-W10.5). MOCK BILLING: NOT LIVE BILLING. Every route declares an explicit permission.

There is no checkout, no payment-method collection, no card data, no tax engine, no public webhook and no route that creates money:
invoices, payments and events enter through the (mock) provider boundary, never through an Admin write. Price changes and refunds are
REQUESTED by one administrator and decided by a DIFFERENT one holding the specific permission; the approve routes are separate per action
so that ``platform.billing.read`` can approve nothing. Billing state never changes product access (entitlements stay with W10.4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_billing_service, get_request_id, require_permission
from src.api.schemas.admin import (
    BillingApprovalPage, BillingApprovalView, BillingCustomerPage, BillingInvoiceDetail, BillingInvoicePage, BillingOverview,
    BillingPaymentDetail, BillingPaymentPage, BillingPriceChangeRequest, BillingRefundPage, BillingRefundRequest, BillingTermsList,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.billing.service import BillingConflict, BillingForbidden, BillingNotFound, BillingValidationError

router = APIRouter(prefix="/admin/billing", tags=["admin-billing"])


def _guard(fn):
    try:
        return fn()
    except BillingNotFound:
        raise HTTPException(status_code=404, detail="Not found.")
    except BillingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except BillingForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except BillingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _audit(request: Request, principal, event: str, target_type: str, target: str | None = None) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type=target_type, target_id=target)


@router.get("", response_model=BillingOverview, summary="MOCK billing overview: provider mode, counts, commercial terms")
def overview(_p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingOverview:
    return BillingOverview(mode=svc.mode(), stats=svc.stats(), terms=svc.list_terms())


@router.get("/terms", response_model=BillingTermsList, summary="Commercial terms per plan version (versioned, immutable; none means unconfigured)")
def terms(_p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingTermsList:
    return BillingTermsList(**svc.list_terms())


@router.get("/approvals", response_model=BillingApprovalPage, summary="Price-change and refund approval requests")
def approvals(action: str | None = None, status: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
              _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingApprovalPage:
    return BillingApprovalPage(**_guard(lambda: svc.list_approvals(action=action, status=status, page=page, page_size=page_size)))


@router.post("/price-changes", response_model=BillingApprovalView, status_code=201,
             summary="Request new MOCK commercial terms (needs a second approver; changes no entitlement)")
def request_price_change(body: BillingPriceChangeRequest, request: Request, principal=Depends(require_permission(perm.PRICE_CHANGE)),
                         svc=Depends(get_billing_service)) -> BillingApprovalView:
    return BillingApprovalView(**_guard(lambda: svc.request_price_change(
        body.plan_version_id, amount_minor=body.amount_minor, currency=body.currency, interval=body.interval, trial_days=body.trial_days,
        visibility=body.visibility, reason=body.reason, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_BILLING_PRICE_CHANGE_REQUESTED, "billing_approval"))))


@router.post("/price-changes/{approval_id}/approve", response_model=BillingApprovalView,
             summary="A DIFFERENT administrator approves: a new immutable terms version becomes active")
def approve_price_change(approval_id: str, request: Request, principal=Depends(require_permission(perm.PRICE_CHANGE)),
                         svc=Depends(get_billing_service)) -> BillingApprovalView:
    return BillingApprovalView(**_guard(lambda: svc.decide_price_change(
        approval_id[:40], approve=True, actor_user_id=principal.user_id,
        audit_decision=_audit(request, principal, A.ADMIN_BILLING_PRICE_CHANGE_APPROVED, "billing_approval"),
        audit_activation=_audit(request, principal, A.ADMIN_BILLING_PRICE_ACTIVATED, "billing_terms"))))


@router.post("/price-changes/{approval_id}/reject", response_model=BillingApprovalView, summary="A different administrator rejects the request")
def reject_price_change(approval_id: str, request: Request, principal=Depends(require_permission(perm.PRICE_CHANGE)),
                        svc=Depends(get_billing_service)) -> BillingApprovalView:
    return BillingApprovalView(**_guard(lambda: svc.decide_price_change(
        approval_id[:40], approve=False, actor_user_id=principal.user_id,
        audit_decision=_audit(request, principal, A.ADMIN_BILLING_PRICE_CHANGE_REJECTED, "billing_approval"))))


@router.get("/invoices", response_model=BillingInvoicePage, summary="MOCK invoices (metadata only)")
def invoices(state: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
             _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingInvoicePage:
    return BillingInvoicePage(**_guard(lambda: svc.list_invoices(state=state, page=page, page_size=page_size)))


@router.get("/invoices/{public_id}", response_model=BillingInvoiceDetail, summary="One MOCK invoice with its payments")
def invoice_detail(public_id: str, _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingInvoiceDetail:
    return BillingInvoiceDetail(**_guard(lambda: svc.invoice_detail(public_id[:40])))


@router.get("/payments", response_model=BillingPaymentPage, summary="MOCK payments (metadata only; failures show a safe category)")
def payments(status: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
             _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingPaymentPage:
    return BillingPaymentPage(**_guard(lambda: svc.list_payments(status=status, page=page, page_size=page_size)))


@router.get("/payments/{public_id}", response_model=BillingPaymentDetail, summary="One MOCK payment with its refunds")
def payment_detail(public_id: str, _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingPaymentDetail:
    return BillingPaymentDetail(**_guard(lambda: svc.payment_detail(public_id[:40])))


@router.get("/refunds", response_model=BillingRefundPage, summary="MOCK refunds (no real money moves)")
def refunds(page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
            _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingRefundPage:
    return BillingRefundPage(**svc.list_refunds(page=page, page_size=page_size))


@router.get("/customers", response_model=BillingCustomerPage, summary="MOCK provider customers and mirrored provider subscriptions (informational only)")
def customers(page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
              _p=Depends(require_permission(perm.BILLING_READ)), svc=Depends(get_billing_service)) -> BillingCustomerPage:
    return BillingCustomerPage(**svc.list_customers(page=page, page_size=page_size))


@router.post("/payments/{public_id}/refunds", response_model=BillingApprovalView, status_code=201,
             summary="Request a MOCK refund (needs a second approver; no real money moves)")
def request_refund(public_id: str, body: BillingRefundRequest, request: Request, principal=Depends(require_permission(perm.BILLING_REFUND)),
                   svc=Depends(get_billing_service)) -> BillingApprovalView:
    return BillingApprovalView(**_guard(lambda: svc.request_refund(
        public_id[:40], amount_minor=body.amount_minor, reason=body.reason, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_BILLING_REFUND_REQUESTED, "billing_approval"))))


@router.post("/refunds/{approval_id}/approve", response_model=BillingApprovalView,
             summary="A DIFFERENT administrator approves: the refund is queued as a W10.9 job (MOCK)")
def approve_refund(approval_id: str, request: Request, principal=Depends(require_permission(perm.BILLING_REFUND)),
                   svc=Depends(get_billing_service)) -> BillingApprovalView:
    return BillingApprovalView(**_guard(lambda: svc.decide_refund(
        approval_id[:40], approve=True, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_BILLING_REFUND_APPROVED, "billing_approval"))))


@router.post("/refunds/{approval_id}/reject", response_model=BillingApprovalView, summary="A different administrator rejects the refund request")
def reject_refund(approval_id: str, request: Request, principal=Depends(require_permission(perm.BILLING_REFUND)),
                  svc=Depends(get_billing_service)) -> BillingApprovalView:
    return BillingApprovalView(**_guard(lambda: svc.decide_refund(
        approval_id[:40], approve=False, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_BILLING_REFUND_REJECTED, "billing_approval"))))
