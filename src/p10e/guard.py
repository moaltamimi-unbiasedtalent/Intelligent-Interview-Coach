"""P10E live-run guard: no paid provider call is possible without owner-approved, finite limits.

The owner authorized paid provider use for P10E (2026-10-19) but named NO monetary ceiling and NO call count. This module turns that into code:

* ``load_authorization`` reads ``evaluations/p10e/authorization.json``. ``limits`` is ``None`` until the owner approves them in a reviewed commit.
* ``require_live`` refuses (``LiveRunRefused``) unless: not running in CI, the explicit opt-in ``P10E_LIVE=1`` is set, the limits are present, finite, positive and approved
  (who, when, reference), and (optionally) a credential exists. Engineering never fills the limits in.
* ``LiveBudget`` admits every provider call BEFORE it is made, using a worst-case cost (input estimate and the output cap, multiplied by the allowed attempts) and stops when the
  call count or the spend ceiling could be exceeded. A missing token count or cost is UNKNOWN, never zero: an unknown outcome keeps its worst-case reservation, and a model with no
  published price cannot be admitted at all because the ceiling could not be enforced.
* ``GuardCallback`` enforces this on every LangChain chat-model call (including the nested calls an agent makes); ``LiveRunRecorder`` writes append-only evidence.

Nothing here makes a network call. A normal test run stays offline.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUTH_PATH = ROOT / "evaluations" / "p10e" / "authorization.json"
PRICING_PATH = ROOT / "evaluations" / "p10e" / "pricing_snapshot.json"
LIVE_DIR = ROOT / "evaluations" / "p10e" / "live"

REQUIRED_LIMITS = ("max_spend_usd", "max_provider_calls", "max_input_tokens_per_request", "max_output_tokens_per_request", "request_timeout_s", "max_retries", "max_concurrency")
HARD_CAPS = {"max_retries": 2, "max_concurrency": 4}            # even an approved value cannot exceed these: "bounded retries, bounded concurrency"
CHARS_PER_TOKEN_PESSIMISTIC = 3                                 # fewer characters per token than typical text, so the input estimate errs high


class LiveRunRefused(Exception):
    """A paid call was refused. ``reason`` is a stable machine-readable code; the message never contains a credential."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class BudgetExceeded(LiveRunRefused):
    pass


@dataclass(frozen=True)
class LiveLimits:
    max_spend_usd: Decimal
    max_provider_calls: int
    max_input_tokens_per_request: int
    max_output_tokens_per_request: int
    request_timeout_s: int
    max_retries: int
    max_concurrency: int

    @staticmethod
    def parse(raw: Any) -> "LiveLimits":
        if not isinstance(raw, dict):
            raise LiveRunRefused("limits_missing", "No owner-approved limits are recorded (limits is empty). Paid execution is refused.")
        missing = [k for k in REQUIRED_LIMITS if raw.get(k) is None]
        if missing:
            raise LiveRunRefused("limits_incomplete", f"Owner-approved limits are incomplete; missing: {', '.join(missing)}.")
        try:
            spend = Decimal(str(raw["max_spend_usd"]))
            ints = {k: int(raw[k]) for k in REQUIRED_LIMITS if k != "max_spend_usd"}
        except Exception as exc:  # noqa: BLE001
            raise LiveRunRefused("limits_invalid", "A limit is not a number.") from exc
        if not spend.is_finite() or spend <= 0:
            raise LiveRunRefused("limits_invalid", "max_spend_usd must be a finite amount above zero (unlimited spending is not authorized).")
        for k, v in ints.items():
            if v < 0 or (v == 0 and k != "max_retries"):
                raise LiveRunRefused("limits_invalid", f"{k} must be a positive whole number.")
            if k in HARD_CAPS and v > HARD_CAPS[k]:
                raise LiveRunRefused("limits_invalid", f"{k} may not exceed {HARD_CAPS[k]} (bounded by design).")
        return LiveLimits(max_spend_usd=spend, **ints)


@dataclass(frozen=True)
class Authorization:
    owner_decision_date: str
    paid_use_granted: bool
    limits_raw: Any
    approved_by: str | None
    approval_date: str | None
    reference: str | None
    raw: dict = field(default_factory=dict)


def load_authorization(path: Path = AUTH_PATH) -> Authorization:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LiveRunRefused("authorization_missing", "The P10E authorization record is missing or unreadable.") from exc
    appr = raw.get("limits_approval") or {}
    return Authorization(owner_decision_date=str(raw.get("owner_decision_date", "")), paid_use_granted=bool((raw.get("granted") or {}).get("paid_provider_use_for_p10e")),
                         limits_raw=raw.get("limits"), approved_by=appr.get("approved_by"), approval_date=appr.get("approval_date"), reference=appr.get("reference"), raw=raw)


def in_ci(env: dict | None = None) -> bool:
    e = os.environ if env is None else env
    return any(str(e.get(k, "")).strip().lower() in ("1", "true", "yes") for k in ("CI", "GITHUB_ACTIONS"))


