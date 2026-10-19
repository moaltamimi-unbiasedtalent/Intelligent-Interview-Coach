"""P10E live-run guard: no paid provider request is possible without owner-approved, finite, CUMULATIVE limits and an explicitly enabled execution flag.

Layers (each independently enforced, none can bypass another):

1. ``require_live`` (authorization): the execution flag ``paid_execution_enabled`` must be the boolean ``true`` (missing, null, a string such as "true", 1 or false all mean REFUSED);
   the owner grant, approval metadata and EVERY required limit must be present, valid and listed as approved; spend above the owner-approved total is refused; not in CI; the explicit
   per-run opt-in ``P10E_LIVE=1``. The flag does not replace the owner checks and the owner checks do not replace the flag.
2. ``live_session`` (execution): additionally the data class must be allowed (synthetic only), the credential present, the designated environment's persistent ledger verified and
   the exclusive session lock held (``src/p10e/ledger.py``), and the HTTP guard installed (``src/p10e/httpguard.py``) so EVERY provider request, including nested agent calls,
   SDK retries and anything else that uses the HTTP client library, is admitted against the cumulative ledger before it is sent.
3. ``LiveBudget``: admission by worst-case cost and cumulative call count; unknown usage is never zero.

Nothing in this module makes a network call. A normal test run stays offline.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator

from src.p10e.errors import BudgetExceeded, LiveRunRefused

ROOT = Path(__file__).resolve().parents[2]
AUTH_PATH = ROOT / "evaluations" / "p10e" / "authorization.json"
PRICING_PATH = ROOT / "evaluations" / "p10e" / "pricing_snapshot.json"
LIVE_DIR = ROOT / "evaluations" / "p10e" / "live"
LEDGER_DIR_ENV = "P10E_LEDGER_DIR"

REQUIRED_LIMITS = ("max_spend_usd", "max_provider_calls", "max_input_tokens_per_request", "max_output_tokens_per_request", "request_timeout_s", "max_retries", "max_concurrency")
HARD_CAPS = {"max_retries": 2, "max_concurrency": 4}            # even an approved value cannot exceed these: "bounded retries, bounded concurrency"
CHARS_PER_TOKEN_PESSIMISTIC = 3                                 # fewer characters per token than typical text, so the input estimate errs high

__all__ = ["LiveRunRefused", "BudgetExceeded", "LiveLimits", "Authorization", "load_authorization", "require_live", "LiveBudget", "MemoryStore", "Reservation", "live_session", "LiveSession",
           "LiveRunRecorder", "load_prices", "estimate_input_tokens", "git_state", "in_ci"]


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
    execution_flag: Any                 # the raw JSON value: only the boolean True enables execution
    limits_raw: Any
    approved_by: str | None
    approval_date: str | None
    reference: str | None
    approves: tuple = ()
    spend_authority: dict = field(default_factory=dict)
    execution_environment: dict = field(default_factory=dict)
    allowed_data_classes: tuple = ()
    allowed_provider_hosts: tuple = ()
    raw: dict = field(default_factory=dict)

    @property
    def execution_enabled(self) -> bool:
        return self.execution_flag is True


def load_authorization(path: Path = AUTH_PATH) -> Authorization:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LiveRunRefused("authorization_missing", "The P10E authorization record is missing or unreadable.") from exc
    appr = raw.get("limits_approval") or {}
    return Authorization(owner_decision_date=str(raw.get("owner_decision_date", "")), paid_use_granted=(raw.get("granted") or {}).get("paid_provider_use_for_p10e") is True,
                         execution_flag=raw.get("paid_execution_enabled"), limits_raw=raw.get("limits"), approved_by=appr.get("approved_by"), approval_date=appr.get("approval_date"),
                         reference=appr.get("reference"), approves=tuple(appr.get("approves") or ()), spend_authority=dict(raw.get("spend_authority") or {}),
                         execution_environment=dict(raw.get("execution_environment") or {}), allowed_data_classes=tuple(raw.get("allowed_data_classes") or ()),
                         allowed_provider_hosts=tuple(raw.get("allowed_provider_hosts") or ()), raw=raw)


def in_ci(env: dict | None = None) -> bool:
    e = os.environ if env is None else env
    return any(str(e.get(k, "")).strip().lower() in ("1", "true", "yes") for k in ("CI", "GITHUB_ACTIONS"))


def require_live(auth: Authorization | None = None, *, env: dict | None = None, credential_names: tuple[str, ...] = ()) -> LiveLimits:
    """Authorization-level checks. Returns the approved limits or raises ``LiveRunRefused``. Reads credential PRESENCE only, never a value."""
    e = os.environ if env is None else env
    auth = auth or load_authorization()
    if in_ci(e):
        raise LiveRunRefused("ci_forbidden", "Paid provider calls never run in CI.")
    if str(e.get("P10E_LIVE", "")).strip() != "1":
        raise LiveRunRefused("opt_in_missing", "Paid execution needs the explicit opt-in P10E_LIVE=1 for this run.")
    if auth.execution_flag is not True:
        raise LiveRunRefused("execution_flag_disabled", "paid_execution_enabled is not the boolean true in the authorization record. Paid execution is refused.")
    if not auth.paid_use_granted or auth.owner_decision_date != "2026-10-19":
        raise LiveRunRefused("not_authorized", "The owner authorization for paid P10E provider use is not recorded.")
    if not (auth.approved_by and auth.approval_date and auth.reference):
        raise LiveRunRefused("limits_not_approved", "The spending and call limits have no recorded owner approval (approved_by, approval_date, reference).")
    unapproved = [k for k in REQUIRED_LIMITS if k not in auth.approves]
    if unapproved:
        raise LiveRunRefused("limits_not_approved", f"The owner has not approved these limits yet: {', '.join(unapproved)}.")
    limits = LiveLimits.parse(auth.limits_raw)
    try:
        total = Decimal(str(auth.spend_authority.get("approved_total_usd")))
    except Exception:  # noqa: BLE001
        raise LiveRunRefused("spend_authority_missing", "No approved total spend is recorded (spend_authority.approved_total_usd).") from None
    if not total.is_finite() or total <= 0:
        raise LiveRunRefused("spend_authority_missing", "The approved total spend is not a finite amount above zero.")
    if limits.max_spend_usd > total:
        raise LiveRunRefused("spend_above_approval", f"max_spend_usd ({limits.max_spend_usd}) is above the owner-approved total ({total}). Spending above it needs a separate owner approval.")
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
    return max(1, -(-len(text) // CHARS_PER_TOKEN_PESSIMISTIC))


# ------------------------------------------------------------------------------------------------------------------------------------- budget
@dataclass
class Reservation:
    seq: int
    model: str
    reserved_usd: Decimal
    input_estimate: int
    started: float = field(default_factory=time.perf_counter)


class MemoryStore:
    """In-memory cumulative accounting with the same semantics as the durable ledger (used by unit tests only; a live run always uses the ledger)."""

    def __init__(self, approved_total: Decimal | None = None, call_cap: int | None = None) -> None:
        self._lock = threading.Lock()
        self._rows: list[dict] = []
        self.approved_total, self.call_cap = approved_total, call_cap

    def reserve(self, *, run_id: str, area: str, model: str, reserved_usd: Decimal, call_units: int, max_usd: Decimal, max_calls: int) -> int:
        with self._lock:
            usd = sum((r["committed"] for r in self._rows), Decimal(0))
            calls = sum(r["units"] for r in self._rows)
            cap_usd = min(max_usd, self.approved_total) if self.approved_total is not None else max_usd
            cap_calls = min(max_calls, self.call_cap) if self.call_cap is not None else max_calls
            if calls + call_units > cap_calls:
                raise BudgetExceeded("call_limit", "The cumulative provider-call limit would be exceeded.")
            if usd + reserved_usd > cap_usd:
                raise BudgetExceeded("spend_ceiling", "This request could exceed the cumulative spending ceiling (worst case); it is refused.")
            self._rows.append({"seq": len(self._rows) + 1, "state": "reserved", "committed": reserved_usd, "units": call_units})
            return len(self._rows)

    def settle(self, seq: int, *, state: str, committed_usd: Decimal, **_: Any) -> None:
        with self._lock:
            r = self._rows[seq - 1]
            if r["state"] != "reserved":
                raise LiveRunRefused("ledger_corrupted", "A settlement referenced an entry that is not an open reservation.")
            r["state"], r["committed"] = state, committed_usd

    def snapshot(self) -> dict:
        with self._lock:
            return {"committed_usd": str(sum((r["committed"] for r in self._rows), Decimal(0))), "calls": sum(r["units"] for r in self._rows)}


class LiveBudget:
    """Admission and accounting for provider requests. Costs are Decimal USD estimates from the published price snapshot, not billed amounts. Each HTTP request is one admission,
    so an SDK retry is a separate, separately reserved and counted request."""

    def __init__(self, limits: LiveLimits, prices: dict[str, tuple[Decimal, Decimal]], store: Any | None = None, *, run_id: str = "run", area: str = "area") -> None:
        self.limits, self.prices, self.store, self.run_id, self.area = limits, prices, store or MemoryStore(), run_id, area
        self._lock = threading.Lock()
        self.admitted = self.completed = self.failed = self.rejected = self.unknown_usage = 0
        self.input_tokens_known = self.output_tokens_known = 0
        self.cost_known = Decimal(0)
        self.provider_cost_reported = Decimal(0)
        self.provider_cost_calls = 0
        self.latencies_ms: list[int] = []
        self.refusals: list[str] = []

    def _worst_case(self, model: str, input_tokens: int, max_output: int) -> Decimal:
        if model not in self.prices:
            raise BudgetExceeded("price_unknown", f"No published price for model '{model}', so the spending ceiling cannot be enforced. The call is refused.")
        pi, po = self.prices[model]
        return pi * input_tokens + po * max_output

    def admit(self, model: str, input_tokens: int, max_output_tokens: int | None = None) -> Reservation:
        out_cap = self.limits.max_output_tokens_per_request if max_output_tokens is None else max_output_tokens
        def refuse(reason: str, msg: str):
            with self._lock:
                self.refusals.append(reason)
            raise BudgetExceeded(reason, msg)
        if input_tokens > self.limits.max_input_tokens_per_request:
            refuse("request_too_large", f"Estimated input of {input_tokens} tokens exceeds the approved per-request limit.")
        if out_cap > self.limits.max_output_tokens_per_request:
            refuse("output_cap_exceeds_limit", "The requested output cap exceeds the approved per-request limit.")
        try:
            worst = self._worst_case(model, input_tokens, out_cap)
        except BudgetExceeded as exc:
            refuse(exc.reason, str(exc))
        try:
            seq = self.store.reserve(run_id=self.run_id, area=self.area, model=model, reserved_usd=worst, call_units=1, max_usd=self.limits.max_spend_usd, max_calls=self.limits.max_provider_calls)
        except BudgetExceeded as exc:
            refuse(exc.reason, str(exc))
        with self._lock:
            self.admitted += 1
        return Reservation(seq=seq, model=model, reserved_usd=worst, input_estimate=input_tokens)

    def settle(self, res: Reservation, *, outcome: str, input_tokens: int | None = None, output_tokens: int | None = None, provider_cost: Decimal | None = None,
               status_code: int | None = None, latency_ms: int | None = None, note: str | None = None) -> Decimal:
        """outcome: ``ok`` (a response arrived), ``rejected`` (the provider answered with a definitive rejection that ran no inference: the dollar reservation is released, the request still
        counts as a call) or ``unknown`` (timeout, connection loss, server error, cancellation: potentially billable, kept at the FULL worst case). Returns the committed dollars."""
        if outcome not in ("ok", "rejected", "unknown"):
            raise ValueError("invalid outcome")
        state, committed = "settled_unknown", res.reserved_usd
        if outcome == "rejected":
            state, committed = "rejected", Decimal(0)
        elif outcome == "ok" and input_tokens is not None and output_tokens is not None and res.model in self.prices:
            pi, po = self.prices[res.model]
            calc = pi * int(input_tokens) + po * int(output_tokens)
            committed = max(calc, provider_cost) if provider_cost is not None else calc     # the larger of the calculated and the provider-reported figure
            state = "settled_known"
        self.store.settle(res.seq, state=state, committed_usd=committed, input_tokens=input_tokens, output_tokens=output_tokens, provider_cost_usd=provider_cost, status_code=status_code, note=note)
        with self._lock:
            if outcome == "ok":
                self.completed += 1
            elif outcome == "rejected":
                self.rejected += 1
            else:
                self.failed += 1
            if latency_ms is not None:
                self.latencies_ms.append(latency_ms)
            if state == "settled_known":
                self.input_tokens_known += int(input_tokens)
                self.output_tokens_known += int(output_tokens)
                self.cost_known += committed
                if provider_cost is not None:
                    self.provider_cost_reported += provider_cost
                    self.provider_cost_calls += 1
            elif outcome != "rejected":
                self.unknown_usage += 1
        return committed

    def summary(self) -> dict:
        lat = sorted(self.latencies_ms)
        snap = self.store.snapshot() if hasattr(self.store, "snapshot") else {}
        return {"run_calls_admitted": self.admitted, "run_calls_completed": self.completed, "run_calls_failed_or_unknown": self.failed, "run_calls_rejected_by_provider": self.rejected,
                "run_calls_with_unknown_usage": self.unknown_usage, "run_input_tokens_known": self.input_tokens_known, "run_output_tokens_known": self.output_tokens_known,
                "run_total_tokens_known": self.input_tokens_known + self.output_tokens_known, "run_cost_known_usd_estimate": str(self.cost_known),
                "run_provider_reported_cost_usd": str(self.provider_cost_reported) if self.provider_cost_calls else "UNKNOWN", "run_provider_reported_cost_calls": self.provider_cost_calls,
                "cumulative": snap, "ceiling_usd": str(self.limits.max_spend_usd), "call_limit": self.limits.max_provider_calls,
                "cost_basis": "calculated from the published price snapshot (or the larger provider-reported figure); the provider's billing dashboard may differ", "refusals": list(self.refusals),
                "latency_ms_p50": lat[len(lat) // 2] if lat else None, "latency_ms_max": lat[-1] if lat else None}


# ------------------------------------------------------------------------------------------------------------------------------------- evidence
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

    def __init__(self, area: str, *, provider: str, model: str, profile: str, dataset_version: str | None = None, base: Path = LIVE_DIR, extra: dict | None = None) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"p10e-{area}-{stamp}-{secrets.token_hex(4)}"
        self.dir = base / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        self.meta = {"run_id": self.run_id, "area": area, "started_at": datetime.now(timezone.utc).isoformat(), "provider": provider, "model": model, "profile": profile,
                     "dataset_version": dataset_version, **git_state(), **(extra or {})}
        self._calls = self.dir / "calls.jsonl"
        self._write("meta.json", self.meta)

    def _write(self, name: str, obj: dict) -> None:
        with open(self.dir / name, "x", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, sort_keys=True)

    def call(self, **fields: Any) -> None:
        with open(self._calls, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(), **fields}, sort_keys=True, default=str) + "\n")

    def finish(self, summary: dict, results: dict | None = None) -> Path:
        self._write("summary.json", {**self.meta, "finished_at": datetime.now(timezone.utc).isoformat(), "budget": summary, "results": results})
        return self.dir


# ------------------------------------------------------------------------------------------------------------------------------------- the live session
@dataclass
class LiveSession:
    limits: LiveLimits
    budget: LiveBudget
    ledger: Any
    auth: Authorization
    run_id: str
    area: str
    http_guard: Any = None

    def evidence_refs(self) -> dict:
        ee = self.auth.execution_environment
        return {"authorization_version": self.auth.raw.get("authorization_version"), "execution_flag": self.auth.execution_flag, "environment_id": ee.get("environment_id"),
                "ledger_genesis_id": self.ledger.meta.get("genesis_id") if self.ledger is not None else None, "ledger_session_id": getattr(self.ledger, "session_id", None)}


@contextmanager
def live_session(area: str, data_class: str, *, env: dict | None = None, auth: Authorization | None = None, credential_check: Callable[[], bool] | None = None,
                 credential_names: tuple[str, ...] = (), prices: dict | None = None, ledger_dir: Path | None = None, repo_root: Path | None = None,
                 install_http_guard: bool = True) -> Iterator[LiveSession]:
    """Every precondition for paid execution, then the exclusive session. The yielded session owns the durable ledger lock until the block exits."""
    from src.p10e import ledger as L

    e = os.environ if env is None else env
    auth = auth or load_authorization()
    limits = require_live(auth, env=e, credential_names=credential_names)
    if credential_check is not None and not credential_check():
        raise LiveRunRefused("credential_missing", "The required provider credential is not configured.")
    if data_class not in auth.allowed_data_classes:
        raise LiveRunRefused("data_class_not_allowed", f"Data class '{data_class}' is not allowed for P10E (synthetic fixtures only).")
    if not auth.allowed_provider_hosts:
        raise LiveRunRefused("provider_hosts_missing", "No allowed provider host is recorded.")
    raw_dir = ledger_dir if ledger_dir is not None else (Path(e[LEDGER_DIR_ENV]) if str(e.get(LEDGER_DIR_ENV, "")).strip() else None)
    if raw_dir is None:
        raise LiveRunRefused("ledger_location_missing", f"The persistent ledger location must be configured explicitly ({LEDGER_DIR_ENV}); there is no default and none is created.")
    ee = auth.execution_environment
    kw = {"repo_root": repo_root} if repo_root is not None else {}
    ledger = L.Ledger.open(raw_dir, expected_genesis=ee.get("ledger_genesis_id"), environment_id=ee.get("environment_id"), **kw)
    guard = None
    try:
        if ee.get("host_fingerprint_sha256") != L.host_fingerprint():
            raise LiveRunRefused("ledger_wrong_host", "This host is not the designated P10E execution host recorded in the authorization.")
        run_id = f"p10e-{area}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"
        budget = LiveBudget(limits, prices or load_prices(), ledger, run_id=run_id, area=area)
        session = LiveSession(limits=limits, budget=budget, ledger=ledger, auth=auth, run_id=run_id, area=area)
        if install_http_guard:
            from src.p10e.httpguard import HttpGuard
            guard = HttpGuard(budget, limits, allowed_hosts=auth.allowed_provider_hosts)
            guard.install()
            session.http_guard = guard
        yield session
    finally:
        if guard is not None:
            guard.uninstall()
        ledger.close()
