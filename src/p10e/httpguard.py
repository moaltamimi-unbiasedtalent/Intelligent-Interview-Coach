"""P10E HTTP guard: the single chokepoint through which EVERY provider request passes during a live session.

All chat traffic in Ask4Mo (the OpenAI SDK behind LangChain, including nested agent calls, helper agents and the SDK's own retries) goes through ``httpx``. While a session is active
this module wraps ``httpx.Client.send`` and ``httpx.AsyncClient.send`` so that no request can be sent unless it has been checked and DURABLY reserved first:

1. the host is in the owner-recorded allowlist (any other host is refused, so no other provider can be used);
2. only the chat-completions endpoint is priced and admitted; a short list of read-only metadata endpoints is allowed (never billed); everything else is refused;
3. the model is one with a published price, streaming is refused, and the outgoing body must carry an output cap at or below the approved limit (the limit must reach the real
   request: ``max_completion_tokens`` or ``max_tokens``);
4. the SDK's retry counter must not exceed the approved retries; every retry is its own request, reserved and counted separately;
5. the input estimate (messages and tool definitions, pessimistic) must fit the per-request limit;
6. the cumulative ledger (dollars and the global call count) accepts the worst-case reservation, committed before the network send;
7. concurrency is bounded and the timeout is clamped to the approved value.

After the response (or a failure) the reservation is settled: a determinate provider rejection releases the dollars but keeps the call counted; a response with usage is priced from
the reported tokens (or the larger provider-reported cost); a timeout, connection loss, server error or missing usage keeps the FULL worst case. Nothing is ever reset.
"""

from __future__ import annotations

import json
import threading
import time
from decimal import Decimal
from typing import Any

import httpx

from src.p10e import guard as G
from src.p10e.errors import BudgetExceeded, LiveRunRefused

METADATA_GET = ("/api/v1/key", "/api/v1/models", "/api/v1/credits")
DEFINITIVE_REJECTIONS = (400, 401, 402, 403, 404, 422, 429)      # the provider answered and ran no inference


