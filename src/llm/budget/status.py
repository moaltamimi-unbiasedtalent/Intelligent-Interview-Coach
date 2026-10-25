"""Read-only AI budget status for Admin (05C). Counts, money headroom and state only: no key, no marker value, no prompt text, no model response, no user identifier.

``budget_status`` is derived per request from the configuration file, the ledger and the process environment (never a provider call). It never raises: any problem is reported as a
``closed``/``unavailable`` state with a fixed reason, because an unreadable budget must never look healthy.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from sqlalchemy.exc import SQLAlchemyError

from src.llm.budget import governor as G
from src.llm.budget.config import KILL_ENV, MARKER_ENV, MODE_ENV, load_config, resolve_budget_class, require_approved_marker, validate_hosted_approval
from src.llm.budget.errors import BudgetError
from src.llm.budget.ledger import DbBudgetLedger

NOTE = ("All money figures are estimates from the configured price table and reported usage, held conservatively; they are not confirmed provider charges. "
        "Unknown outcomes stay held at their worst case. Unknown token and cost figures are shown as null, never zero.")


def budget_status(session_factory, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    enforcing = (env.get(MODE_ENV) or "").strip().lower() == "enforce"
    installed = G.active_governor()
    out: dict[str, Any] = {
        "state": "unavailable", "reason": None, "enforcement": "enforcing" if (enforcing and installed is not None and installed.is_open) else ("closed" if installed is not None else "not_enforcing"),
        "budget_class": None, "config_loaded": False, "approval_marker_configured": False, "approval_marker_presented": bool((env.get(MARKER_ENV) or "").strip()),
        "env_kill_switch": (env.get(KILL_ENV) or "").strip().lower() in ("1", "true", "yes"), "ledger": None, "note": NOTE,
    }
    try:
        klass = resolve_budget_class(env)
        out["budget_class"] = klass
        cfg = load_config(environ=env)
    except BudgetError as exc:
        out["reason"] = exc.reason
        return out
    out["config_loaded"] = True
    out["approval_marker_configured"] = bool(cfg.approval_marker)
    if klass not in cfg.classes:
        out["reason"] = "class_not_configured"
        return out
    out["limits"] = {"max_input_tokens": cfg.limits.max_input_tokens, "max_output_tokens": cfg.limits.max_output_tokens, "request_timeout_s": cfg.limits.request_timeout_s,
                     "max_retries": cfg.limits.max_retries, "max_concurrency": cfg.limits.max_concurrency}
    out["priced_models"] = len(cfg.pricing)
    try:
        ledger = DbBudgetLedger(session_factory)
        ledger.ensure_ready()
        snap = ledger.snapshot(cfg, klass)
        snap["integrity"] = ledger.integrity(klass)
    except (BudgetError, SQLAlchemyError) as exc:
        out["reason"] = getattr(exc, "reason", "ledger_unavailable")
        return out
    out["ledger"] = snap
    try:
        require_approved_marker(cfg, env)
        validate_hosted_approval(cfg, env)
    except BudgetError as exc:
        out.update(state="not_approved", reason=exc.reason)
        return out
    if installed is not None and installed.is_open and (installed.config.raw_hash != cfg.raw_hash or installed.budget_class != klass):
        out.update(state="unavailable", reason="policy_mismatch")
        return out
    if installed is None or not installed.is_open:
        out.update(state="closed", reason=installed.closed_reason if installed else "enforcement_required")
        return out
    stopped = snap["remaining_requests"] == 0 or float(snap["remaining_to_stop_usd"]) == 0.0
    if snap["killed"] or out["env_kill_switch"]:
        out["state"] = "killed"
    elif not snap["integrity"]["consistent"]:
        out["state"] = "unavailable"
        out["reason"] = "ledger_inconsistent"
    elif stopped:
        out["state"] = "stopped"
    elif not (out["approval_marker_configured"] and out["approval_marker_presented"]):
        out["state"] = "not_approved"
    else:
        out["state"] = "open"
    return out
