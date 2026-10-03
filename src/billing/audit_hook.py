"""Audit spec builder for provider-executed refunds (kept apart so the service stays importable without the admin audit module cycle)."""

from __future__ import annotations

from src.application import admin_audit as A


def build_execution_audit(ok: bool, refund_public_id: str, approval_pid, payment_pid, amount_minor: int, currency: str) -> dict:
    return A.build_audit(event_type=A.ADMIN_BILLING_REFUND_EXECUTED if ok else A.ADMIN_BILLING_REFUND_FAILED, actor_user_id=None, request_id=None,
                         target_type="billing_refund", target_id=refund_public_id, result="success" if ok else "failure",
                         approval_public_id=approval_pid, payment_public_id=payment_pid, refund_public_id=refund_public_id,
                         amount_minor=amount_minor, currency=currency)
