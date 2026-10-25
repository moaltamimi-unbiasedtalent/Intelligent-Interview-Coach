"""Provider control for the capstone demonstration: ONE httpx chokepoint for every adapter in the process (LangChain/OpenAI SDK, the interview HTTPX client, the RAGAS
evaluator and its embeddings).

Modes (``ASK4MO_PROVIDER_MODE``):
* ``offline``: every request to a host other than the in-process test transport or loopback is refused, whatever credentials exist (.env, Streamlit secrets, environment).
* ``live``: explicit opt-in only. Requires the owner authorization record, the pricing snapshot, a valid ledger and no kill switch; refuses in CI; admits ONLY
  ``openrouter.ai`` chat completions and embeddings (priced) plus read-only model-metadata GETs (unpriced); refuses streaming, unknown models, missing or oversized
  output caps, oversized inputs, excess retries and every other host or endpoint; reserves the worst case atomically before dispatch and settles afterwards.
* unset: no guard (legacy behaviour; the demonstration launcher always sets a mode).
Any other value, or an installation problem, raises: the process does not start (fail closed).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from decimal import Decimal

import httpx

from src.demo_live.budget import (DemoBudget, DemoBudgetError, Authorization, estimate_tokens, load_authorization, load_pricing, micros)

OP_HEADER = "x-ask4mo-operation"
LOCAL_HOSTS = {"testserver", "localhost", "127.0.0.1", "::1"}
METADATA_GET = ("/api/v1/key", "/api/v1/models", "/api/v1/credits", "/api/v1/embeddings/models")
DETERMINATE_REJECTIONS = (400, 401, 402, 403, 404, 422, 429)


class ProviderControl:
    _active: "ProviderControl | None" = None
    _orig_sync = None
    _orig_async = None

    def __init__(self, mode: str, *, ledger_dir: str | None = None, authorization: Authorization | None = None, pricing: dict | None = None, budget: DemoBudget | None = None,
                 default_category: str | None = None) -> None:
        if mode not in ("offline", "live"):
            raise DemoBudgetError("mode_invalid", "ASK4MO_PROVIDER_MODE must be 'offline' or 'live'.")
        self.mode = mode
        self.default_category = default_category
        self.refusals: list[str] = []
        self.budget = None
        if mode == "live":
            if (os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")):
                raise DemoBudgetError("ci_forbidden", "Live provider mode never runs in CI.")
            self.auth = authorization or load_authorization()
            self.pricing = pricing if pricing is not None else load_pricing()
            if not self.pricing:
                raise DemoBudgetError("pricing_unavailable", "The pricing snapshot is empty.")
            if budget is None:
                if not ledger_dir:
                    raise DemoBudgetError("ledger_missing", "Live mode needs ASK4MO_DEMO_LEDGER_DIR (the separate demonstration ledger).")
                budget = DemoBudget(ledger_dir, self.auth)
            self.budget = budget
            self._sem = threading.BoundedSemaphore(self.auth.limits.max_concurrency)

    # ------------------------------------------------------------------ install
    def install(self) -> "ProviderControl":
        if self.mode != "offline":
            from src.llm.budget.governor import refuse_ungoverned_transport

            refuse_ungoverned_transport()
        if ProviderControl._active is not None:
            raise DemoBudgetError("guard_active", "A provider control is already installed in this process.")
        ProviderControl._orig_sync, ProviderControl._orig_async = httpx.Client.send, httpx.AsyncClient.send
        ctl = self

        def sync_send(client, request, **kw):  # noqa: ANN001
            return ctl._send_sync(ProviderControl._orig_sync, client, request, kw)

        async def async_send(client, request, **kw):  # noqa: ANN001
            return await ctl._send_async(ProviderControl._orig_async, client, request, kw)

        httpx.Client.send, httpx.AsyncClient.send = sync_send, async_send
        ProviderControl._active = self
        return self

    def uninstall(self) -> None:
        if ProviderControl._active is self:
            httpx.Client.send, httpx.AsyncClient.send = ProviderControl._orig_sync, ProviderControl._orig_async
            ProviderControl._active = None

    # ------------------------------------------------------------------ checks
    def _refuse(self, reason: str, message: str):
        self.refusals.append(reason)
        raise DemoBudgetError(reason, message)

    def _host(self, request: httpx.Request) -> str:
        return (request.url.host or "").lower()

    def _classify(self, request: httpx.Request) -> str:
        host = self._host(request)
        if host in LOCAL_HOSTS:
            return "local"
        if self.mode == "offline":
            self._refuse("offline_mode", f"OFFLINE MODE: provider and network requests are disabled (attempted host: {host}). No credential can change this.")
        if host not in self.auth.hosts:
            self._refuse("host_not_allowed", f"Requests to '{host}' are not allowed in the capstone demonstration.")
        path = request.url.path.rstrip("/")
        if request.method == "POST" and any(path.endswith(e) for e in self.auth.endpoints):
            return "embeddings" if path.endswith("/embeddings") else "chat"
        if request.method == "GET" and path in METADATA_GET:
            return "metadata"
        self._refuse("endpoint_not_allowed", f"{request.method} {path} is not an allowed demonstration endpoint.")
        return ""

    def _category(self, request: httpx.Request) -> tuple[str, str]:
        op = (request.headers.get(OP_HEADER) or self.default_category or os.environ.get("ASK4MO_DEMO_CATEGORY") or "").strip().lower()
        return op, op

    def _prepare(self, request: httpx.Request, kind: str, kw: dict) -> tuple[str, str, int, str]:
        lim = self.auth.limits
        if kw.get("stream"):
            self._refuse("streaming_not_supported", "Streaming responses are not admitted (usage could not be settled).")
        try:
            body = json.loads(request.content or b"{}")
        except ValueError:
            self._refuse("body_unreadable", "The request body could not be inspected.")
        model = body.get("model")
        if not isinstance(model, str) or model not in self.pricing:
            self._refuse("model_not_priced", f"Model '{model}' has no price in the demonstration pricing snapshot (fail closed).")
        if body.get("stream"):
            self._refuse("streaming_not_supported", "Streaming responses are not admitted.")
        try:
            retry = int(request.headers.get("x-stainless-retry-count", "0"))
        except ValueError:
            retry = 0
        if retry > lim.max_retries:
            self._refuse("retry_limit", "The SDK retry count exceeds the approved maximum retries.")
        p_in, p_out = self.pricing[model]
        if kind == "embeddings":
            text = json.dumps(body.get("input"), ensure_ascii=False, default=str)
            tokens = estimate_tokens(text)
            out_cap = 0
        else:
            cap = body.get("max_completion_tokens", body.get("max_tokens"))
            if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
                self._refuse("output_cap_missing", "The outgoing request carries no output-token cap (fail closed).")
            if cap > lim.max_output_tokens:
                self._refuse("output_cap_exceeds_limit", "The outgoing output cap exceeds the approved per-request limit.")
            tokens = estimate_tokens(json.dumps({"messages": body.get("messages"), "tools": body.get("tools"), "response_format": body.get("response_format")}, ensure_ascii=False, default=str))
            out_cap = cap
        if tokens > lim.max_input_tokens:
            self._refuse("input_too_large", "The input estimate exceeds the approved per-request limit.")
        usd = Decimal(tokens) * p_in + Decimal(out_cap) * p_out
        worst = micros(usd * self.auth.usd_to_eur)
        t = float(lim.request_timeout_s)
        cur = request.extensions.get("timeout") or {}
        request.extensions["timeout"] = {k: (t if cur.get(k) is None else min(float(cur[k]), t)) for k in ("connect", "read", "write", "pool")}
        cat, op = self._category(request)
        return model, cat, worst, op

    def _cost(self, model: str, kind: str, data: dict) -> tuple[int | None, int | None, int | None, int | None, int | None]:
        """(committed, input_tokens, output_tokens, est, provider) in micro-EUR or ``None`` when usage is absent (unknown)."""
        u = data.get("usage") or {}
        tin, tout = u.get("prompt_tokens", u.get("input_tokens")), u.get("completion_tokens", u.get("output_tokens", 0))
        if tin is None:
            return None, None, None, None, None
        tin, tout = int(tin), int(tout or 0)
        p_in, p_out = self.pricing[model]
        est = micros((Decimal(tin) * p_in + Decimal(tout) * p_out) * self.auth.usd_to_eur)
        provider = micros(Decimal(str(u["cost"])) * self.auth.usd_to_eur) if u.get("cost") is not None else None
        return max(est, provider or 0), tin, tout, est, provider

    # ------------------------------------------------------------------ settlement
    def _settle(self, seq: int, model: str, kind: str, response: httpx.Response) -> None:
        sc = response.status_code
        if sc == 200:
            try:
                committed, tin, tout, est, prov = self._cost(model, kind, response.json())
            except Exception:  # noqa: BLE001 - unreadable usage is UNKNOWN, never zero
                committed = None
            if committed is None:
                self.budget.settle(seq, outcome="unknown", status_code=sc, note="no readable usage: worst case kept")
            else:
                self.budget.settle(seq, outcome="settled", committed=committed, input_tokens=tin, output_tokens=tout, est_cost=est, provider_cost=prov, status_code=sc)
        elif sc in DETERMINATE_REJECTIONS:
            self.budget.settle(seq, outcome="rejected", status_code=sc, note="provider refused; no inference ran")
        else:
            self.budget.settle(seq, outcome="unknown", status_code=sc, note="provider error: potentially billable, worst case kept")

    def _wrap(self, request: httpx.Request, kind: str, kw: dict, preacquired: bool = False):
        try:
            model, cat, worst, op = self._prepare(request, kind, kw)
        except BaseException:
            if preacquired:
                self._sem.release()
            raise
        if not preacquired and not self._sem.acquire(timeout=self.auth.limits.request_timeout_s):
            self._refuse("concurrency_limit", "The approved concurrency limit is saturated.")
        try:
            seq = self.budget.reserve(category=cat, operation=op or cat, model=model, endpoint=kind, worst_case=worst)
        except DemoBudgetError as exc:
            self._sem.release()
            self.refusals.append(exc.reason)
            raise
        if OP_HEADER in request.headers:
            del request.headers[OP_HEADER]                    # an internal label; never sent to the provider
        return model, seq

    # ------------------------------------------------------------------ the wrappers
    def _send_sync(self, orig, client, request, kw):  # noqa: ANN001
        kind = self._classify(request)
        if kind == "local":
            return orig(client, request, **kw)
        if kind == "metadata":
            if self.budget.killed():
                self._refuse("kill_switch", "The demonstration kill switch is engaged.")
            return orig(client, request, **kw)
        model, seq = self._wrap(request, kind, kw)
        try:
            try:
                response = orig(client, request, **kw)
            except BaseException:
                self.budget.settle(seq, outcome="unknown", note="no response: worst case kept")
                raise
            self._settle(seq, model, kind, response)
            return response
        finally:
            self._sem.release()

    async def _send_async(self, orig, client, request, kw):  # noqa: ANN001
        kind = self._classify(request)
        if kind == "local":
            return await orig(client, request, **kw)
        if kind == "metadata":
            if self.budget.killed():
                self._refuse("kill_switch", "The demonstration kill switch is engaged.")
            return await orig(client, request, **kw)
        # The concurrency limit is a threading semaphore shared with sync callers; waiting on it must never block the event loop (a blocked loop cannot finish the in-flight
        # requests that hold the slots, which deadlocked the first live RAGAS run), so the wait happens in a worker thread.
        got = await asyncio.get_running_loop().run_in_executor(None, lambda: self._sem.acquire(timeout=self.auth.limits.request_timeout_s))
        if not got:
            self._refuse("concurrency_limit", "The approved concurrency limit is saturated.")
        model, seq = self._wrap(request, kind, kw, preacquired=True)
        try:
            try:
                response = await orig(client, request, **kw)
                await response.aread()
            except BaseException:
                self.budget.settle(seq, outcome="unknown", note="no response: worst case kept")
                raise
            self._settle(seq, model, kind, response)
            return response
        finally:
            self._sem.release()


def operation_headers(operation: str) -> dict[str, str]:
    """The internal budget-category label for an adapter's requests; empty unless a provider-control mode is set (so production behaviour is unchanged). The guard removes it
    before dispatch, so it never reaches the provider."""
    governed = (os.environ.get("ASK4MO_PROVIDER_MODE") or "").strip() or (os.environ.get("AI_BUDGET_MODE") or "").strip().lower() == "enforce"      # 05C: the production governor reads the same label
    return {"X-Ask4Mo-Operation": operation} if governed else {}


def install_from_env(env: dict | None = None) -> ProviderControl | None:
    """Install the provider control chosen by ``ASK4MO_PROVIDER_MODE``; ``None`` when it is unset. Raises (the process must not start) on any problem."""
    e = os.environ if env is None else env
    from src.llm.budget.config import hosted

    if hosted(e):
        return None  # Hosted processes use the production ledger, never the demo ledger.
    mode = (e.get("ASK4MO_PROVIDER_MODE") or "").strip().lower()
    if not mode:
        return None
    if ProviderControl._active is not None:
        if ProviderControl._active.mode != mode:
            raise DemoBudgetError("guard_active", "A provider control with a different mode is already installed in this process.")
        return ProviderControl._active
    ctl = ProviderControl(mode, ledger_dir=e.get("ASK4MO_DEMO_LEDGER_DIR"), default_category=(e.get("ASK4MO_DEMO_CATEGORY") or None))
    return ctl.install()
