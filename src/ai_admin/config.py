"""AI configuration schema, canonical form, hash and deterministic validation (P10B-W10.7).

A configuration changes exactly two things and nothing else:

* ``profiles``: which APPROVED CATALOGUE entry (by id) each Fast/Balanced/Advanced profile resolves to; and
* ``operations``: bounded numeric tunables (``max_output_tokens``, ``timeout_s``, ``max_retries``) for model-backed operations.

Everything else (an operation's capability, minimum tier, fallback floor, structured-output and tool flags, temperature, the deterministic
and realtime operations, the three specialists, the Interview session profile, prompts, secrets) is code-defined and cannot appear here:
unknown keys are rejected, never ignored. The canonical form is fully expanded (defaults filled in), so two configurations that mean the same
thing hash the same, and the hash covers the catalogue version so a catalogue change can never silently re-attribute an old hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from src.ai_admin import catalogue as C
from src.llm.models import ModelProfile
from src.llm.policy import OPERATION_POLICY, ModelCapability, ModelOperation, _TIER_ORDER, _clamp_up, _fallback_chain

SCHEMA_VERSION = 1
TUNABLES: dict[str, tuple[float, float, bool]] = {          # field -> (min, max, integer?)
    "max_output_tokens": (256, 4096, True),
    "timeout_s": (10, 180, False),
    "max_retries": (0, 3, True),
}
MAX_TOTAL_BUDGET_S = 600.0     # timeout * (retries + 1): one operation may not hold a request longer than this
_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


class ConfigError(ValueError):
    """The submitted configuration is not well formed. The message never echoes submitted values."""


# Only operations with a REAL, distinct runtime consumer are tunable (see src/llm/runtime.py for the consumer of each). Specialist coaching has no
# shipped model call path (a deterministic fallback owns it); the role specialist shares the structured-generation producer; the final response is
# produced by the orchestration model itself. A setting with no consumer would be cosmetic, so those operations are not configurable.
TUNABLE_OPERATIONS: tuple[ModelOperation, ...] = (ModelOperation.ORCHESTRATION, ModelOperation.STRUCTURED_GENERATION, ModelOperation.EVALUATION)


def tunable_operations() -> list[ModelOperation]:
    return list(TUNABLE_OPERATIONS)


def model_backed_operations() -> list[ModelOperation]:
    return [op for op, p in OPERATION_POLICY.items() if p.capability not in (ModelCapability.NONE, ModelCapability.REALTIME)]


def baseline_config() -> dict:
    """The configuration equivalent to the code as shipped (profiles from the registry defaults, tunables from the code policy)."""
    return {
        "schema": SCHEMA_VERSION,
        "profiles": dict(C.BASELINE_PROFILES),
        "operations": {op.value: {"max_output_tokens": OPERATION_POLICY[op].max_output_tokens,
                                  "timeout_s": float(OPERATION_POLICY[op].timeout_s),
                                  "max_retries": OPERATION_POLICY[op].max_retries} for op in tunable_operations()},
    }


def _number(value: Any, field: str, integer: bool) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"A {field.replace('_', ' ')} value must be a number.")
    if integer:
        if isinstance(value, float) and not value.is_integer():
            raise ConfigError(f"A {field.replace('_', ' ')} value must be a whole number.")
        return int(value)
    return float(value)


def normalise(raw: Any) -> dict:
    """Return the canonical, fully expanded configuration or raise ``ConfigError``. Unknown keys are an error."""
    if not isinstance(raw, dict):
        raise ConfigError("The configuration must be an object.")
    extra = set(raw) - {"schema", "profiles", "operations"}
    if extra:
        raise ConfigError("The configuration has fields that are not part of the schema.")
    if raw.get("schema", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ConfigError("The configuration schema version is not supported.")
    base = baseline_config()
    profiles_in = raw.get("profiles", base["profiles"])
    if not isinstance(profiles_in, dict) or set(profiles_in) != {p.value for p in ModelProfile}:
        raise ConfigError("Assign exactly the three profiles: fast, balanced and advanced.")
    profiles: dict[str, str] = {}
    for key, value in profiles_in.items():
        if not isinstance(value, str) or not _ID.match(value):
            raise ConfigError("A profile must be assigned a catalogue entry id.")
        profiles[key] = value
    ops_in = raw.get("operations", {})
    if not isinstance(ops_in, dict):
        raise ConfigError("Operation settings must be an object.")
    allowed = {op.value for op in tunable_operations()}
    if set(ops_in) - allowed:
        raise ConfigError("Only operations with a runtime consumer can be tuned; code-defined, deterministic, realtime and consumer-less operations cannot.")
    ops: dict[str, dict] = {}
    for name in sorted(allowed):
        merged = dict(base["operations"][name])
        given = ops_in.get(name, {})
        if not isinstance(given, dict) or set(given) - set(TUNABLES):
            raise ConfigError("An operation can only set max output tokens, timeout and retries.")
        for field, value in given.items():
            merged[field] = _number(value, field, TUNABLES[field][2])
        merged["max_output_tokens"] = int(merged["max_output_tokens"])
        merged["max_retries"] = int(merged["max_retries"])
        merged["timeout_s"] = float(merged["timeout_s"])
        ops[name] = merged
    return {"schema": SCHEMA_VERSION, "profiles": {p.value: profiles[p.value] for p in ModelProfile}, "operations": ops}


def config_hash(canonical: dict, catalogue_version: str = C.CATALOGUE_VERSION) -> str:
    """SHA-256 over the canonical JSON plus the catalogue version. Stable across key order and number spelling."""
    body = json.dumps({"catalogue": catalogue_version, "config": canonical}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("ascii")).hexdigest()


def diff_from_baseline(canonical: dict) -> list[dict]:
    """Human-readable list of every field that differs from the code baseline."""
    base = baseline_config()
    out: list[dict] = []
    for p in ModelProfile:
        if canonical["profiles"][p.value] != base["profiles"][p.value]:
            out.append({"field": f"profile.{p.value}", "baseline": base["profiles"][p.value], "value": canonical["profiles"][p.value]})
    for name, tun in canonical["operations"].items():
        for f, v in tun.items():
            if v != base["operations"][name][f]:
                out.append({"field": f"operation.{name}.{f}", "baseline": base["operations"][name][f], "value": v})
    return out


@dataclass(frozen=True)
class Check:
    code: str
    label: str
    passed: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"code": self.code, "label": self.label, "passed": self.passed, "detail": self.detail}


def _entry(canonical: dict, profile: ModelProfile):
    return C.CATALOGUE.get(canonical["profiles"][profile.value])


def _has_slug_like(node: Any) -> bool:
    if isinstance(node, str):
        return "/" in node or ":" in node or "." in node
    if isinstance(node, dict):
        return any(_has_slug_like(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_slug_like(v) for v in node)
    return False


def validate(canonical: dict) -> list[Check]:
    """Deterministic, offline validation of a canonical configuration. Returns every check (passed or not)."""
    checks: list[Check] = []

    def add(code: str, label: str, ok: bool, detail: str = "") -> None:
        checks.append(Check(code, label, bool(ok), "" if ok else detail))

    known = all(canonical["profiles"][p.value] in C.CATALOGUE for p in ModelProfile)
    add("catalogue_membership", "Every profile uses an approved catalogue entry", known, "A profile references an entry that is not in the approved catalogue.")
    add("no_raw_provider_slug", "No raw provider model slug appears anywhere", not _has_slug_like(canonical),
        "A value looks like a provider slug. Choose catalogue entries by id.")
    if not known:
        return checks
    allowed = all(p in _entry(canonical, p).allowed_profiles for p in ModelProfile)
    add("profile_allowed", "Each entry is permitted for the profile it serves", allowed, "An entry is assigned to a profile it is not approved for.")
    ranks = [C.TIER_RANK[_entry(canonical, p).tier] for p in (ModelProfile.FAST, ModelProfile.BALANCED, ModelProfile.ADVANCED)]
    add("tier_monotonic", "Fast <= Balanced <= Advanced in capability tier", ranks == sorted(ranks), "A lower profile is assigned a more capable tier than a higher one.")
    costs = [_entry(canonical, p).cost_class for p in ModelProfile]
    add("cost_ordering", "Cost class never decreases from Fast to Advanced", costs == sorted(costs), "A cheaper profile uses a costlier model than a higher profile.")

    bounds_ok, budget_ok, detail_b, detail_t = True, True, "", ""
    for name, tun in canonical["operations"].items():
        for field, (lo, hi, _i) in TUNABLES.items():
            if not lo <= tun[field] <= hi:
                bounds_ok, detail_b = False, f"{name}: {field.replace('_', ' ')} is outside {lo:g} to {hi:g}."
        if tun["timeout_s"] * (tun["max_retries"] + 1) > MAX_TOTAL_BUDGET_S:
            budget_ok, detail_t = False, f"{name}: timeout x (retries + 1) exceeds {MAX_TOTAL_BUDGET_S:g} seconds."
    add("tunable_bounds", "Every tunable is inside its code-defined bounds", bounds_ok, detail_b)
    add("time_budget", "No operation can hold a request beyond the total time budget", budget_ok, detail_t)

    cap_ok, floor_ok, d_cap, d_floor = True, True, "", ""
    for op in model_backed_operations():
        policy = OPERATION_POLICY[op]
        for user in ModelProfile:
            effective, _ = _clamp_up(user, policy.min_capability)
            entry = _entry(canonical, effective)
            if (policy.requires_tools and not entry.supports_tools) or (policy.structured_output and not entry.supports_structured_output):
                cap_ok, d_cap = False, f"{op.value}: the model serving {effective.value} lacks a required capability."
            if _TIER_ORDER[effective] < _TIER_ORDER[policy.min_capability]:
                floor_ok, d_floor = False, f"{op.value}: resolves below its minimum capability."
            for fb in _fallback_chain(effective, policy.fallback_floor):
                if _TIER_ORDER[fb] < _TIER_ORDER[policy.fallback_floor]:
                    floor_ok, d_floor = False, f"{op.value}: a fallback drops below its floor."
    add("capability_support", "Every model-backed operation keeps tool and structured-output support", cap_ok, d_cap)
    add("floors_preserved", "Operation minimum tiers and fallback floors hold for every profile", floor_ok, d_floor)
    add("code_defined_untouched", "Deterministic and realtime operations are not configurable",
        not ({o.value for o in ModelOperation if OPERATION_POLICY[o].capability in (ModelCapability.NONE, ModelCapability.REALTIME)} & set(canonical["operations"])),
        "A deterministic or realtime operation appears in the configuration.")
    return checks


def passed(checks: list[Check]) -> bool:
    return bool(checks) and all(c.passed for c in checks)
