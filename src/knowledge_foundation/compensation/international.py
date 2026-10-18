"""ILOSTAT-style international statistical evidence (GKB-12; PROPOSED ENGINEERING DESIGN). A STRUCTURAL CONTRACT only: nothing is known or assumed about any real ILOSTAT dataset, indicator
code, classification label, unit or coverage (none is held locally; a download or ingestion needs registry approval that does not exist). The caller supplies the source's own vocabulary as
explicit maps; a label that is not mapped is rejected, never guessed.

Eligibility is strict: only an indicator the caller maps to a COMPENSATION quantity (a pay period, a statistic and an earnings concept that is not household income) becomes a record. Employment
rates, productivity, GDP and every other labour-market indicator are rejected as ``unsupported_statistic``: they are not salary estimates and are never converted into one. A unit that is not a
currency (for example a purchasing-power or index unit) is rejected. The occupation classification and its edition must be stated by the source row and mapped explicitly (ISCO-08 and
ISCO-88 are different editions). Every record is national (country-level) harmonised evidence: it may reach C3 only through a registry source whose precedence category is decided, and the
international family boundary in the precedence policy keeps it non-operational until the owner decides D-16."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Iterable, Mapping

from src.knowledge_foundation.compensation.adapters import _amount, _build
from src.knowledge_foundation.compensation.record import CompensationRecordV2
from src.persistence import COMP_EARNINGS_CONCEPTS, COMP_EVIDENCE_METHODS, COMP_PAY_PERIODS, COMP_POPULATION_SCOPES

__all__ = ["ISO3_TO_ISO2", "ilostat_records"]

# ISO 3166-1 alpha-3 to alpha-2 for the markets this programme names (a reference table, not data). Anything else is rejected as ``area_unmapped`` unless the caller supplies ``area_map``.
ISO3_TO_ISO2 = {"ARG": "AR", "BOL": "BO", "BRA": "BR", "CHL": "CL", "COL": "CO", "ECU": "EC", "GUY": "GY", "PRY": "PY", "PER": "PE", "SUR": "SR", "URY": "UY", "VEN": "VE",
                "CAN": "CA", "MEX": "MX", "USA": "US", "GBR": "GB"}


def ilostat_records(rows: Iterable[Mapping[str, Any]], *, source_ref: str, source_edition: str, indicator_map: Mapping[str, Mapping[str, Any]], currency_by_unit: Mapping[str, str | None],
                    classification_map: Mapping[str, tuple[str, str]], currency_by_country: Mapping[str, str] | None = None, local_currency_unit: str | None = None,
                    area_map: Mapping[str, str] | None = None, publication_date: datetime | None = None) -> tuple[list[CompensationRecordV2], Counter]:
    """Row contract: ``ref_area`` (alpha-3), ``classif`` (occupation code), ``classification`` (source label), ``indicator``, ``unit``, ``time`` (reference year), ``value``.
    ``indicator_map[indicator]`` = {period, measure, percentile?, concept, population, method?, basis?}; ``currency_by_unit[unit]`` = ISO currency or None (not a currency);
    ``local_currency_unit`` names the unit whose currency is taken from ``currency_by_country``; ``classification_map[label]`` = (taxonomy scheme, edition)."""
    for ind, cfg in indicator_map.items():
        if cfg.get("period") not in COMP_PAY_PERIODS or cfg.get("concept") not in COMP_EARNINGS_CONCEPTS or cfg.get("concept") in ("unknown", "household_income"):
            raise ValueError(f"indicator_map: '{ind}' must map to a pay period and an occupation-compensation earnings concept")
        if cfg.get("population", "unknown") not in COMP_POPULATION_SCOPES or cfg.get("method", "unknown") not in COMP_EVIDENCE_METHODS or cfg.get("measure") not in ("median", "mean", "percentile"):
            raise ValueError(f"indicator_map: '{ind}' has an unknown population, method or statistic")
    areas = {**ISO3_TO_ISO2, **(area_map or {})}
    out: list[CompensationRecordV2] = []
    rej: Counter = Counter()
    for row in rows:
        country = areas.get(str(row.get("ref_area") or "").strip().upper())
        if country is None:
            rej["area_unmapped"] += 1
            continue
        code = str(row.get("classif") if row.get("classif") is not None else "").strip()
        if not code.isdigit() or not 1 <= len(code) <= 4:
            rej["invalid_native_code"] += 1
            continue
        classification = classification_map.get(str(row.get("classification")))
        if classification is None:
            rej["classification_unmapped"] += 1
            continue
        cfg = indicator_map.get(str(row.get("indicator")))
        if cfg is None:
            rej["unsupported_statistic"] += 1                      # employment rates, productivity, GDP and any other indicator: not a salary measure
            continue
        unit = str(row.get("unit") or "")
        if unit not in currency_by_unit:
            rej["unsupported_unit"] += 1
            continue
        currency = currency_by_unit[unit]
        if currency is None and local_currency_unit is not None and unit == local_currency_unit:
            currency = (currency_by_country or {}).get(country)
            if currency is None:
                rej["currency_unmapped"] += 1
                continue
        if currency is None:
            rej["unit_not_a_currency"] += 1
            continue
        try:
            year = int(row.get("time"))
        except (TypeError, ValueError):
            rej["invalid_reference_year"] += 1
            continue
        value, state = _amount(row.get("value"))
        if state == "invalid":
            rej["malformed_amount"] += 1
            continue
        rec = _build(rej, taxonomy_scheme=classification[0], taxonomy_edition=classification[1], native_code=code, occupation_level="detailed" if len(code) == 4 else "broad", country=country,
                     geography_level="national", currency=currency, pay_period=cfg["period"], pay_basis=cfg.get("basis", "unknown"), measure=cfg["measure"], percentile=int(cfg.get("percentile", 0)),
                     earnings_concept=cfg["concept"], population_scope=cfg.get("population", "unknown"), evidence_method=cfg.get("method", "unknown"),
                     value_status="reported" if state == "reported" else "suppressed", value=value, source_ref=source_ref, source_edition=source_edition, reference_year=year,
                     publication_date=publication_date, limitations="International harmonised statistic published for the stated country, period, concept and population only: not a national occupation-specific figure; nothing converted.",
                     provenance={"transformation": "ilostat_contract", "indicator": str(row.get("indicator")), "unit": unit, "level_basis": "isco_digit_count"})
        if rec is not None:
            out.append(rec)
    return out, rej
