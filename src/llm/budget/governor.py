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
import inspect
import json
import math
import os
import threading
import time
from concurrent.futures import CancelledError as SyncCancelledError
from decimal import Decimal
from typing import Any, Callable, Mapping
from weakref import WeakSet

import httpx

from src.llm.budget.config import (
    BudgetConfig, CATEGORIES, GOVERNED_07B_LEDGER_ENV, GOVERNED_07B_MAX_EMBEDDING_INPUTS, GOVERNED_07B_OPERATIONS, KILL_ENV, MICRO, MODE_ENV,
    check_07b_handoff_deadline, hosted, load_config, require_approved_marker, resolve_budget_class, usd_to_micro, validate_hosted_approval,
)
from src.llm.budget.errors import BudgetError
from src.llm.budget.ledger import SQLITE_MAX_INTEGER, DbBudgetLedger, Reservation
from src.llm.budget.postgres_07b import Postgres07BLedger, validate_postgres_url

HOSTED_POLICY_VERSION = 2

OP_HEADER = "x-ask4mo-operation"
METADATA_GET = ("/api/v1/key", "/api/v1/models", "/api/v1/credits", "/api/v1/embeddings/models")
PRICED_ENDPOINTS = ("/chat/completions", "/embeddings")
PAID_PATH_SUFFIXES = (*PRICED_ENDPOINTS, "/audio/transcriptions", "/realtime/sessions", "/responses",
                      "/messages", "/images/generations", "/audio/speech")
GOVERNED_07B_PATHS = {b"/api/v1/chat/completions": "chat", b"/api/v1/embeddings": "embeddings"}
GOVERNED_07B_CHAT_FIELDS = {
    "model", "messages", "max_tokens", "max_completion_tokens", "temperature", "top_p",
    "frequency_penalty", "presence_penalty", "seed", "stop", "n", "stream", "response_format",
}
GOVERNED_07B_EMBED_FIELDS = {"model", "input", "dimensions", "encoding_format"}
DETERMINATE_REJECTIONS = (400, 401, 402, 403, 404, 422, 429)
MAX_429_EVIDENCE_BYTES = 64 * 1024
MAX_LEDGER_USD = Decimal(SQLITE_MAX_INTEGER) / MICRO
CHARGE_TOKEN_FIELDS = {
    "prompt_tokens", "completion_tokens", "input_tokens", "output_tokens", "total_tokens",
    "reasoning_tokens", "cached_tokens", "cache_read_input_tokens", "cache_write_input_tokens",
}
CHARGE_COST_FIELDS = {
    "cost", "provider_cost", "provider_cost_usd", "cost_usd", "total_cost", "total_cost_usd",
    "upstream_inference_cost", "upstream_inference_prompt_cost", "upstream_inference_completions_cost",
}
OPERATION_CATEGORY = {"agent": "agent", "interview": "interview", "embedding": "embedding", "embeddings": "embedding", "evaluation": "evaluation", "ragas": "evaluation"}


def estimate_tokens(text: str) -> int:
    """Conservative byte bound, including non-ASCII input and serialized tool schemas."""
    return max(1, len(text.encode("utf-8")))


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    body = dict(pairs)
    if len(body) != len(pairs):
        raise ValueError("duplicate request fields")
    return body


