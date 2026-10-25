"""The production AI budget governor (05C): per-request limits, worst-case reservation, settlement and the ONE httpx chokepoint.

Every provider request of the process (the Interview HTTPX client, the Career/agent LangChain adapters, embeddings, RAGAS) goes through ``httpx.Client.send`` / ``AsyncClient.send``.
This module wraps those two methods ONCE; no call site carries a budget check of its own. A request to a configured provider host is admitted only if:

* the governor is OPEN: the configuration, price table, approved-budget marker and ledger are all valid and the kill switch is off (anything else fails CLOSED with a stable reason);
* the endpoint is an allowed priced endpoint (chat completions, embeddings) or a free read-only metadata GET (key, models, credits, embedding models; these only honour the kill switch);
* streaming is absent, the model is priced, the output-token cap is present and within the limit, the input estimate is within the limit and the SDK retry count is within the bound;
* the worst case (input estimate x prompt price + output cap x completion price) fits under the class stop threshold and the category stop threshold (atomic, see ``ledger.py``);
* it is not an identical request already in flight, an identical request with an unknown outcome, or a retry beyond the bound.

After the response the reservation is settled from usage using the LARGER of our estimate and the provider's reported cost. A response without readable usage, a timeout, a lost
connection or a server error is an UNKNOWN outcome held at its worst case. Only provider refusals that ran no inference (429 and other 4xx) release the money.

This is not used when the capstone demonstration guard (``src/demo_live``) is installed: that is a separate, file-ledger harness with its own EUR budget.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from decimal import Decimal
from typing import Any, Mapping

import httpx

from src.llm.budget.config import (BudgetConfig, CATEGORIES, KILL_ENV, MODE_ENV, load_config, require_approved_marker, resolve_budget_class, usd_to_micro, hosted, validate_hosted_approval)
from src.llm.budget.errors import BudgetError
from src.llm.budget.ledger import DbBudgetLedger, Reservation

HOSTED_POLICY_VERSION = 1

OP_HEADER = "x-ask4mo-operation"
METADATA_GET = ("/api/v1/key", "/api/v1/models", "/api/v1/credits", "/api/v1/embeddings/models")
PRICED_ENDPOINTS = ("/chat/completions", "/embeddings")
DETERMINATE_REJECTIONS = (400, 401, 402, 403, 404, 422, 429)
OPERATION_CATEGORY = {"agent": "agent", "interview": "interview", "embedding": "embedding", "embeddings": "embedding", "evaluation": "evaluation", "ragas": "evaluation"}


def estimate_tokens(text: str) -> int:
    """Conservative byte bound, including non-ASCII input and serialized tool schemas."""
    return max(1, len(text.encode("utf-8")))


def _error_category(status: int | None, exc: BaseException | None = None) -> str | None:
    if exc is not None:
        return "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
    if status is None or status == 200:
        return None
    if status == 429:
        return "rate_limited"
    return "server_error" if status >= 500 else "rejected"


class BudgetGovernor:
    """One governor per process: a configuration, a ledger, a budget class and (when it cannot be open) the fixed reason it is closed."""

    def __init__(self, config: BudgetConfig | None, ledger: DbBudgetLedger | None, budget_class: str, *, default_category: str | None = None,
                 closed_reason: str | None = None, environ: Mapping[str, str] | None = None) -> None:
        self.config, self.ledger, self.budget_class = config, ledger, budget_class
        self.default_category = default_category
        self.closed_reason = closed_reason
        self.env = os.environ if environ is None else environ
        self.refusals: list[str] = []
        self._sem = threading.BoundedSemaphore(config.limits.max_concurrency) if config else None

    # ------------------------------------------------------------------ construction
    @classmethod
    def build(cls, session_factory, *, budget_class: str | None = None, default_category: str | None = None, environ: Mapping[str, str] | None = None,
              config: BudgetConfig | None = None, require_marker: bool = True) -> "BudgetGovernor":
        """Build an OPEN governor or raise ``BudgetError`` (config, marker, class, ledger, CI). Never reads a provider key."""
        env = os.environ if environ is None else environ
        if env.get("CI") or env.get("GITHUB_ACTIONS"):
            raise BudgetError("ci_forbidden", "Paid provider calls never run in CI.")
        klass = budget_class or resolve_budget_class(env)
        if hosted(env) and (env.get(MODE_ENV) != "enforce" or klass == "development"):
            raise BudgetError("enforcement_required", "Hosted calls require the approved production budget policy.")
        cfg = config or load_config(environ=env)
        if klass not in cfg.classes:
            raise BudgetError("class_not_configured", f"Budget class {klass!r} has no configured ceiling (fail closed).")
        if require_marker:
            require_approved_marker(cfg, env)
        validate_hosted_approval(cfg, env)
        ledger = DbBudgetLedger(session_factory)
        ledger.ensure_ready()
        if hosted(env):
            with session_factory() as session:
                if session.get_bind().dialect.name != "postgresql":
                    raise BudgetError("durable_ledger_required", "Hosted budgets require PostgreSQL.")
        if (env.get(KILL_ENV) or "").strip().lower() in ("1", "true", "yes"):
            ledger.kill("environment")  # latch across process restart / image rollback
        return cls(cfg, ledger, klass, default_category=default_category, environ=env)

    @classmethod
    def closed(cls, reason: str, budget_class: str = "production", environ: Mapping[str, str] | None = None) -> "BudgetGovernor":
        return cls(None, None, budget_class, closed_reason=reason, environ=environ)

    @property
    def is_open(self) -> bool:
        return self.closed_reason is None and self.config is not None and self.ledger is not None

    def killed(self) -> bool:
        if (self.env.get(KILL_ENV) or "").strip().lower() in ("1", "true", "yes"):
            return True
        return self.ledger.killed() if self.ledger else True

    def _refuse(self, reason: str, message: str):
        self.refusals.append(reason)
        raise BudgetError(reason, message)

    # ------------------------------------------------------------------ classification
    def classify(self, request: httpx.Request) -> str:
        """``passthrough`` (not a governed host), ``metadata``, ``chat`` or ``embeddings``; raises for any other endpoint of a governed host."""
        host = (request.url.host or "").lower()
        hosts = self.config.hosts if self.config else ("openrouter.ai",)
        if host not in hosts:
            paid_path = any(request.url.path.rstrip("/").endswith(p) for p in (*PRICED_ENDPOINTS, "/audio/transcriptions", "/realtime/sessions", "/responses", "/messages", "/images/generations", "/audio/speech"))
            if hosted(self.env) and (paid_path or host in ("openrouter.ai", "api.openai.com")):
                self._refuse("provider_host_not_allowed", "The provider endpoint is not approved.")
            return "passthrough"
        if request.url.scheme != "https" or request.url.port not in (None, 443) or request.url.userinfo:
            self._refuse("provider_endpoint_invalid", "The provider endpoint is not approved.")
        path = request.url.path.rstrip("/")
        if request.method == "POST" and any(path.endswith(e) for e in PRICED_ENDPOINTS):
            return "embeddings" if path.endswith("/embeddings") else "chat"
        if request.method == "GET" and path in METADATA_GET:
            return "metadata"
        self._refuse("endpoint_not_allowed", "The provider endpoint is not allowed.")
        return ""

    def category_for(self, request: httpx.Request, kind: str) -> str:
        if kind == "embeddings":
            return "embedding"
        label = (request.headers.get(OP_HEADER) or "").strip().lower()
        cat = OPERATION_CATEGORY.get(label) or self.default_category
        if cat not in CATEGORIES:
            self._refuse("category_unknown", "The request has no recognised budget category (fail closed).")
        return cat  # type: ignore[return-value]

    # ------------------------------------------------------------------ admission
    def prepare(self, request: httpx.Request, kind: str, kw: dict) -> tuple[str, str, int, str, str]:
        """Validate per-request limits and compute (model, category, worst case micro-USD, fingerprint, operation). Mutates only the request timeout (clamped)."""
        cfg = self.config
        assert cfg is not None
        lim = cfg.limits
        if kw.get("stream"):
            self._refuse("streaming_not_supported", "Streaming responses are not admitted (usage could not be settled).")
        try:
            body = json.loads(request.content or b"{}")
        except ValueError:
            self._refuse("body_unreadable", "The request body could not be inspected.")
        if not isinstance(body, dict):
            self._refuse("body_unreadable", "The request body could not be inspected.")
        if body.get("n", 1) != 1 or body.get("best_of", 1) != 1 or body.get("modalities") or body.get("audio"):
            self._refuse("request_shape_not_supported", "Only a single text completion is budget-qualified.")
        for message in body.get("messages", []) or []:
            if not isinstance(message, dict):
                self._refuse("body_unreadable", "The message body could not be inspected.")
            content = message.get("content")
            if isinstance(content, list) and any(not isinstance(part, dict) or part.get("type") != "text" for part in content):
                self._refuse("request_shape_not_supported", "Multimodal inference is not budget-qualified.")
        if body.get("stream"):
            self._refuse("streaming_not_supported", "Streaming responses are not admitted.")
        model = body.get("model")
        price = cfg.pricing.get(model) if isinstance(model, str) else None
        if price is None:
            self._refuse("model_not_priced", "The requested model has no price in the budget configuration (fail closed).")
        try:
            retry = int(request.headers.get("x-stainless-retry-count", "0"))
        except ValueError:
            self._refuse("retry_limit", "The SDK retry count is invalid.")
        if retry < 0 or retry > lim.max_retries:
            self._refuse("retry_limit", "The SDK retry count exceeds the configured maximum.")
        if kind == "embeddings":
            tokens, out_cap = estimate_tokens(json.dumps(body.get("input"), ensure_ascii=False, default=str)), 0
        else:
            cap = body.get("max_completion_tokens", body.get("max_tokens"))
            if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
                self._refuse("output_cap_missing", "The outgoing request carries no output-token cap (fail closed).")
            if cap > lim.max_output_tokens:
                self._refuse("output_cap_exceeds_limit", "The outgoing output cap exceeds the configured per-request limit.")
            tokens = estimate_tokens(json.dumps(body, ensure_ascii=False, default=str))
            out_cap = cap
        if tokens > lim.max_input_tokens:
            self._refuse("input_too_large", "The input estimate exceeds the configured per-request limit.")
        worst = usd_to_micro(Decimal(tokens) * price.prompt + Decimal(out_cap) * price.completion)
        t = float(lim.request_timeout_s)
        cur = request.extensions.get("timeout") or {}
        request.extensions["timeout"] = {k: (t if cur.get(k) is None else min(float(cur[k]), t)) for k in ("connect", "read", "write", "pool")}
        category = self.category_for(request, kind)
        fingerprint = hashlib.sha256(f"{request.method}|{request.url.path}|".encode() + json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        return model, category, worst, fingerprint, category

    def _open_or_refuse(self) -> None:
        if not self.is_open:
            self._refuse(self.closed_reason or "governor_closed", "The AI budget governor is closed (configuration, approval or ledger is not valid); paid provider calls are refused (fail closed).")
        validate_hosted_approval(self.config, self.env)
        require_approved_marker(self.config, self.env)
        if self.killed():
            self._refuse("kill_switch", "The AI budget kill switch is engaged; no provider request is sent.")

    def reserve(self, request: httpx.Request, kind: str, kw: dict) -> tuple[Reservation, str, float]:
        self._open_or_refuse()
        model, category, worst, fingerprint, operation = self.prepare(request, kind, kw)
        try:
            res = self.ledger.reserve(self.config, budget_class=self.budget_class, category=category, operation=operation, model=model, endpoint=kind, fingerprint=fingerprint, worst_case=worst)  # type: ignore[union-attr]
        except BudgetError as exc:
            self.refusals.append(exc.reason)
            raise
        if OP_HEADER in request.headers:
            del request.headers[OP_HEADER]                     # an internal label; never sent to the provider
        return res, model, time.perf_counter()

    # ------------------------------------------------------------------ settlement
    def usage_cost(self, model: str, data: dict, *, endpoint: str = "chat") -> tuple[int | None, int | None, int | None, int | None, int | None]:
        """(committed, input tokens, output tokens, our estimate, provider figure) in micro-USD, or ``None`` committed when usage is absent (UNKNOWN, never 0)."""
        u = data.get("usage") if isinstance(data, dict) else None
        u = u or {}
        tin, tout = u.get("prompt_tokens", u.get("input_tokens")), u.get("completion_tokens", u.get("output_tokens"))
        if endpoint == "embeddings" and tout is None:
            tout = 0  # Text embedding endpoints have no generated completion.
        if tin is None or tout is None:
            return None, None, None, None, None
        if type(tin) is not int or type(tout) is not int or tin < 0 or tout < 0:
            raise ValueError("invalid token usage")
        price = self.config.pricing[model]  # type: ignore[union-attr]
        est = usd_to_micro(Decimal(tin) * price.prompt + Decimal(tout) * price.completion)
        provider = usd_to_micro(Decimal(str(u["cost"]))) if u.get("cost") is not None else None
        return max(est, provider or 0), tin, tout, est, provider

    def settle_response(self, res: Reservation, model: str, response: httpx.Response, started: float) -> None:
        ms = int((time.perf_counter() - started) * 1000)
        sc = response.status_code
        led = self.ledger
        assert led is not None
        if sc == 200:
            try:
                committed, tin, tout, est, prov = self.usage_cost(model, response.json(), endpoint=res.endpoint)
                bad = False
            except Exception:  # noqa: BLE001 - an unreadable body is UNKNOWN, never zero
                committed, bad = None, True
            if committed is None:
                reported = None
                try:
                    reported = usd_to_micro(response.json()["usage"]["cost"])
                except (KeyError, ValueError, TypeError, ArithmeticError):
                    pass
                led.settle(res, outcome="unknown", committed=reported or 0, provider_cost=reported, status_code=sc, latency_ms=ms, error_category="malformed_body" if bad else "usage_missing")
            else:
                led.settle(res, outcome="settled", committed=committed, input_tokens=tin, output_tokens=tout, est_cost=est, provider_cost=prov, status_code=sc, latency_ms=ms)
        elif sc in DETERMINATE_REJECTIONS:
            led.settle(res, outcome="rejected", status_code=sc, latency_ms=ms, error_category=_error_category(sc))
        else:
            led.settle(res, outcome="unknown", status_code=sc, latency_ms=ms, error_category=_error_category(sc))

    def settle_failure(self, res: Reservation, started: float, exc: BaseException) -> None:
        try:
            self.ledger.settle(res, outcome="unknown", latency_ms=int((time.perf_counter() - started) * 1000), error_category=_error_category(None, exc))  # type: ignore[union-attr]
        except BudgetError:
            pass                                               # the reservation stays open at its worst case

    # ------------------------------------------------------------------ the two wrappers
    def send_sync(self, orig, client, request, kw):  # noqa: ANN001
        kind = self.classify(request)
        if kind == "passthrough":
            return orig(client, request, **kw)
        if kind == "metadata":
            kw["follow_redirects"] = False
            self._open_or_refuse_metadata()
            return orig(client, request, **kw)
        self._open_or_refuse()
        kw["follow_redirects"] = False
        if not self._sem.acquire(timeout=self.config.limits.request_timeout_s):  # type: ignore[union-attr]
            self._refuse("concurrency_limit", "The configured concurrency limit is saturated.")
        try:
            res, model, started = self.reserve(request, kind, kw)
            try:
                response = orig(client, request, **kw)
            except BaseException as exc:
                self.settle_failure(res, started, exc)
                raise
            self.settle_response(res, model, response, started)
            return response
        finally:
            self._sem.release()

    async def send_async(self, orig, client, request, kw):  # noqa: ANN001
        kind = self.classify(request)
        if kind == "passthrough":
            return await orig(client, request, **kw)
        if kind == "metadata":
            kw["follow_redirects"] = False
            self._open_or_refuse_metadata()
            return await orig(client, request, **kw)
        self._open_or_refuse()
        kw["follow_redirects"] = False
        # the semaphore is shared with sync callers; waiting must never block the event loop
        waiting = asyncio.get_running_loop().run_in_executor(None, lambda: self._sem.acquire(timeout=self.config.limits.request_timeout_s))  # type: ignore[union-attr]
        try:
            got = await asyncio.shield(waiting)
        except BaseException:
            # Cancellation cannot abandon a background waiter that later acquires.
            waiting.add_done_callback(lambda task: self._sem.release() if task.result() else None)
            raise
        if not got:
            self._refuse("concurrency_limit", "The configured concurrency limit is saturated.")
        try:
            res, model, started = self.reserve(request, kind, kw)
            try:
                response = await orig(client, request, **kw)
                await response.aread()
            except BaseException as exc:
                self.settle_failure(res, started, exc)
                raise
            self.settle_response(res, model, response, started)
            return response
        finally:
            self._sem.release()

    def _open_or_refuse_metadata(self) -> None:
        """Free metadata GETs consume no tokens: they need only a valid, not-killed governor (they are how the owner checks a key and the model list)."""
        self._open_or_refuse()

    # ------------------------------------------------------------------ status (no key, no prompt text)
    def status(self) -> dict[str, Any]:
        if not self.is_open:
            return {"state": "closed", "reason": self.closed_reason, "budget_class": self.budget_class}
        snap = self.ledger.snapshot(self.config, self.budget_class)  # type: ignore[union-attr]
        snap["state"] = "killed" if self.killed() else ("stopped" if Decimal(snap["remaining_to_stop_usd"]) == 0 or snap["remaining_requests"] == 0 else "open")
        snap["integrity"] = self.ledger.integrity(self.budget_class)  # type: ignore[union-attr]
        if not snap["integrity"]["consistent"]:
            snap.update(state="unavailable", reason="ledger_inconsistent")
        return snap


# ------------------------------------------------------------------ process-wide install (one chokepoint)
class _Installed:
    governor: BudgetGovernor | None = None
    orig_sync = None
    orig_async = None


def active_governor() -> BudgetGovernor | None:
    return _Installed.governor


def install(governor: BudgetGovernor) -> BudgetGovernor:
    if _Installed.governor is not None:
        raise BudgetError("guard_active", "An AI budget governor is already installed in this process.")
    try:
        from src.demo_live.guard import ProviderControl

        if ProviderControl._active is not None:
            raise BudgetError("guard_conflict", "The capstone demonstration provider control is installed; the production governor is not used together with it.")
    except ImportError:  # pragma: no cover
        pass
    _Installed.orig_sync, _Installed.orig_async = httpx.Client.send, httpx.AsyncClient.send

    def sync_send(client, request, **kw):  # noqa: ANN001
        return governor.send_sync(_Installed.orig_sync, client, request, kw)

    async def async_send(client, request, **kw):  # noqa: ANN001
        return await governor.send_async(_Installed.orig_async, client, request, kw)

    httpx.Client.send, httpx.AsyncClient.send = sync_send, async_send
    _Installed.governor = governor
    return governor


def uninstall() -> None:
    if _Installed.governor is not None:
        httpx.Client.send, httpx.AsyncClient.send = _Installed.orig_sync, _Installed.orig_async
        _Installed.governor, _Installed.orig_sync, _Installed.orig_async = None, None, None


def install_from_env(session_factory=None, environ: Mapping[str, str] | None = None) -> BudgetGovernor | None:
    """Install the governor when ``AI_BUDGET_MODE=enforce``; ``None`` (provider behaviour unchanged) otherwise. When enforcement is requested but the configuration, approval marker or ledger
    is not valid, a CLOSED governor is installed instead: the process keeps serving non-AI traffic and every paid provider call is refused with the reason (fail closed)."""
    env = os.environ if environ is None else environ
    if (env.get(MODE_ENV) or "").strip().lower() != "enforce":
        if not hosted(env):
            return None
        if _Installed.governor is not None:
            return _Installed.governor
        return install(BudgetGovernor.closed("enforcement_required", environ=env))
    if _Installed.governor is not None:
        return _Installed.governor
    try:
        if session_factory is None:
            from src.config import load_config as load_app_config
            from src.persistence import make_engine, make_session_factory

            session_factory = make_session_factory(make_engine(load_app_config().database_url))
        governor = BudgetGovernor.build(session_factory, environ=env)
    except BudgetError as exc:
        governor = BudgetGovernor.closed(exc.reason, environ=env)
    except Exception:  # noqa: BLE001 - any other construction problem is also closed
        governor = BudgetGovernor.closed("ledger_unavailable", environ=env)
    return install(governor)


def refuse_ungoverned_transport(environ: Mapping[str, str] | None = None) -> None:
    """Legacy speech/realtime SDKs have no qualified monetary settlement contract."""
    if hosted(os.environ if environ is None else environ):
        raise BudgetError("transport_not_qualified", "This AI transport is not budget-qualified for hosted use.")
