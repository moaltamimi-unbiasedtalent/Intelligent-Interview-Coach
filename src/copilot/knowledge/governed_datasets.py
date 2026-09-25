"""Governed curated datasets K1–K4 (Capstone P6) — bounded, reviewed, abstention-first.

These close the K1–K4 knowledge requirements as small, COMMITTED, reviewed datasets
(under ``data/knowledge/governed/``) with strict, deterministic access:

- **K1** German occupation compensation — declared occupation set with provenance
  (authority, reference year, pay unit, currency); ABSTAINS outside the set (never
  invents a salary).
- **K2** Credentials / regulated professions — declared profession/jurisdiction matrix
  differentiating REQUIRED vs PREFERRED credentials with official lineage + dates;
  abstains outside coverage.
- **K3** Emerging roles / aliases — versioned alias → canonical map that only applies on
  a confident, unambiguous match (never overrides existing resolution).
- **K4** Additional Adzuna capabilities — an allow-listed set of entitled operations with
  strict parameter bounds and a safe-output shape; validation is deterministic and makes
  NO live provider call (live validation UNVALIDATED, cost-gated).

Everything here is deterministic and offline: no model, no network, no secret. All
figures are engineering-draft pending human data review — the delivered capability is the
governance mechanism (provenance, pay units, abstention, no-invention, bounds), not a
claim that the numbers are authority-verified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

GOVERNED_DIR = Path("data/knowledge/governed")

K1_PATH = GOVERNED_DIR / "k1_de_compensation.json"
K2_PATH = GOVERNED_DIR / "k2_credentials.json"
K3_PATH = GOVERNED_DIR / "k3_role_aliases.json"
K4_PATH = GOVERNED_DIR / "k4_adzuna_capabilities.json"

__all__ = [
    "load_dataset", "governed_dataset_summaries",
    "lookup_compensation", "CompensationResult",
    "lookup_credentials", "CredentialResult",
    "resolve_alias", "AliasResult",
    "validate_adzuna_operation", "AdzunaValidation",
]


def load_dataset(path: Path) -> dict:
    """Load one governed dataset JSON (empty dict if absent/malformed — never raises)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a missing governed dataset degrades safely
        return {}


@lru_cache(maxsize=8)
def _cached(path_str: str) -> dict:
    return load_dataset(Path(path_str))


def _k1() -> dict:
    return _cached(str(K1_PATH))


def _k2() -> dict:
    return _cached(str(K2_PATH))


def _k3() -> dict:
    return _cached(str(K3_PATH))


def _k4() -> dict:
    return _cached(str(K4_PATH))