class _ChargeObject(tuple):
    """Preserve ordered JSON object pairs and distinguish them from arrays."""


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError("non-finite JSON number")


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

    def __init__(self, config: BudgetConfig | None, ledger: DbBudgetLedger | Postgres07BLedger | None, budget_class: str, *, default_category: str | None = None,
                 closed_reason: str | None = None, environ: Mapping[str, str] | None = None, governed_07b: bool = False) -> None:
        self.config, self.ledger, self.budget_class = config, ledger, budget_class
        self.default_category = default_category
        self.closed_reason = closed_reason
        self.env = os.environ if environ is None else environ
        self._hosted_at_build = hosted(self.env)
        self.refusals: list[str] = []
        self.governed_07b = governed_07b
        self._seen_07b: set[str] = set()
        self._stopped_07b = False
        self._prototype_clients: WeakSet = WeakSet()
        self.prototype_handler: Callable | None = None
        self._sem = threading.BoundedSemaphore(config.limits.max_concurrency) if config else None

    # ------------------------------------------------------------------ construction
    @classmethod
    def build(cls, session_factory, *, budget_class: str | None = None, default_category: str | None = None, environ: Mapping[str, str] | None = None,
              config: BudgetConfig | None = None, require_marker: bool = True, governed_07b: bool = False) -> "BudgetGovernor":
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
        if require_marker or governed_07b:
            require_approved_marker(cfg, env)
        validate_hosted_approval(cfg, env, governed_07b=governed_07b)
        if governed_07b and klass != "evaluation":
            raise BudgetError("class_mismatch", "07B requires the evaluation budget class.")
        postgres_07b = False
        if governed_07b:
            from sqlalchemy.engine import make_url
            from sqlalchemy.exc import ArgumentError

            try:
                expected = make_url(env[GOVERNED_07B_LEDGER_ENV])
            except (ArgumentError, KeyError):
                raise BudgetError("ledger_unavailable", "07B requires the approved dedicated durable ledger.") from None
            with session_factory() as session:
                bind = session.get_bind()
                if bind.url != expected:
                    raise BudgetError("ledger_unavailable", "07B requires the approved dedicated durable ledger.")
                postgres_07b = bind.dialect.name == "postgresql"
                if postgres_07b:
                    validate_postgres_url(expected)
                elif bind.dialect.name != "sqlite":
                    raise BudgetError("transport_not_qualified", "07B requires an approved SQLite or PostgreSQL ledger.")
        ledger = Postgres07BLedger(session_factory, cfg) if postgres_07b else DbBudgetLedger(session_factory)
        ledger.ensure_ready()
        if hosted(env):
            with session_factory() as session:
                if session.get_bind().dialect.name != "postgresql":
                    raise BudgetError("durable_ledger_required", "Hosted budgets require PostgreSQL.")
        if (env.get(KILL_ENV) or "").strip().lower() in ("1", "true", "yes"):
            if isinstance(ledger, Postgres07BLedger):
                raise BudgetError("kill_switch", "07B was stopped locally. A durable stop requires the stop operator.")
            ledger.kill("environment")  # latch across process restart / image rollback
        return cls(cfg, ledger, klass, default_category=default_category, environ=env, governed_07b=governed_07b)

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
            paid_path = request.url.path.rstrip("/").endswith(PAID_PATH_SUFFIXES)
            if self.governed_07b or (hosted(self.env) and (paid_path or host in ("openrouter.ai", "api.openai.com"))):
                self._refuse("provider_host_not_allowed", "The provider endpoint is not approved.")
            return "passthrough"
        if request.url.scheme != "https" or request.url.port not in (None, 443) or request.url.userinfo:
            self._refuse("provider_endpoint_invalid", "The provider endpoint is not approved.")
        if self.governed_07b:
            if (request.headers.get_list("host") != [host] or request.url.fragment
                    or {"sni_hostname", "target"} & request.extensions.keys()):
                self._refuse("provider_endpoint_invalid", "The provider endpoint is not approved.")
            kind = GOVERNED_07B_PATHS.get(request.url.raw_path)
            if request.method != "POST" or kind is None:
                self._refuse("endpoint_not_allowed", "The provider endpoint is not allowed.")
            return kind
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
            body = json.loads(request.content or b"{}", object_pairs_hook=_unique_json_object if self.governed_07b else None)
        except (ValueError, httpx.RequestNotRead):
            self._refuse("body_unreadable", "The request body could not be inspected.")
        if not isinstance(body, dict):
            self._refuse("body_unreadable", "The request body could not be inspected.")
        if self.governed_07b:
            self._validate_07b_body(body, kind)
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
        cur = request.extensions.get("timeout", {})
        phases = ("connect", "read", "write", "pool")
        if self.governed_07b:
            if (not isinstance(cur, dict) or cur.keys() - set(phases)
                    or any(value is not None and (type(value) not in (float, int) or not 0 < value < math.inf)
                           for value in cur.values())):
                self._refuse("invalid_timeout", "07B requires positive finite transport timeouts.")
            request.extensions["timeout"] = {key: min(cur.get(key) or t, t) for key in phases}
        else:
            cur = cur or {}
            request.extensions["timeout"] = {key: (t if cur.get(key) is None else min(float(cur[key]), t)) for key in phases}
        if self.governed_07b:
            operation = request.headers.get(OP_HEADER, "")
            category = self._07b_category(operation, kind, model)
            target = str(request.url)
        else:
            category = operation = self.category_for(request, kind)
            target = request.url.path
        fingerprint = hashlib.sha256(f"{request.method}|{target}|".encode() + json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        return model, category, worst, fingerprint, operation

    def _validate_07b_body(self, body: dict, kind: str) -> None:
        if kind == "embeddings":
            inputs = body.get("input")
            if (not isinstance(inputs, list) or not inputs
                    or any(not isinstance(item, str) or not item.strip() for item in inputs)):
                self._refuse("embedding_input_invalid", "07B embeddings require nonempty text inputs.")
            if len(inputs) > GOVERNED_07B_MAX_EMBEDDING_INPUTS:
                self._refuse("input_too_large", "The embedding batch exceeds the approved input count.")
            if (body.keys() - GOVERNED_07B_EMBED_FIELDS
                    or body.get("encoding_format", "float") not in ("float", "base64")
                    or ("dimensions" in body and (type(body["dimensions"]) is not int or body["dimensions"] <= 0))):
                self._refuse("request_shape_not_supported", "The embedding request shape is not approved.")
            return
        messages = body.get("messages")
        if (body.keys() - GOVERNED_07B_CHAT_FIELDS or not isinstance(messages, list) or not messages
                or any(not isinstance(item, dict) or item.keys() - {"role", "content", "name"}
                       or item.get("role") not in ("system", "developer", "user", "assistant")
                       or not isinstance(item.get("content"), str) for item in messages)
                or {"max_tokens", "max_completion_tokens"} <= body.keys()
                or type(body.get("n", 1)) is not int
                or type(body.get("stream", False)) is not bool):
            self._refuse("request_shape_not_supported", "The chat request shape is not approved.")

    def _07b_category(self, operation: str, kind: str, model: str) -> str:
        policy = GOVERNED_07B_OPERATIONS.get(operation)
        if policy is None or policy[0] != kind:
            self._refuse("category_unknown", "The request operation is not approved for this endpoint.")
        if self.config.approval["operation_models"][operation] != model:
            self._refuse("model_not_allowed", "The model is not approved for this operation.")
        return policy[1]

    def _open_or_refuse(self) -> None:
        if not self.is_open:
            self._refuse(self.closed_reason or "governor_closed", "The AI budget governor is closed (configuration, approval or ledger is not valid); paid provider calls are refused (fail closed).")
        validate_hosted_approval(self.config, self.env, governed_07b=self.governed_07b)
        require_approved_marker(self.config, self.env)
        if self.governed_07b and self._stopped_07b:
            self._refuse("evaluation_stopped", "The 07B run stopped after a provider or accounting failure.")
        if self.killed():
            self._refuse("kill_switch", "The AI budget kill switch is engaged; no provider request is sent.")

    def reserve(self, request: httpx.Request, kind: str, kw: dict) -> tuple[Reservation, str, float]:
        self._open_or_refuse()
        model, category, worst, fingerprint, operation = self.prepare(request, kind, kw)
        if self.governed_07b:
            if fingerprint in self._seen_07b:
                self._refuse("retry_limit", "An identical request was already dispatched in this 07B run.")
            if self._unknown_07b():
                self._refuse("unknown_outcome_no_retry", "An earlier provider outcome requires reconciliation.")
        try:
            res = self.ledger.reserve(self.config, budget_class=self.budget_class, category=category,
                                      operation=operation, model=model, endpoint=kind, fingerprint=fingerprint,
                                      worst_case=worst, governed_07b=self.governed_07b)  # type: ignore[union-attr]
        except BudgetError as exc:
            self.refusals.append(exc.reason)
            raise
        if self.governed_07b:
            # Check after the one durable concurrency slot is held. A separate
            # process cannot settle an earlier reservation after this check.
            if self._unknown_07b():
                self.ledger.settle(res, outcome="rejected", error_category="reconciliation_required")
                self._refuse("unknown_outcome_no_retry", "An earlier provider outcome requires reconciliation.")
            try:
                self._open_or_refuse()
            except BudgetError:
                self.ledger.settle(res, outcome="rejected", error_category="admission_changed")
                raise
            self._seen_07b.add(fingerprint)
        if OP_HEADER in request.headers:
            del request.headers[OP_HEADER]                     # an internal label; never sent to the provider
        return res, model, time.perf_counter()

    def _unknown_07b(self) -> bool:
        try:
            counts = self.ledger.snapshot(self.config, self.budget_class)["calls_by_state"]
        except Exception:
            self._stopped_07b = True
            raise BudgetError("ledger_error", "07B could not verify outstanding holds.") from None
        return bool(counts.get("unknown"))

    # ------------------------------------------------------------------ settlement
    def usage_cost(self, model: str, data: dict, *, endpoint: str = "chat") -> tuple[int | None, int | None, int | None, int | None, int | None]:
        """(committed, input tokens, output tokens, our estimate, provider figure) in micro-USD, or ``None`` committed when usage is absent (UNKNOWN, never 0)."""
        u = data.get("usage") if isinstance(data, dict) else None
        u = u or {}
        tin, tout = u.get("prompt_tokens", u.get("input_tokens")), u.get("completion_tokens", u.get("output_tokens"))
        if endpoint == "embeddings" and tout is None:
            tout = 0  # Text embedding endpoints have no generated completion.
        if tin is None or tout is None:
            return None, tin if type(tin) is int and tin >= 0 else None, tout if type(tout) is int and tout >= 0 else None, None, None
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
                data = response.json()
                if self.governed_07b and (not isinstance(data, dict) or data.get("model") != model or "error" in data):
                    raise ValueError("unexpected provider response identity")
                committed, tin, tout, est, prov = self.usage_cost(model, data, endpoint=res.endpoint)
                bad = False
            except Exception:  # noqa: BLE001 - an unreadable body is UNKNOWN, never zero
                committed, tin, tout, bad = None, None, None, True
            if committed is None:
                self._stopped_07b |= self.governed_07b
                reported = None
                try:
                    reported = usd_to_micro(response.json()["usage"]["cost"])
                except (KeyError, ValueError, TypeError, ArithmeticError):
                    pass
                led.settle(res, outcome="unknown", committed=reported or 0, input_tokens=tin, output_tokens=tout, provider_cost=reported, status_code=sc, latency_ms=ms, error_category="malformed_body" if bad else "usage_missing")
                if self.governed_07b:
                    self._refuse("outcome_unknown", "The provider response could not be reconciled.")
            else:
                led.settle(res, outcome="settled", committed=committed, input_tokens=tin, output_tokens=tout, est_cost=est, provider_cost=prov, status_code=sc, latency_ms=ms)
                if self.governed_07b and committed > res.worst_case:
                    self._refuse("budget_overrun", "Provider usage exceeded the reservation.")
        elif sc in DETERMINATE_REJECTIONS:
            self._stopped_07b |= self.governed_07b
            evidence = None
            if self.governed_07b:
                evidence = self._rate_limit_charge(response) if sc == 429 else self._rejection_charge(response)
            if evidence is not None:
                led.settle(res, outcome="unknown", committed=evidence, status_code=sc, latency_ms=ms,
                           error_category="contradictory_charge")
                self._refuse("outcome_unknown", "Provider rejection carried conflicting charge evidence.")
            led.settle(res, outcome="rejected", status_code=sc, latency_ms=ms, error_category=_error_category(sc))
        else:
            self._stopped_07b |= self.governed_07b
            led.settle(res, outcome="unknown", status_code=sc, latency_ms=ms, error_category=_error_category(sc))
            if self.governed_07b:
                self._refuse("outcome_unknown", "The provider response could not be reconciled.")

    @staticmethod
    def _rate_limit_charge(response: httpx.Response) -> int | None:
        """None means a clean 429, zero means unknown cost, positive means reported exposure."""
        try:
            body = response.content
            if len(body) > MAX_429_EVIDENCE_BYTES:
                return 0
            root = json.loads(body, object_pairs_hook=_ChargeObject, parse_float=Decimal,
                              parse_constant=_reject_nonfinite_json)
        except (httpx.ResponseNotRead, ValueError, RecursionError, ArithmeticError):
            return 0
        if not isinstance(root, _ChargeObject):
            return 0

        reported = 0
        ambiguous = False
        pending = [root]
        while pending:
            node = pending.pop()
            if isinstance(node, list):
                pending.extend(node)
            if not isinstance(node, _ChargeObject):
                continue
            seen = set()
            for key, value in node:
                ambiguous |= key in seen
                seen.add(key)
                if key in ("usage", "cost_details") and not isinstance(value, _ChargeObject):
                    ambiguous = True
                if key in CHARGE_TOKEN_FIELDS:
                    ambiguous |= type(value) is not int or value != 0
                if key in CHARGE_COST_FIELDS:
                    try:
                        if type(value) not in (str, int, Decimal) or len(str(value)) > 64:
                            raise ValueError
                        cost = Decimal(str(value))
                        if not cost.is_finite() or not 0 <= cost <= MAX_LEDGER_USD:
                            raise ValueError
                        # A positive value remains charge evidence if conversion underflows.
                        ambiguous |= cost > 0
                        reported = max(reported, usd_to_micro(cost))
                    except (ValueError, ArithmeticError):
                        ambiguous = True
                if isinstance(value, (_ChargeObject, list)):
                    pending.append(value)
        return reported if reported or ambiguous else None

    @staticmethod
    def _rejection_charge(response: httpx.Response) -> int | None:
        try:
            data = response.json()
        except ValueError:
            return None
        usage = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            return None
        try:
            cost = usd_to_micro(Decimal(str(usage.get("cost"))))
        except (ValueError, TypeError, ArithmeticError):
            cost = 0
        if cost or any(type(usage.get(key)) is int and usage[key] > 0
                       for key in ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens", "total_tokens")):
            return cost
        return None

    def settle_failure(self, res: Reservation, started: float, exc: BaseException) -> None:
        self._stopped_07b |= self.governed_07b
        try:
            self.ledger.settle(res, outcome="unknown", latency_ms=int((time.perf_counter() - started) * 1000), error_category=_error_category(None, exc))  # type: ignore[union-attr]
        except BudgetError:
            pass                                               # the reservation stays open at its worst case

    def prototype_client(self, handler: Callable | None = None, *, asynchronous: bool = False):
        """Create a closed-world HTTPX client for the offline 07B fixture."""
        if handler is None:
            handler = self.prototype_handler
        if not self.governed_07b or not callable(handler):
            self._refuse("transport_not_qualified", "07B requires a synthetic transport handler.")
        transport = _07BPrototypeTransport(self, handler)
        client_cls = httpx.AsyncClient if asynchronous else httpx.Client
        client = client_cls(transport=transport, trust_env=False)
        self._prototype_clients.add(client)
        return client

    def _prototype_send_options(self, client, kw: dict) -> None:
        if client not in self._prototype_clients or client.event_hooks["request"] or kw.get("stream"):
            self._refuse("transport_not_qualified", "07B admits only its offline transport without mutation hooks or streaming.")
        kw.update(follow_redirects=False, auth=None)

    # ------------------------------------------------------------------ the two wrappers
    def send_sync(self, orig, client, request, kw):  # noqa: ANN001
        kind = self.classify(request)
        if self.governed_07b:
            self._prototype_send_options(client, kw)
            return orig(client, request, **kw)
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
        if self.governed_07b:
            self._prototype_send_options(client, kw)
            return await orig(client, request, **kw)
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


class _07BPrototypeTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """The actual receiving HTTPX transport in the offline prototype. It has no network delegate."""

    def __init__(self, governor: BudgetGovernor, handler: Callable) -> None:
        self.governor = governor
        self.handler = handler

    def _receive(self, request: httpx.Request, *, task: asyncio.Task | None = None):
        gov = self.governor
        kind = gov.classify(request)
        reservation, model, started = gov.reserve(request, kind, {})
        accepted = False

        def accept():
            nonlocal accepted
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            if (gov.env.get(KILL_ENV) or "").strip().lower() in ("1", "true", "yes"):
                raise BudgetError("kill_switch", "07B was stopped before transport acceptance.")
            check_07b_handoff_deadline(gov.config)
            # Successful acceptance linearizes at the clock sample inside this
            # actual receiver, while the database excludes concurrent kill commits.
            accepted = True

        try:
            gov.ledger.accept_07b_handoff(reservation, accept)
        except BaseException as exc:
            if not accepted and (isinstance(exc, (asyncio.CancelledError, SyncCancelledError, KeyboardInterrupt))
                                 or isinstance(exc, BudgetError) and exc.reason in ("kill_switch", "approval_invalid")):
                gov.ledger.settle(reservation, outcome="rejected", error_category="admission_changed")
            else:
                gov.settle_failure(reservation, started, exc)
            raise
        return reservation, model, started

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        gov = self.governor
        reservation, model, started = self._receive(request)
        try:
            response = self.handler(request)
            response.read()
        except BaseException as exc:
            gov.settle_failure(reservation, started, exc)
            raise
        gov.settle_response(reservation, model, response, started)
        return response

    async def _receive_postgres(self, request: httpx.Request):
        # PostgreSQL lock or connection waits must not block the event loop.
        # Cancellation discards the receiver result and never invokes the
        # handler. If acceptance already committed, its hold stays durable.
        task = asyncio.current_task()
        worker = asyncio.create_task(asyncio.to_thread(self._receive, request, task=task))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            worker.add_done_callback(self._observe_abandoned_receiver)
            raise

    @staticmethod
    def _observe_abandoned_receiver(worker: asyncio.Task) -> None:
        if not worker.cancelled():
            worker.exception()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        gov = self.governor
        postgres = isinstance(gov.ledger, Postgres07BLedger)
        if postgres:
            reservation, model, started = await self._receive_postgres(request)
        else:
            reservation, model, started = self._receive(request, task=asyncio.current_task())
        try:
            response = self.handler(request)
            if inspect.isawaitable(response):
                response = await response
            await response.aread()
        except BaseException as exc:
            if postgres:
                await asyncio.to_thread(gov.settle_failure, reservation, started, exc)
            else:
                gov.settle_failure(reservation, started, exc)
            raise
        if postgres:
            await asyncio.to_thread(gov.settle_response, reservation, model, response, started)
        else:
            gov.settle_response(reservation, model, response, started)
        return response


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

        control = ProviderControl._active
        # A CLOSED governor may layer over the offline network refusal. Neither
        # layer can authorize spending. Open/live controls remain incompatible.
        if control is not None and not (control.mode == "offline" and governor.closed_reason):
            raise BudgetError("guard_conflict", "The capstone demonstration provider control is installed; an open production governor is not used together with it.")
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
    existing = _Installed.governor
    if existing is not None and hosted(env):
        existing.env = env
        try:
            class_matches = existing.budget_class == resolve_budget_class(env)
        except BudgetError:
            class_matches = False
        if not existing._hosted_at_build or not class_matches or existing.budget_class == "development" or (env.get(MODE_ENV) or "").strip().lower() != "enforce":
            existing.closed_reason = "enforcement_required"
        return existing
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
    current = active_governor()
    if current is not None and current.governed_07b:
        raise BudgetError("transport_not_qualified", "This AI transport is not budget-qualified for 07B.")
    if hosted(os.environ if environ is None else environ):
        raise BudgetError("transport_not_qualified", "This AI transport is not budget-qualified for hosted use.")