def require_live(auth: Authorization | None = None, *, env: dict | None = None, credential_names: tuple[str, ...] = ()) -> LiveLimits:
    """Return the approved limits or raise ``LiveRunRefused``. Reads credential PRESENCE only, never a value."""
    e = os.environ if env is None else env
    auth = auth or load_authorization()
    if in_ci(e):
        raise LiveRunRefused("ci_forbidden", "Paid provider calls never run in CI.")
    if str(e.get("P10E_LIVE", "")).strip() != "1":
        raise LiveRunRefused("opt_in_missing", "Paid execution needs the explicit opt-in P10E_LIVE=1 for this run.")
    if not auth.paid_use_granted or auth.owner_decision_date != "2026-10-19":
        raise LiveRunRefused("not_authorized", "The owner authorization for paid P10E provider use is not recorded.")
    if not (auth.approved_by and auth.approval_date and auth.reference):
        raise LiveRunRefused("limits_not_approved", "The spending and call limits have no recorded owner approval (approved_by, approval_date, reference).")
    limits = LiveLimits.parse(auth.limits_raw)
    absent = [n for n in credential_names if not str(e.get(n, "")).strip()]
    if absent:
        raise LiveRunRefused("credential_missing", f"Required credential(s) not configured: {', '.join(absent)}.")
    return limits


def load_prices(path: Path = PRICING_PATH) -> dict[str, tuple[Decimal, Decimal]]:
    snap = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for slug, m in snap["models"].items():
        if m.get("available") and m.get("usd_per_input_token") and m.get("usd_per_output_token"):
            out[slug] = (Decimal(m["usd_per_input_token"]), Decimal(m["usd_per_output_token"]))
    return out


def estimate_input_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN_PESSIMISTIC))


class LiveBudget:
    """Thread-safe admission control and accounting. Costs are Decimal USD estimates from the published price snapshot, not billed amounts."""

    def __init__(self, limits: LiveLimits, prices: dict[str, tuple[Decimal, Decimal]]) -> None:
        self.limits, self.prices = limits, prices
        self._lock = threading.Lock()
        self.calls_admitted = 0
        self.calls_completed = 0
        self.calls_failed = 0
        self.input_tokens_known = 0
        self.output_tokens_known = 0
        self.calls_with_unknown_usage = 0
        self.spent_known = Decimal(0)                  # cost computed from reported token counts
        self.reserved_unknown = Decimal(0)             # worst-case reservations that were never resolved to a known count
        self.in_flight = Decimal(0)
        self.latencies_ms: list[int] = []
        self.refusals: list[str] = []

    def _worst_case(self, model: str, input_tokens: int, max_output: int) -> Decimal:
        if model not in self.prices:
            raise BudgetExceeded("price_unknown", f"No published price for model '{model}', so the spending ceiling cannot be enforced. The call is refused.")
        pi, po = self.prices[model]
        return (pi * input_tokens + po * max_output) * (1 + self.limits.max_retries)

    def committed(self) -> Decimal:
        return self.spent_known + self.reserved_unknown + self.in_flight

    def admit(self, model: str, input_tokens: int, max_output_tokens: int | None = None) -> Decimal:
        out_cap = self.limits.max_output_tokens_per_request if max_output_tokens is None else max_output_tokens
        with self._lock:
            def refuse(reason: str, msg: str):
                self.refusals.append(reason)
                raise BudgetExceeded(reason, msg)
            if input_tokens > self.limits.max_input_tokens_per_request:
                refuse("request_too_large", f"Estimated input of {input_tokens} tokens exceeds the approved per-request limit.")
            if out_cap > self.limits.max_output_tokens_per_request:
                refuse("output_cap_exceeds_limit", "The requested output cap exceeds the approved per-request limit.")
            if self.calls_admitted + 1 > self.limits.max_provider_calls:
                refuse("call_limit", "The approved provider-call limit is reached.")
            try:
                worst = self._worst_case(model, input_tokens, out_cap)
            except BudgetExceeded as exc:
                self.refusals.append(exc.reason)
                raise
            if self.committed() + worst > self.limits.max_spend_usd:
                refuse("spend_ceiling", "This call could exceed the approved spending ceiling (worst case); it is refused.")
            self.calls_admitted += 1
            self.in_flight += worst
            return worst

    def settle(self, model: str, reserved: Decimal, *, input_tokens: int | None, output_tokens: int | None, ok: bool, latency_ms: int | None = None) -> None:
        with self._lock:
            self.in_flight -= reserved
            if ok:
                self.calls_completed += 1
            else:
                self.calls_failed += 1
            if latency_ms is not None:
                self.latencies_ms.append(latency_ms)
            if input_tokens is not None and output_tokens is not None and model in self.prices:
                pi, po = self.prices[model]
                self.input_tokens_known += int(input_tokens)
                self.output_tokens_known += int(output_tokens)
                self.spent_known += pi * int(input_tokens) + po * int(output_tokens)
            else:
                # UNKNOWN is not zero: the worst-case reservation stays committed for the rest of the run.
                self.calls_with_unknown_usage += 1
                self.reserved_unknown += reserved

    def summary(self) -> dict:
        lat = sorted(self.latencies_ms)
        return {"calls_admitted": self.calls_admitted, "calls_completed": self.calls_completed, "calls_failed": self.calls_failed,
                "calls_with_unknown_usage": self.calls_with_unknown_usage, "input_tokens_known": self.input_tokens_known, "output_tokens_known": self.output_tokens_known,
                "total_tokens_known": self.input_tokens_known + self.output_tokens_known,
                "cost_known_usd_estimate": str(self.spent_known), "cost_unknown_assumed_worst_case_usd": str(self.reserved_unknown),
                "committed_usd_upper_bound": str(self.committed()), "ceiling_usd": str(self.limits.max_spend_usd), "remaining_usd_upper_bound": str(self.limits.max_spend_usd - self.committed()),
                "cost_basis": "calculated from the published price snapshot; the provider's billing dashboard may differ", "refusals": list(self.refusals),
                "latency_ms_p50": lat[len(lat) // 2] if lat else None, "latency_ms_max": lat[-1] if lat else None}


def make_guard_callback(budget: LiveBudget, model: str, recorder: "LiveRunRecorder | None" = None):
    """A LangChain callback handler that admits each chat-model call and settles it with the reported usage. Raises BudgetExceeded from inside the call to stop it."""
    from langchain_core.callbacks import BaseCallbackHandler

    class GuardCallback(BaseCallbackHandler):
        raise_error = True
        run_inline = True

        def __init__(self) -> None:
            self._open: dict[Any, tuple[Decimal, float]] = {}

        def _start(self, run_id: Any, text: str) -> None:
            reserved = budget.admit(model, estimate_input_tokens(text))
            self._open[run_id] = (reserved, time.perf_counter())

        def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):  # noqa: ANN001
            text = "\n".join(str(getattr(m, "content", m)) for batch in messages for m in batch)
            self._start(run_id, text)

        def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):  # noqa: ANN001
            self._start(run_id, "\n".join(prompts))

        def on_llm_end(self, response, *, run_id, **kwargs):  # noqa: ANN001
            reserved, began = self._open.pop(run_id, (Decimal(0), time.perf_counter()))
            tin = tout = None
            try:
                out = getattr(response, "llm_output", None) or {}
                usage = out.get("token_usage") if isinstance(out, dict) else None
                if isinstance(usage, dict):
                    tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if tin is None:
                    gens = getattr(response, "generations", None) or []
                    msg = getattr(gens[0][0], "message", None) if gens and gens[0] else None
                    meta = getattr(msg, "usage_metadata", None)
                    if isinstance(meta, dict):
                        tin, tout = meta.get("input_tokens"), meta.get("output_tokens")
            except Exception:  # noqa: BLE001 - unreadable usage is UNKNOWN, never zero
                tin = tout = None
            ms = int((time.perf_counter() - began) * 1000)
            budget.settle(model, reserved, input_tokens=tin, output_tokens=tout, ok=True, latency_ms=ms)
            if recorder:
                recorder.call(model=model, ok=True, input_tokens=tin, output_tokens=tout, latency_ms=ms)

        def on_llm_error(self, error, *, run_id, **kwargs):  # noqa: ANN001
            reserved, began = self._open.pop(run_id, (Decimal(0), time.perf_counter()))
            ms = int((time.perf_counter() - began) * 1000)
            budget.settle(model, reserved, input_tokens=None, output_tokens=None, ok=False, latency_ms=ms)
            if recorder:
                recorder.call(model=model, ok=False, input_tokens=None, output_tokens=None, latency_ms=ms, error=type(error).__name__)

    return GuardCallback()


