"""Configuration of the production AI budget governor (05C).

Everything that decides how much may be spent is CONFIGURATION, never a code constant and never invented here: ceilings per budget class (development, evaluation, production) and per
category (agent, interview, embedding, evaluation), each with a HARD CAP and a lower STOP threshold, the per-request limits, the model price table and the owner's approved-budget
marker. The repository ships no values: ``AI_BUDGET_CONFIG_PATH`` names a JSON file the owner provides. A missing or invalid file fails CLOSED (every paid call is refused).

Money is integer micro-USD (rounded UP, so we never under-count). Pricing is USD per token, as the provider publishes it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Mapping

from src.llm.budget.errors import BudgetError

MICRO = Decimal(1_000_000)
BUDGET_CLASSES = ("development", "evaluation", "production")
CATEGORIES = ("agent", "interview", "embedding", "evaluation")
CONFIG_PATH_ENV = "AI_BUDGET_CONFIG_PATH"
MODE_ENV = "AI_BUDGET_MODE"                    # "enforce" installs the chokepoint; anything else (or unset) leaves provider behaviour unchanged
CLASS_ENV = "AI_BUDGET_CLASS"
MARKER_ENV = "AI_BUDGET_APPROVED_MARKER"
KILL_ENV = "AI_BUDGET_KILL"
DEFAULT_HOSTS = ("openrouter.ai",)
_MARKER_RE = re.compile(r"^OD-BUDGET:[A-Za-z0-9._-]{4,64}$")
LOCAL_ENVIRONMENTS = ("development", "dev", "local", "test", "testing")


def usd_to_micro(value: str | int | float | Decimal) -> int:
    d = Decimal(str(value))
    if d < 0:
        raise ValueError("negative amount")
    return int((d * MICRO).to_integral_value(rounding=ROUND_CEILING))


def micro_to_usd(micro: int | None) -> str | None:
    return None if micro is None else f"{Decimal(micro) / MICRO:.6f}"


@dataclass(frozen=True)
class Ceiling:
    hard_cap: int            # micro-USD, never reachable by normal operation
    stop: int                # micro-USD, admission stops here (stop <= hard_cap)


@dataclass(frozen=True)
class ClassBudget:
    ceiling: Ceiling
    max_requests: int
    categories: Mapping[str, Ceiling]


@dataclass(frozen=True)
class Limits:
    max_input_tokens: int
    max_output_tokens: int
    request_timeout_s: int
    max_retries: int
    max_concurrency: int
    dedupe_window_s: int = 300


@dataclass(frozen=True)
class Price:
    prompt: Decimal          # USD per input token
    completion: Decimal      # USD per output token


@dataclass(frozen=True)
class BudgetConfig:
    classes: Mapping[str, ClassBudget]
    limits: Limits
    pricing: Mapping[str, Price]
    approval_marker: str | None
    hosts: tuple[str, ...] = DEFAULT_HOSTS
    raw_hash: str = field(default="", compare=False)


def _ceiling(raw: dict, where: str) -> Ceiling:
    try:
        hard, stop = usd_to_micro(raw["hard_cap_usd"]), usd_to_micro(raw["stop_usd"])
    except (KeyError, ValueError, TypeError, ArithmeticError):
        raise BudgetError("config_invalid", f"The {where} ceiling needs hard_cap_usd and stop_usd (non-negative amounts).") from None
    if hard <= 0 or stop <= 0 or stop > hard:
        raise BudgetError("config_invalid", f"The {where} ceiling must satisfy 0 < stop_usd <= hard_cap_usd.")
    return Ceiling(hard_cap=hard, stop=stop)


def parse_config(raw: dict) -> BudgetConfig:
    try:
        lim = raw["limits"]
        limits = Limits(int(lim["max_input_tokens"]), int(lim["max_output_tokens"]), int(lim["request_timeout_s"]), int(lim["max_retries"]),
                        int(lim["max_concurrency"]), int(lim.get("dedupe_window_s", 300)))
        pricing = {m: Price(Decimal(str(p["prompt"])), Decimal(str(p["completion"]))) for m, p in raw["pricing"]["models"].items()}
        classes_raw = raw["classes"]
    except (KeyError, ValueError, TypeError, ArithmeticError, AttributeError):
        raise BudgetError("config_invalid", "The budget configuration is missing a required section or has an invalid value.") from None
    if min(limits.max_input_tokens, limits.max_output_tokens, limits.request_timeout_s, limits.max_concurrency) <= 0 or limits.max_retries < 0 or limits.dedupe_window_s < 0:
        raise BudgetError("config_invalid", "The per-request limits must be positive (retries and the dedupe window may be 0).")
    if not pricing or any(p.prompt < 0 or p.completion < 0 for p in pricing.values()):
        raise BudgetError("config_invalid", "The price table is empty or has a negative price.")
    classes: dict[str, ClassBudget] = {}
    for name, c in classes_raw.items():
        if name not in BUDGET_CLASSES:
            raise BudgetError("config_invalid", f"Unknown budget class {name!r}.")
        try:
            top = _ceiling(c, f"class {name}")
            max_requests = int(c["max_requests"])
            cats = {k: _ceiling(v, f"category {name}/{k}") for k, v in c.get("categories", {}).items()}
        except (KeyError, ValueError, TypeError, AttributeError):
            raise BudgetError("config_invalid", f"The class {name} section is invalid.") from None
        if max_requests <= 0:
            raise BudgetError("config_invalid", f"The class {name} request cap must be positive.")
        for k, v in cats.items():
            if k not in CATEGORIES:
                raise BudgetError("config_invalid", f"Unknown budget category {k!r}.")
            if v.hard_cap > top.hard_cap or v.stop > top.stop:
                raise BudgetError("config_invalid", f"The {name}/{k} ceiling exceeds its class ceiling.")
        classes[name] = ClassBudget(top, max_requests, cats)
    if not classes:
        raise BudgetError("config_invalid", "No budget class is configured.")
    marker = raw.get("approval_marker")
    if marker is not None and not (isinstance(marker, str) and _MARKER_RE.match(marker)):
        raise BudgetError("config_invalid", "approval_marker must look like OD-BUDGET:<reference>.")
    hosts = tuple(str(h).lower() for h in raw.get("allowed_provider_hosts", DEFAULT_HOSTS))
    return BudgetConfig(classes=classes, limits=limits, pricing=pricing, approval_marker=marker, hosts=hosts,
                        raw_hash=hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest())


def load_config(path: str | os.PathLike | None = None, environ: Mapping[str, str] | None = None) -> BudgetConfig:
    env = os.environ if environ is None else environ
    p = path or env.get(CONFIG_PATH_ENV)
    if not p:
        raise BudgetError("config_unavailable", f"No budget configuration: {CONFIG_PATH_ENV} is not set. Paid calls are refused (fail closed).")
    try:
        raw = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BudgetError("config_unavailable", "The budget configuration file is missing or unreadable. Paid calls are refused (fail closed).") from None
    if not isinstance(raw, dict):
        raise BudgetError("config_invalid", "The budget configuration must be a JSON object.")
    return parse_config(raw)


def resolve_budget_class(environ: Mapping[str, str] | None = None) -> str:
    """The class this process spends from: ``AI_BUDGET_CLASS`` when set (must be a known class), else production for hosted environments and development otherwise."""
    env = os.environ if environ is None else environ
    explicit = (env.get(CLASS_ENV) or "").strip().lower()
    if explicit:
        if explicit not in BUDGET_CLASSES:
            raise BudgetError("class_invalid", f"{CLASS_ENV} must be one of {', '.join(BUDGET_CLASSES)}.")
        return explicit
    api_env = (env.get("API_ENV") or "development").strip().lower()
    return "development" if api_env in LOCAL_ENVIRONMENTS else "production"


def require_approved_marker(config: BudgetConfig, environ: Mapping[str, str] | None = None) -> None:
    """Every paid path needs the approved-budget marker. The owner defines the value in the configuration (``approval_marker``); the process must present exactly that value in
    ``AI_BUDGET_APPROVED_MARKER``. Neither this repository, CI nor an agent defines or sets it. Raises ``BudgetError`` with fixed codes only (never either value)."""
    env = os.environ if environ is None else environ
    given = (env.get(MARKER_ENV) or "").strip()
    if not config.approval_marker:
        raise BudgetError("marker_not_configured", "The budget configuration defines no approval_marker, so no paid run is approved.")
    if not given:
        raise BudgetError("marker_missing", f"{MARKER_ENV} is not set; this paid path needs the owner's approved-budget marker.")
    if not hmac.compare_digest(given.encode(), config.approval_marker.encode()):
        raise BudgetError("marker_mismatch", f"{MARKER_ENV} does not match the configured approval marker.")