def _norm(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


# --- K1: German occupation compensation --------------------------------------


@dataclass
class CompensationResult:
    covered: bool
    abstained: bool
    occupation_id: str | None = None
    title_en: str | None = None
    currency: str | None = None
    pay_unit: str | None = None
    median: int | None = None
    range: list[int] | None = None
    reference_year: int | None = None
    source_authority: str | None = None
    jurisdiction: str | None = None
    reason: str | None = None


def lookup_compensation(query: str, *, jurisdiction: str = "DE") -> CompensationResult:
    """Look up declared German occupation compensation, ABSTAINING outside the set.

    Matching is by occupation_id, English or German title (exact, case-insensitive) —
    deliberately conservative: an unmatched or out-of-jurisdiction query abstains with a
    reason and NO invented salary.
    """
    data = _k1()
    if not data or (jurisdiction or "").upper() != (data.get("jurisdiction") or "DE").upper():
        return CompensationResult(covered=False, abstained=True,
                                  reason="No governed compensation coverage for this jurisdiction.")
    q = _norm(query)
    for occ in data.get("occupations", []):
        candidates = {_norm(occ.get("occupation_id")), _norm(occ.get("title_en")), _norm(occ.get("title_de"))}
        if q in {c for c in candidates if c}:
            return CompensationResult(
                covered=True, abstained=False,
                occupation_id=occ.get("occupation_id"), title_en=occ.get("title_en"),
                currency=data.get("currency"), pay_unit=data.get("pay_unit"),
                median=occ.get("median_gross_annual_eur"),
                range=occ.get("range_gross_annual_eur"),
                reference_year=occ.get("reference_year") or data.get("reference_year"),
                source_authority=occ.get("source_authority") or data.get("authority"),
                jurisdiction=data.get("jurisdiction"),
            )
    return CompensationResult(covered=False, abstained=True,
                             reason="This occupation is outside the declared German compensation set.")


# --- K2: credentials / regulated professions ---------------------------------


@dataclass
class CredentialResult:
    covered: bool
    abstained: bool
    profession_id: str | None = None
    title: str | None = None
    jurisdiction: str | None = None
    regulated: bool | None = None
    required: list[dict] = field(default_factory=list)
    preferred: list[dict] = field(default_factory=list)
    source_url: str | None = None
    reason: str | None = None


def lookup_credentials(profession: str, *, jurisdiction: str) -> CredentialResult:
    """Look up declared credential requirements, ABSTAINING outside the matrix."""
    data = _k2()
    q = _norm(profession)
    juris = (jurisdiction or "").upper()
    for prof in data.get("professions", []):
        if (prof.get("jurisdiction") or "").upper() != juris:
            continue
        candidates = {_norm(prof.get("profession_id")), _norm(prof.get("title"))}
        if q in {c for c in candidates if c}:
            return CredentialResult(
                covered=True, abstained=False,
                profession_id=prof.get("profession_id"), title=prof.get("title"),
                jurisdiction=prof.get("jurisdiction"), regulated=prof.get("regulated"),
                required=list(prof.get("required_credentials", [])),
                preferred=list(prof.get("preferred_credentials", [])),
                source_url=prof.get("source_url"),
            )
    return CredentialResult(covered=False, abstained=True,
                           reason="This profession/jurisdiction is outside the declared credential matrix.")


# --- K3: emerging roles / aliases --------------------------------------------


@dataclass
class AliasResult:
    resolved: bool
    canonical: str | None = None
    canonical_family: str | None = None
    added_in: str | None = None
    confidence: str | None = None


def resolve_alias(text: str) -> AliasResult:
    """Resolve an emerging-role alias to its canonical form on a CONFIDENT exact match.

    Only an exact (case-insensitive) alias match resolves; anything else is left
    unresolved so existing role resolution is never overridden and ambiguous/new roles
    stay safe.
    """
    data = _k3()
    q = _norm(text)
    if not q:
        return AliasResult(resolved=False)
    for entry in data.get("aliases", []):
        if _norm(entry.get("alias")) == q:
            return AliasResult(
                resolved=True, canonical=entry.get("canonical"),
                canonical_family=entry.get("canonical_family"),
                added_in=entry.get("added_in"), confidence=entry.get("confidence"))
    return AliasResult(resolved=False)


# --- K4: additional Adzuna capabilities (bounded spec + validation) ----------


@dataclass
class AdzunaValidation:
    valid: bool
    operation_id: str | None = None
    endpoint: str | None = None
    entitlement: str | None = None
    cleaned_params: dict[str, Any] = field(default_factory=dict)
    safe_output: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    live_validation_status: str = "UNVALIDATED"


def validate_adzuna_operation(
    operation_id: str, params: dict[str, Any] | None, *, entitlements: set[str] | None = None
) -> AdzunaValidation:
    """Validate a request for an additional Adzuna operation WITHOUT calling the provider.

    Enforces: the operation is allow-listed; the caller holds the required entitlement;
    every parameter is present-if-required and within declared bounds; the country is
    allow-listed. Returns cleaned params + the safe-output shape, or a bounded error list.
    NO live call is made (live validation is UNVALIDATED, cost-gated).
    """
    data = _k4()
    params = params or {}
    ents = entitlements or set()
    ops = {o["operation_id"]: o for o in data.get("operations", [])}
    spec = ops.get(operation_id)
    if spec is None:
        return AdzunaValidation(valid=False, errors=[f"Operation '{operation_id}' is not allow-listed."])

    errors: list[str] = []
    entitlement = spec.get("entitlement")
    if entitlement and entitlement not in ents:
        errors.append(f"Missing entitlement '{entitlement}'.")

    cleaned: dict[str, Any] = {}
    allowed_countries = set(data.get("allowed_countries", []))
    for name, rule in (spec.get("params") or {}).items():
        present = name in params and params[name] is not None
        if rule.get("required") and not present:
            errors.append(f"Missing required parameter '{name}'.")
            continue
        if not present:
            if "default" in rule:
                cleaned[name] = rule["default"]
            continue
        value = params[name]
        kind = rule.get("type")
        if kind == "country_code":
            code = str(value).strip().upper()
            if code not in allowed_countries:
                errors.append(f"Country '{code}' is not allow-listed.")
            else:
                cleaned[name] = code
        elif kind == "string":
            text = str(value).strip()
            if not text:
                errors.append(f"Parameter '{name}' must be non-empty.")
            elif len(text) > int(rule.get("max_length", 200)):
                errors.append(f"Parameter '{name}' exceeds max length.")
            else:
                cleaned[name] = text
        elif kind == "int":
            try:
                num = int(value)
            except (TypeError, ValueError):
                errors.append(f"Parameter '{name}' must be an integer.")
                continue
            if "min" in rule and num < rule["min"]:
                errors.append(f"Parameter '{name}' below minimum {rule['min']}.")
            elif "max" in rule and num > rule["max"]:
                errors.append(f"Parameter '{name}' above maximum {rule['max']}.")
            else:
                cleaned[name] = num
        else:  # unknown declared type → reject conservatively
            errors.append(f"Parameter '{name}' has an unsupported type.")

    return AdzunaValidation(
        valid=not errors,
        operation_id=operation_id if not errors else None,
        endpoint=spec.get("adzuna_endpoint"),
        entitlement=entitlement,
        cleaned_params=cleaned if not errors else {},
        safe_output=list(spec.get("safe_output", [])),
        errors=errors,
        live_validation_status=data.get("live_validation_status", "UNVALIDATED"),
    )


# --- manifest summaries ------------------------------------------------------


def governed_dataset_summaries() -> list[dict]:
    """Safe metadata for each governed dataset — for the Knowledge Manifest / diagnostics.

    Never exposes secrets or candidate content: only counts, provenance and review status.
    """
    out: list[dict] = []
    k1 = _k1()
    if k1:
        out.append({
            "dataset_id": k1.get("dataset_id"), "requirement": "K1", "title": k1.get("title"),
            "jurisdiction": k1.get("jurisdiction"), "language": k1.get("language"),
            "version": k1.get("version"), "reference_year": k1.get("reference_year"),
            "authority": k1.get("authority"), "authority_level": k1.get("authority_level"),
            "review_status": k1.get("data_review_status"),
            "record_count": len(k1.get("occupations", [])),
            "citation_capable": True,
        })
    k2 = _k2()
    if k2:
        juris = sorted({p.get("jurisdiction") for p in k2.get("professions", []) if p.get("jurisdiction")})
        out.append({
            "dataset_id": k2.get("dataset_id"), "requirement": "K2", "title": k2.get("title"),
            "jurisdiction": ",".join(juris), "version": k2.get("version"),
            "review_status": k2.get("data_review_status"),
            "record_count": len(k2.get("professions", [])), "citation_capable": True,
        })
    k3 = _k3()
    if k3:
        out.append({
            "dataset_id": k3.get("dataset_id"), "requirement": "K3", "title": k3.get("title"),
            "version": k3.get("version"), "review_status": k3.get("data_review_status"),
            "record_count": len(k3.get("aliases", [])), "citation_capable": False,
        })
    k4 = _k4()
    if k4:
        out.append({
            "dataset_id": k4.get("dataset_id"), "requirement": "K4", "title": k4.get("title"),
            "version": k4.get("version"), "provider": k4.get("provider"),
            "review_status": k4.get("live_validation_status"),
            "record_count": len(k4.get("operations", [])), "citation_capable": False,
        })
    return out
