"""Brevo delivery-event webhook route (05D). Unauthenticated by cookie, authenticated by the shared-secret signature / bearer over the RAW body.

POST only, server-to-server (no session, no CSRF token). The body is read as raw bytes under an explicit size limit before anything else and handed
UNMODIFIED to verification. Non-operational while ``src.mail.webhook.DELIVERY_EVENTS_AUTHORIZED`` is False (503, nothing stored). The response never
contains a payload, a signature, a secret or an internal reason (the reason is in the audit trail).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.api.dependencies import get_mail_webhook_receiver, get_request_id
from src.api.rate_limit import client_ip, enforce
from src.mail import webhook as W

router = APIRouter(prefix="/mail", tags=["mail-webhooks"])

_MESSAGES = {400: "Webhook rejected.", 401: "Webhook rejected.", 413: "Payload too large.", 503: "Webhook is not available."}


class WebhookAck(BaseModel):
    status: str


async def _read_limited(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > W.MAX_BODY_BYTES:
        raise W.WebhookError("payload_too_large", 413)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > W.MAX_BODY_BYTES:
            raise W.WebhookError("payload_too_large", 413)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/webhooks/brevo", response_model=WebhookAck, summary="Brevo delivery events (authenticated; non-operational until authorized)")
async def brevo_webhook(request: Request, receiver=Depends(get_mail_webhook_receiver)) -> WebhookAck:
    enforce("mail_webhook_ip", client_ip(request))
    headers = {W.SIGNATURE_HEADER: request.headers.get(W.SIGNATURE_HEADER), "authorization": request.headers.get("authorization")}
    try:
        raw = await _read_limited(request)
        out = await run_in_threadpool(receiver.handle, raw, headers, correlation_id=get_request_id(request) or None)
    except W.WebhookError as exc:
        raise HTTPException(status_code=exc.status, detail=_MESSAGES.get(exc.status, "Webhook rejected."))
    return WebhookAck(**out)
