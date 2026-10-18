"""Governed adapter contracts for Canada (GKB-8), Mexico (GKB-9) and Brazil (GKB-10). Each adapter is a PURE transformation from parsed source rows to the SAME ``CompensationRecordV2``
used everywhere (no country-specific money model) plus a reason-code count for rows it cannot represent. It reads no file, downloads nothing and persists nothing: persisting goes through
the registry-gated importer. Nothing about any real dataset is assumed: the caller supplies the source's own vocabulary (statistic, pay period, earnings concept, population and method labels)
as explicit maps, and a label that is not mapped is REJECTED, never guessed. The adapter never converts a period or a currency, never turns a regional row into a national one, never
repairs a value, and maps a suppression marker to an explicit status.

Row contract (all keys optional unless stated): ``code`` (required), ``region`` (ISO 3166-2 subdivision, validated; absent means national), ``statistic`` and ``period`` (required, source
labels), ``value`` (required), ``lower``/``upper`` (published bounds), ``currency`` (must equal the national currency when present), ``concept``, ``population``, ``method`` (source labels),
``basis`` (gross or net, otherwise the adapter default), ``level`` (detailed or broad as PUBLISHED by the source; otherwise ``level_by_code_length`` supplied by the caller)."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any, Iterable, Mapping

from src.knowledge_foundation.compensation.adapters import _amount, _build
from src.knowledge_foundation.compensation.countries import CountryProfile, PROFILES, WIDER_SA_PROFILES, normalize_region
from src.knowledge_foundation.compensation.record import CompensationRecordV2
from src.persistence import COMP_EARNINGS_CONCEPTS, COMP_EVIDENCE_METHODS, COMP_PAY_PERIODS, COMP_POPULATION_SCOPES

__all__ = ["country_records", "canada_records", "mexico_records", "brazil_records", "south_america_records"]


def _check_map(name: str, mapping: Mapping[str, Any] | None, allowed: Iterable[str]) -> None:
    for label, target in (mapping or {}).items():
        if target not in set(allowed):
            raise ValueError(f"{name}: '{label}' maps to an unknown value")


def country_records(profile: CountryProfile, rows: Iterable[Mapping[str, Any]], *, source_ref: str, source_edition: str, taxonomy_edition: str, reference_year: int,
                    statistic_map: Mapping[str, tuple[str, int]], period_map: Mapping[str, str], concept_map: Mapping[str, str] | None = None,
                    population_map: Mapping[str, str] | None = None, method_map: Mapping[str, str] | None = None, level_by_code_length: Mapping[int, str] | None = None,
                    require_concept: bool = False, require_population: bool = False, pay_basis: str = "unknown", bounds_semantic: str = "unknown", code_pattern: str | None = None,
                    publication_date: datetime | None = None) -> tuple[list[CompensationRecordV2], Counter]:
    _check_map("period_map", period_map, COMP_PAY_PERIODS)
    _check_map("concept_map", concept_map, COMP_EARNINGS_CONCEPTS)
    _check_map("population_map", population_map, COMP_POPULATION_SCOPES)
    _check_map("method_map", method_map, COMP_EVIDENCE_METHODS)
    pattern = re.compile(code_pattern) if code_pattern else None
    out: list[CompensationRecordV2] = []
    rej: Counter = Counter()
    for row in rows:
        code = str(row.get("code") if row.get("code") is not None else "").strip()
        if not code:
            rej["missing_native_code"] += 1
            continue
        if pattern is not None and not pattern.fullmatch(code):
            rej["invalid_native_code"] += 1
            continue
        currency = profile.currency
        if profile.enforce_currency:
            if row.get("currency") not in (None, "", profile.currency):
                rej["currency_mismatch"] += 1
                continue
        else:                                                              # wider South America: the SOURCE row states its currency (no assumption, no default)
            currency = str(row.get("currency") or "").strip()
            if not currency:
                rej["currency_missing"] += 1
                continue
        region_in = row.get("region")
        region = None
        if region_in not in (None, ""):
            region = normalize_region(profile.country, str(region_in))
            if region is None:
                rej["region_unrecognised"] += 1
                continue
        stat = statistic_map.get(str(row.get("statistic")))
        if stat is None:
            rej["unsupported_statistic"] += 1
            continue
        period = period_map.get(str(row.get("period")))
        if period is None:
            rej["unsupported_period"] += 1
            continue
        resolved: dict[str, str] = {}
        failed = False
        for key, mapping, required, field in (("concept", concept_map, require_concept, "earnings_concept"), ("population", population_map, require_population, "population_scope"),
                                              ("method", method_map, require_population, "evidence_method")):
            label = row.get(key)
            if label in (None, ""):
                if required:
                    rej[f"{key}_missing"] += 1
                    failed = True
                    break
                resolved[field] = "unknown"
                continue
            target = (mapping or {}).get(str(label))
            if target is None:
                rej[f"{key}_unmapped"] += 1
                failed = True
                break
            resolved[field] = target
        if failed:
            continue
        level = row.get("level") if row.get("level") in ("detailed", "broad") else (level_by_code_length or {}).get(len(code), "unknown")
        value, state = _amount(row.get("value"))
        if state == "invalid":
            rej["malformed_amount"] += 1
            continue
        lower, ls = _amount(row.get("lower"))
        upper, us = _amount(row.get("upper"))
        bounds_ok = state == "reported" and ls == "reported" and us == "reported" and lower <= upper
        basis = row.get("basis") if row.get("basis") in ("gross", "net") else pay_basis
        rec = _build(rej, taxonomy_scheme=profile.taxonomy_scheme, taxonomy_edition=taxonomy_edition, native_code=code, occupation_level=level, country=profile.country,
                     region=region, geography_level="regional" if region else "national", currency=currency, pay_period=period, pay_basis=basis, measure=stat[0],
                     percentile=stat[1], value_status="reported" if state == "reported" else "suppressed", value=value, lower_value=lower if bounds_ok else None,
                     upper_value=upper if bounds_ok else None, bounds_semantic=bounds_semantic if bounds_ok else "unknown", source_ref=source_ref, source_edition=source_edition,
                     reference_year=reference_year, publication_date=publication_date,
                     limitations=f"{profile.name}: figure published for the stated geography, period, concept and population only; nothing converted or derived.",
                     provenance={"transformation": f"{profile.country.lower()}_country_adapter", "level_basis": "source_published" if row.get("level") in ("detailed", "broad") else "caller_rule",
                                 "source_labels": {"statistic": str(row.get("statistic")), "period": str(row.get("period"))}}, **resolved)
        if rec is not None:
            out.append(rec)
    return out, rej


def canada_records(rows: Iterable[Mapping[str, Any]], **kw) -> tuple[list[CompensationRecordV2], Counter]:
    """GKB-8: NOC-coded evidence in CAD. National and provincial or territorial figures stay separate (a provincial row is never a national figure and a national figure is never inferred
    from a province); an hourly figure stays hourly. Earnings concept and population are optional (recorded as unknown when the source does not say)."""
    return country_records(PROFILES["CA"], rows, **kw)


def mexico_records(rows: Iterable[Mapping[str, Any]], **kw) -> tuple[list[CompensationRecordV2], Counter]:
    """GKB-9: SINCO-coded evidence in MXN. The earnings concept is REQUIRED (individual earnings, employment income, wage statistic, household income, formal-sector compensation are
    different quantities; household income is mapped but then rejected by the importer as not occupation compensation) and so is the population."""
    kw.setdefault("require_concept", True)
    kw.setdefault("require_population", True)
    return country_records(PROFILES["MX"], rows, **kw)


def brazil_records(rows: Iterable[Mapping[str, Any]], **kw) -> tuple[list[CompensationRecordV2], Counter]:
    """GKB-10: CBO-coded evidence in BRL. Concept, population and method are REQUIRED so administrative formal-sector records and survey evidence are never merged into one figure."""
    kw.setdefault("require_concept", True)
    kw.setdefault("require_population", True)
    return country_records(PROFILES["BR"], rows, **kw)


def south_america_records(country: str, rows: Iterable[Mapping[str, Any]], **kw) -> tuple[list[CompensationRecordV2], Counter]:
    """GKB-11: one reusable source-family adapter for the wider South American markets (Argentina, Bolivia, Chile, Colombia, Ecuador, Guyana, Paraguay, Peru, Suriname, Uruguay, Venezuela;
    Brazil keeps ``brazil_records``). Structural contract only: the earnings concept, population and method are REQUIRED (household surveys, administrative payroll, formal-sector figures and
    occupation wages are different quantities), the currency must be stated by the source row, regions are validated against the ISO 3166-2 vocabulary where one is recorded, and nothing about
    any real dataset is assumed. The taxonomy namespace is ISCO (no national classification is identified); the edition comes from the caller."""
    profile = WIDER_SA_PROFILES.get((country or "").strip().upper())
    if profile is None:
        raise ValueError("not a wider South America profile (Brazil uses brazil_records)")
    kw.setdefault("require_concept", True)
    kw.setdefault("require_population", True)
    return country_records(profile, rows, **kw)