class HttpGuard:
    _active: "HttpGuard | None" = None
    _orig_sync = None
    _orig_async = None

    def __init__(self, budget: G.LiveBudget, limits: G.LiveLimits, *, allowed_hosts: tuple[str, ...], recorder: Any = None) -> None:
        self.budget, self.limits, self.allowed_hosts, self.recorder = budget, limits, tuple(allowed_hosts), recorder
        self._sem = threading.BoundedSemaphore(limits.max_concurrency)
        self.metadata_requests = 0
        self.anomalies: list[str] = []
        self.refused: list[str] = []

    # ------------------------------------------------------------------ install
    def install(self) -> None:
        if HttpGuard._active is not None:
            raise LiveRunRefused("http_guard_active", "An HTTP guard is already installed in this process.")
        HttpGuard._orig_sync, HttpGuard._orig_async = httpx.Client.send, httpx.AsyncClient.send
        guard = self

        def sync_send(client, request, **kw):  # noqa: ANN001
            return guard._send_sync(HttpGuard._orig_sync, client, request, kw)

        async def async_send(client, request, **kw):  # noqa: ANN001
            return await guard._send_async(HttpGuard._orig_async, client, request, kw)

        httpx.Client.send, httpx.AsyncClient.send = sync_send, async_send
        HttpGuard._active = self

    def uninstall(self) -> None:
        if HttpGuard._active is self:
            httpx.Client.send, httpx.AsyncClient.send = HttpGuard._orig_sync, HttpGuard._orig_async
            HttpGuard._active = None

    # ------------------------------------------------------------------ checks
    def _refuse(self, reason: str, message: str, *, budget: bool = False):
        self.refused.append(reason)
        raise (BudgetExceeded if budget else LiveRunRefused)(reason, message)

    def _classify(self, request: httpx.Request) -> str:
        host = (request.url.host or "").lower()
        if host not in self.allowed_hosts:
            self._refuse("host_not_allowed", f"Requests to '{host}' are not allowed during a P10E live session.")
        path = request.url.path.rstrip("/")
        if request.method == "POST" and path.endswith("/chat/completions"):
            return "chat"
        if request.method == "GET" and path in METADATA_GET:
            return "metadata"
        self._refuse("endpoint_not_allowed", f"{request.method} {path} is not an allowed P10E endpoint (only priced chat completions and read-only metadata).")
        return ""

    def _prepare(self, request: httpx.Request, kw: dict) -> tuple[str, int, int]:
        if kw.get("stream"):
            self._refuse("streaming_not_supported", "Streaming responses are not admitted (usage could not be settled).")
        try:
            body = json.loads(request.content or b"{}")
        except ValueError:
            self._refuse("body_unreadable", "The request body could not be inspected.")
        model = body.get("model")
        if not isinstance(model, str) or model not in self.budget.prices:
            self._refuse("model_not_recognized", f"Model '{model}' has no published price in the P10E snapshot.")
        if body.get("stream"):
            self._refuse("streaming_not_supported", "Streaming responses are not admitted (usage could not be settled).")
        cap = body.get("max_completion_tokens", body.get("max_tokens"))
        if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
            self._refuse("output_cap_missing", "The outgoing request carries no output-token cap.")
        if cap > self.limits.max_output_tokens_per_request:
            self._refuse("output_cap_exceeds_limit", "The outgoing output cap exceeds the approved per-request limit.", budget=True)
        try:
            retry = int(request.headers.get("x-stainless-retry-count", "0"))
        except ValueError:
            retry = 0
        if retry > self.limits.max_retries:
            self._refuse("retry_limit", "The SDK retry count exceeds the approved maximum retries.", budget=True)
        est = G.estimate_input_tokens(json.dumps({"messages": body.get("messages"), "tools": body.get("tools"), "response_format": body.get("response_format")}, ensure_ascii=False, default=str))
        self._clamp_timeout(request)
        return model, est, cap

    def _clamp_timeout(self, request: httpx.Request) -> None:
        t = float(self.limits.request_timeout_s)
        cur = request.extensions.get("timeout") or {}
        request.extensions["timeout"] = {k: (t if cur.get(k) is None else min(float(cur[k]), t)) for k in ("connect", "read", "write", "pool")}

    def _admit(self, model: str, est: int, cap: int) -> G.Reservation:
        try:
            return self.budget.admit(model, est, cap)
        except BudgetExceeded as exc:
            self.refused.append(exc.reason)               # runners detect a stop from this record (the SDK may wrap the exception)
            raise

    # ------------------------------------------------------------------ settlement
    def _settle_response(self, res: G.Reservation, response: httpx.Response, started: float, expected_model: str) -> None:
        ms = int((time.perf_counter() - started) * 1000)
        status = response.status_code
        tin = tout = None
        cost: Decimal | None = None
        answered_by = None
        if status == 200:
            try:
                data = response.json()
                u = data.get("usage") or {}
                tin, tout = u.get("prompt_tokens"), u.get("completion_tokens")
                tin = int(tin) if tin is not None else None
                tout = int(tout) if tout is not None else None
                if u.get("cost") is not None:
                    cost = Decimal(str(u["cost"]))
                answered_by = data.get("model")
            except Exception:  # noqa: BLE001 - unreadable usage is UNKNOWN, never zero
                tin = tout = None
            if answered_by and not str(answered_by).startswith(expected_model.split(":")[0]):
                self.anomalies.append(f"model fallback: requested {expected_model}, answered by {answered_by}")
            self.budget.settle(res, outcome="ok", input_tokens=tin, output_tokens=tout, provider_cost=cost, status_code=status, latency_ms=ms)
        elif status in DEFINITIVE_REJECTIONS:
            self.budget.settle(res, outcome="rejected", status_code=status, latency_ms=ms, note="provider rejected the request; no inference ran")
        else:
            self.budget.settle(res, outcome="unknown", status_code=status, latency_ms=ms, note="provider error: potentially billable, kept at full worst case")
        if self.recorder:
            self.recorder.call(model=expected_model, status=status, input_tokens=tin, output_tokens=tout, provider_cost_usd=None if cost is None else str(cost), latency_ms=ms,
                               seq=res.seq, answered_by=answered_by)

    def _settle_exception(self, res: G.Reservation, exc: BaseException, started: float, model: str) -> None:
        ms = int((time.perf_counter() - started) * 1000)
        self.budget.settle(res, outcome="unknown", latency_ms=ms, note=f"no response ({type(exc).__name__}): potentially billable, kept at full worst case")
        if self.recorder:
            self.recorder.call(model=model, status=None, error=type(exc).__name__, latency_ms=ms, seq=res.seq)

    # ------------------------------------------------------------------ the wrappers
    def _send_sync(self, orig, client, request, kw):  # noqa: ANN001
        kind = self._classify(request)
        if kind == "metadata":
            self.metadata_requests += 1
            return orig(client, request, **kw)
        model, est, cap = self._prepare(request, kw)
        if not self._sem.acquire(timeout=self.limits.request_timeout_s):
            self._refuse("concurrency_limit", "The approved concurrency limit is saturated.")
        try:
            res = self._admit(model, est, cap)                          # durable reservation BEFORE the network send
            started = time.perf_counter()
            try:
                response = orig(client, request, **kw)
            except BaseException as exc:
                self._settle_exception(res, exc, started, model)
                raise
            self._settle_response(res, response, started, model)
            return response
        finally:
            self._sem.release()

    async def _send_async(self, orig, client, request, kw):  # noqa: ANN001
        kind = self._classify(request)
        if kind == "metadata":
            self.metadata_requests += 1
            return await orig(client, request, **kw)
        model, est, cap = self._prepare(request, kw)
        if not self._sem.acquire(timeout=self.limits.request_timeout_s):
            self._refuse("concurrency_limit", "The approved concurrency limit is saturated.")
        try:
            res = self._admit(model, est, cap)
            started = time.perf_counter()
            try:
                response = await orig(client, request, **kw)
                await response.aread()
            except BaseException as exc:
                self._settle_exception(res, exc, started, model)
                raise
            self._settle_response(res, response, started, model)
            return response
        finally:
            self._sem.release()
