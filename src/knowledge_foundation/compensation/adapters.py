"""Source adapters (GKB-6 EU, GKB-7 US) and UK compatibility. An adapter is a PURE transformation from parsed source rows to ``CompensationRecordV2`` candidates plus a reason-code
count for rows it cannot represent; it reads no file, downloads nothing and writes nothing (persisting goes through the registry-gated importer). It never converts a period, a
currency or a gross/net basis, never rounds, never repairs a value and maps a suppression marker to an explicit ``suppressed`` status (never zero).

* ``oews_records`` (US BLS OEWS): annual median wage in USD with the published 10th/90th percentile bounds; SOC edition is an explicit parameter (default ``unknown``: a production import
  refuses it); pay basis stays ``unknown`` unless the caller documents it.
* ``ashe_records`` (UK ONS ASHE): published GROSS WEEKLY pay in GBP stays weekly (never annualised); UK SOC 2020 is explicit and versioned.
* ``eurostat_ses_records`` (EU contract): requires an explicit indicator map and currency-unit rules (no Eurostat code is assumed); PPS values are not currency and are rejected; a
  missing market stays missing.
* ``derive_onet_soc_prefix_links``: an UNVERIFIED structural-prefix relationship (basis ``derived_rule``, status ``partial``) that no resolver step relies on."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from src.knowledge_foundation.compensation.policy import normalize_country
from src.knowledge_foundation.compensation.record import CompensationRecordV2
from src.knowledge_foundation.graph import OccupationGraph

__all__ = ["oews_records", "ashe_records", "eurostat_ses_records", "derive_onet_soc_prefix_links", "SUPPRESSION_MARKERS"]

SUPPRESSION_MARKERS = frozenset({"*", "**", "#", "x", "X", ":", "-", "~", "n/a", "N/A", "na", "NA", ""})


def _amount(value: Any) -> tuple[Decimal | None, str]:
    """(amount, state) with state in reported, suppressed, invalid. A float is converted through its shortest decimal text (exact for a published figure); NaN is missing."""
    if value is None:
        return None, "suppressed"
    if isinstance(value, bool):
        return None, "invalid"
    if isinstance(value, str):
        t = value.strip().replace(",", "")
        if t in SUPPRESSION_MARKERS:
            return None, "suppressed"
        try:
            d = Decimal(t)
        except Exception:  # noqa: BLE001
            return None, "invalid"
    elif isinstance(value, float):
        if value != value:
            return None, "suppressed"
        d = Decimal(repr(value))
    else:
        try:
            d = Decimal(str(value))
        except Exception:  # noqa: BLE001
            return None, "invalid"
    if not d.is_finite() or d <= 0:
        return None, "invalid"
    return d, "reported"


def _build(rej: Counter, **kw) -> CompensationRecordV2 | None:
    try:
        return CompensationRecordV2(**kw)
    except (ValueError, TypeError) as exc:
        loc = "model"
        errors = getattr(exc, "errors", None)
        if callable(errors) and exc.errors():
            loc = ".".join(str(x) for x in exc.errors()[0]["loc"]) or "model"
        rej[f"schema_invalid:{loc}"] += 1
        return None


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- US
def oews_records(rows: Iterable[Mapping[str, Any]], *, source_edition: str, reference_year: int, soc_edition: str = "unknown", source_ref: str = "bls_oews", pay_basis: str = "unknown",
                 publication_date: datetime | None = None) -> tuple[list[CompensationRecordV2], Counter]:
    out: list[CompensationRecordV2] = []
    rej: Counter = Counter()
    for row in rows:
        code = str(row.get("OCC_CODE") or "").strip()
        group = str(row.get("O_GROUP") or "").strip().lower()
        if group == "total":
            rej["aggregate_total_row"] += 1
            continue
        if not code:
            rej["missing_native_code"] += 1
            continue
        level = {"detailed": "detailed", "broad": "broad", "minor": "broad", "major": "broad"}.get(group, "unknown")
        median, state = _amount(row.get("A_MEDIAN"))
        if state == "invalid":
            rej["malformed_amount"] += 1
            continue
        lower, ls = _amount(row.get("A_PCT10"))
        upper, us = _amount(row.get("A_PCT90"))
        bounds_ok = state == "reported" and ls == "reported" and us == "reported" and lower <= upper
        rec = _build(rej, taxonomy_scheme="soc", taxonomy_edition=soc_edition, native_code=code, occupation_level=level, country="US", geography_level="national", currency="USD",
                     pay_period="annual", pay_basis=pay_basis, measure="median", value_status="reported" if state == "reported" else "suppressed", value=median,
                     lower_value=lower if bounds_ok else None, upper_value=upper if bounds_ok else None, bounds_semantic="percentile_10_90" if bounds_ok else "unknown",
                     source_ref=source_ref, source_edition=source_edition, reference_year=reference_year, publication_date=publication_date,
                     limitations="Published annual median wage; the pay basis (gross or net) is not recorded unless stated by the caller.",
                     provenance={"transformation": "oews_annual_median", "level_basis": "O_GROUP", "source_group": group or None})
        if rec is not None:
            out.append(rec)
    return out, rej


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- UK
def ashe_records(rows: Iterable[Mapping[str, Any]], *, source_edition: str, reference_year: int, uk_soc_edition: str = "2020", source_ref: str = "ons_ashe", pay_basis: str = "gross",
                 data_vintage: str = "", publication_date: datetime | None = None) -> tuple[list[CompensationRecordV2], Counter]:
    """ASHE Table 14.1a: GROSS WEEKLY pay, all employees, median. Weekly pay is kept weekly. Level comes from the UK SOC digit count (4 = unit group = detailed; 1 to 3 = broader groups)."""
    out: list[CompensationRecordV2] = []
    rej: Counter = Counter()
    for row in rows:
        code = str(row.get("code") if row.get("code") is not None else "").strip()
        if not code or not code.isdigit() or len(code) > 4:
            rej["invalid_native_code"] += 1
            continue
        median, state = _amount(row.get("median"))
        if state == "invalid":
            rej["malformed_amount"] += 1
            continue
        rec = _build(rej, taxonomy_scheme="uk_soc", taxonomy_edition=uk_soc_edition, native_code=code, occupation_level="detailed" if len(code) == 4 else "broad", country="GB",
                     geography_level="national", currency="GBP", pay_period="weekly", pay_basis=pay_basis, measure="median",
                     value_status="reported" if state == "reported" else "suppressed", value=median, source_ref=source_ref, source_edition=source_edition, reference_year=reference_year,
                     data_vintage=data_vintage, publication_date=publication_date, limitations="Published gross weekly pay (all employees); NOT annualised and NOT converted to another currency.",
                     provenance={"transformation": "ashe_weekly_median", "level_basis": "uk_soc_digit_count", "source_country_label": "UK"})
        if rec is not None:
            out.append(rec)
    return out, rej


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- EU
def eurostat_ses_records(rows: Iterable[Mapping[str, Any]], *, source_edition: str, reference_year: int, indicator_map: Mapping[str, tuple[str, str]], currency_by_unit: Mapping[str, str | None],
                         currency_by_country: Mapping[str, str] | None = None, isco_edition: str = "08", source_ref: str = "eurostat_earnings",
                         publication_date: datetime | None = None) -> tuple[list[CompensationRecordV2], Counter]:
    """Contract for a structured Eurostat earnings table. NOTHING is assumed about Eurostat's codes: the caller supplies ``indicator_map`` (indicator -> (pay period, measure)) and
    ``currency_by_unit`` (unit -> ISO currency, or None for a unit that is not a currency such as PPS, or ``NAC`` resolved through ``currency_by_country``)."""
    out: list[CompensationRecordV2] = []
    rej: Counter = Counter()
    for row in rows:
        geo = normalize_country(row.get("geo"))
        if not geo:
            rej["missing_geography"] += 1
            continue
        code = str(row.get("isco") if row.get("isco") is not None else "").strip()
        if not code.isdigit() or not 1 <= len(code) <= 4:
            rej["invalid_native_code"] += 1
            continue
        mapped = indicator_map.get(str(row.get("indic")))
        if mapped is None:
            rej["unsupported_statistic"] += 1
            continue
        unit = str(row.get("unit") or "")
        if unit not in currency_by_unit:
            rej["unsupported_unit"] += 1
            continue
        currency = currency_by_unit[unit]
        if currency is None and unit == "NAC":
            currency = (currency_by_country or {}).get(geo)
            if currency is None:
                rej["currency_unmapped"] += 1
                continue
        if currency is None:
            rej["unit_not_a_currency"] += 1
            continue
        value, state = _amount(row.get("value"))
        if state == "invalid":
            rej["malformed_amount"] += 1
            continue
        period, measure = mapped
        rec = _build(rej, taxonomy_scheme="isco", taxonomy_edition=isco_edition, native_code=code, occupation_level="detailed" if len(code) == 4 else "broad", country="EU" if geo.startswith("EU") else geo,
                     geography_level="eu_aggregate" if geo.startswith("EU") else "national", currency=currency, pay_period=period, pay_basis="unknown", measure=measure,
                     value_status="reported" if state == "reported" else "suppressed", value=value, source_ref=source_ref, source_edition=source_edition, reference_year=reference_year,
                     publication_date=publication_date, limitations="Harmonised international statistic: not a national occupation-specific figure; pay basis not recorded.",
                     provenance={"transformation": "eurostat_ses_contract", "level_basis": "isco_digit_count", "indicator": str(row.get("indic")), "unit": unit})
        if rec is not None:
            out.append(rec)
    return out, rej


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- O*NET-SOC
def derive_onet_soc_prefix_links(graph: OccupationGraph, *, onet_edition: str, soc_edition: str, limit: int | None = None) -> dict[str, int]:
    """Register UNVERIFIED structural links from O*NET-SOC nodes (``xx-xxxx.yy``) to the SOC node with the same 6-digit prefix. Basis ``derived_rule``, status ``partial`` (never
    VERIFIED, never equivalent), with an explicit limitation; the compensation resolver follows only VERIFIED relationships, so these links never carry compensation evidence."""
    from sqlalchemy import select
    from src.persistence import GraphOccupation, GraphOccupationIdentifier, OccupationTaxonomy
    made = skipped = 0
    with graph._sf() as s:
        onet = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == "onet_soc", OccupationTaxonomy.edition == onet_edition))
        soc = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == "soc", OccupationTaxonomy.edition == soc_edition))
        if onet is None or soc is None:
            return {"created": 0, "skipped": 0}
        pairs = []
        for ident, node in s.execute(select(GraphOccupationIdentifier, GraphOccupation).join(GraphOccupation, GraphOccupation.id == GraphOccupationIdentifier.occupation_id)
                                     .where(GraphOccupationIdentifier.taxonomy_id == onet.id)).all():
            hit = s.execute(select(GraphOccupation.occupation_key).join(GraphOccupationIdentifier, GraphOccupationIdentifier.occupation_id == GraphOccupation.id)
                            .where(GraphOccupationIdentifier.taxonomy_id == soc.id, GraphOccupationIdentifier.native_code == ident.native_code.split(".")[0])).first()
            pairs.append((node.occupation_key, hit[0] if hit else None))
    for i, (a, b) in enumerate(pairs):
        if limit is not None and i >= limit:
            break
        if b is None or a == b:
            skipped += 1
            continue
        graph.add_relationship(a, b, relationship_type="broader", basis="derived_rule", mapping_status="partial", from_taxonomy=("onet_soc", onet_edition), to_taxonomy=("soc", soc_edition),
                               limitations="Structural code-prefix rule (O*NET-SOC refines a SOC code); the SOC edition behind the O*NET taxonomy is unverified. Not a source-provided crosswalk.")
        made += 1
    return {"created": made, "skipped": skipped}
