"""Stripe webhook route (W12.4D-D). The ONLY unauthenticated billing route, and it is authenticated by the provider's SIGNATURE, not by a cookie.

POST only; no candidate login, no CSRF token (there is no session to forge), no CORS-dependent behaviour (a server-to-server call). The body is read as
raw bytes under an explicit size limit before anything else, and is handed UNMODIFIED to signature verification. The response never contains a payload,
a signature, a secret or an internal reason; the reason lives in the audit trail. The route changes no entitlement: it only authenticates and stores.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.api.dependencies import get_request_id, get_webhook_receiver
from src.api.rate_limit import client_ip, enforce
from src.billing import policy as P
from src.billing.stripe_events import WebhookError

router = APIRouter(prefix="/billing", tags=["billing-webhooks"])

_MESSAGES = {400: "Webhook rejected.", 413: "Payload too large.", 503: "Webhook is not available."}


class WebhookAck(BaseModel):
    status: str


async def _read_limited(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > P.WEBHOOK_MAX_BODY_BYTES:
        raise WebhookError("payload_too_large", 413)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > P.WEBHOOK_MAX_BODY_BYTES:
            raise WebhookError("payload_too_large", 413)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/webhooks/stripe", response_model=WebhookAck, summary="Stripe webhook (signature-authenticated; non-operational until authorized)")
async def stripe_webhook(request: Request, receiver=Depends(get_webhook_receiver)) -> WebhookAck:
    enforce("billing_webhook_ip", client_ip(request))
    try:
        raw = await _read_limited(request)
        out = await run_in_threadpool(receiver.handle, raw, request.headers.get("stripe-signature"), correlation_id=get_request_id(request) or None)
    except WebhookError as exc:
        raise HTTPException(status_code=exc.status, detail=_MESSAGES.get(exc.status, "Webhook rejected."))
    return WebhookAck(**out)