def git_state() -> dict:
    def run(*a: str) -> str | None:
        try:
            return subprocess.check_output(["git", *a], cwd=ROOT, stderr=subprocess.DEVNULL, timeout=10).decode().strip()
        except Exception:  # noqa: BLE001
            return None
    sha = run("rev-parse", "HEAD")
    status = run("status", "--porcelain", "--untracked-files=no")
    return {"commit": sha, "checkout": "unknown" if status is None else ("dirty" if status else "clean")}


class LiveRunRecorder:
    """Append-only evidence for one live run in its own directory. Existing files are never overwritten. Secrets and raw provider payloads are never written."""

    def __init__(self, area: str, *, provider: str, model: str, profile: str, dataset_version: str | None = None, base: Path = LIVE_DIR) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"p10e-{area}-{stamp}-{secrets.token_hex(4)}"
        self.dir = base / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        self.meta = {"run_id": self.run_id, "area": area, "started_at": datetime.now(timezone.utc).isoformat(), "provider": provider, "model": model, "profile": profile,
                     "dataset_version": dataset_version, **git_state()}
        self._calls = self.dir / "calls.jsonl"
        self._write("meta.json", self.meta)

    def _write(self, name: str, obj: dict) -> None:
        with open(self.dir / name, "x", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, sort_keys=True)

    def call(self, **fields: Any) -> None:
        with open(self._calls, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(), **fields}, sort_keys=True) + "\n")

    def finish(self, summary: dict, results: dict | None = None) -> Path:
        self._write("summary.json", {**self.meta, "finished_at": datetime.now(timezone.utc).isoformat(), "budget": summary, "results": results})
        return self.dir
