#!/usr/bin/env python
"""Generate the P10C-G global evaluation corpus (``src/knowledge_foundation/data/global_evaluation_corpus.json``). Deterministic: no randomness, no clock, no network; re-running produces
byte-identical output. Every source, occupation, alias and amount is INVENTED and labelled synthetic (a fixture source can never be approved or serve as evidence). The corpus uses the existing
compensation-corpus schema (``load_world`` / ``evaluate_cases``) so the existing resolvers, registry and policy are exercised, not a parallel engine.

    python scripts/gen_global_evaluation_corpus.py [--check]       (--check fails when the committed file differs from the generated one)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/knowledge_foundation/data/global_evaluation_corpus.json"
VERSION = "1.0.0"
NAT, PES, HARM = "national_official_occupation_statistics", "national_public_employment_service", "eurostat_harmonised"

# jurisdiction: (country, scheme, edition, code pattern, code factory, currency, native pay period, source id, precedence category, other country for the no-fallback case)
JUR = {
    "us": ("US", "soc", "2018", "[0-9]{2}-[0-9]{4}", lambda n: f"98-{n:04d}", "USD", "annual", "fx_g_us", NAT, "CA"),
    "gb": ("GB", "uk_soc", "2020", "[0-9]{1,4}", lambda n: f"{9000 + n}", "GBP", "weekly", "fx_g_gb", NAT, "US"),
    "de": ("DE", "kldb", "2010", "[0-9]{5}", lambda n: f"{98000 + n}", "EUR", "annual", "fx_g_de", PES, "FR"),
    "fr": ("FR", "isco", "08", "[0-9]{4}", lambda n: f"{9800 + n}", "EUR", "annual", "fx_g_eu", HARM, "DE"),
    "ca": ("CA", "noc", "2021", "[0-9]{5}", lambda n: f"{98000 + n}", "CAD", "annual", "fx_g_ca", NAT, "US"),
    "mx": ("MX", "sinco", "2019", "[0-9]{4}", lambda n: f"{9800 + n}", "MXN", "monthly", "fx_g_mx", NAT, "US"),
    "br": ("BR", "cbo", "2002", "[0-9]{6}", lambda n: f"{980000 + n}", "BRL", "monthly", "fx_g_br", NAT, "US"),
    "cl": ("CL", "isco", "08", "[0-9]{4}", lambda n: f"{9700 + n}", "CLP", "monthly", "fx_g_cl", NAT, "AR"),
}
SOURCES = [("fx_g_us", "US statistics office", NAT), ("fx_g_us2", "US second office", NAT), ("fx_g_gb", "UK statistics office", NAT), ("fx_g_de", "German employment service", PES),
           ("fx_g_eu", "EU statistics office", HARM), ("fx_g_ca", "Canadian statistics office", NAT), ("fx_g_mx", "Mexican statistics office", NAT), ("fx_g_br", "Brazilian statistics office", NAT),
           ("fx_g_cl", "Chilean statistics office", NAT)]
EDITIONS = {"fx_g_us": "G-US-1", "fx_g_us2": "G-US2-1", "fx_g_gb": "G-GB-1", "fx_g_de": "G-DE-1", "fx_g_eu": "G-EU-1", "fx_g_ca": "G-CA-1", "fx_g_mx": "G-MX-1", "fx_g_br": "G-BR-1",
            "fx_g_cl": "G-CL-1", "fx_g_unattrib": "G-UN-1"}
CASES: list[dict] = []
SCENARIOS: list[dict] = []


def rec(source, scheme, ed, code, level, country, cur, period, measure, value, year=2025, **kw):
    r = {"source_ref": source, "source_edition": EDITIONS[source], "taxonomy_scheme": scheme, "taxonomy_edition": ed, "native_code": code, "occupation_level": level, "country": country,
         "geography_level": kw.pop("geography_level", "national"), "currency": cur, "pay_period": period, "pay_basis": "gross", "measure": measure, "value": value, "reference_year": year}
    r.update(kw)
    return r


def scen(sid, label, ids, aliases, records, relationships=()):
    SCENARIOS.append({"id": sid, "label": f"{label} [synthetic fixture]", "identifiers": [list(i) for i in ids], "aliases": list(aliases), "records": list(records), "relationships": list(relationships)})


def case(cid, category, scenario, request, expect, tags, internal=True, state=None):
    CASES.append({"id": cid, "category": category, "scenario": scenario, "request": request, "internal": internal, "expect": expect, "tags": tags,
                  "source_state": state or "synthetic_fixture (restricted; can never be approved or serve as evidence)", "evidence_origin": "SYNTHETIC",
                  "qualification_state": "SOURCE_QUALIFICATION_PENDING" if internal is False else "NOT_APPLICABLE_SYNTHETIC"})


def rel(to, source="fx_occ", status="verified", typ="broader", basis="source_provided", ft=None, tt=None):
    return {"to": to, "type": typ, "basis": basis, "status": status, "source": source, "from_taxonomy": ft, "to_taxonomy": tt}


# --------------------------------------------------------------------------------------------------------------------------------------- per jurisdiction
for key, (cc, scheme, ed, pattern, mk, cur, period, src, cat, other) in JUR.items():
    detail, broad, child = mk(1), mk(2), mk(3)
    base = f"syn g {key}"
    scen(f"g_{key}_detail", f"{cc} detailed occupation", [(scheme, ed, detail)], [f"{base} detail"],
         [rec(src, scheme, ed, detail, "detailed", cc, cur, period, "median", "61000.00" if period == "annual" else "3050.50" if period == "monthly" else "1100.50")])
    scen(f"g_{key}_broad", f"{cc} broad occupation group", [(scheme, ed, broad)], [f"{base} broad"],
         [rec(src, scheme, ed, broad, "broad", cc, cur, period, "median", "52000.00" if period == "annual" else "2800.00" if period == "monthly" else "950.00")])
    scen(f"g_{key}_child", f"{cc} detailed occupation without its own measurement", [(scheme, ed, child)], [f"{base} child"], [],
         [rel(f"g_{key}_broad", ft=[scheme, ed], tt=[scheme, ed])])
    cls = "C3" if cat == HARM else "C1"
    bcls = "C3" if cat == HARM else "C2"
    value = "61000" if period == "annual" else "3050.50" if period == "monthly" else "1100.5"
    case(f"{key}-exact-code", "country", f"g_{key}_detail", {"taxonomy_scheme": scheme, "taxonomy_edition": ed, "taxonomy_code": detail, "country": cc, "pay_period": period, "measure": "median"},
         {"outcome": "evidence", "evidence_class": cls, "value": value, "currency": cur, "pay_period": period, "citation": True, "specificity": "exact"}, ["occupation:exact_code", f"jurisdiction:{cc}", "fallback:country_native_detailed" if cls == "C1" else "fallback:international_harmonised"])
    case(f"{key}-official-title", "country", f"g_{key}_detail", {"title": f"{base} detail", "title_language": "en", "country": cc, "pay_period": period, "measure": "median"},
         {"outcome": "evidence", "evidence_class": cls, "value": value}, ["occupation:official_title", f"jurisdiction:{cc}"])
    case(f"{key}-wrong-edition", "country", f"g_{key}_detail", {"taxonomy_scheme": scheme, "taxonomy_edition": "1999", "taxonomy_code": detail, "country": cc},
         {"outcome": "not_found", "no_value": True}, ["occupation:wrong_taxonomy_edition", f"jurisdiction:{cc}"])
    case(f"{key}-broad-evidence", "country", f"g_{key}_broad", {"title": f"{base} broad", "title_language": "en", "country": cc, "pay_period": period, "measure": "median"},
         {"outcome": "evidence", "evidence_class": bcls, "limitation_contains": "BROAD" if bcls == "C2" else "international harmonised"}, ["compensation:detailed_vs_broad", "fallback:country_native_broad" if bcls == "C2" else "fallback:international_harmonised", f"jurisdiction:{cc}"])
    case(f"{key}-child-abstains-with-context", "country", f"g_{key}_child", {"title": f"{base} child", "title_language": "en", "country": cc, "pay_period": period, "measure": "median"},
         {"outcome": "abstain", "evidence_class": "C4", "abstention": "exact_occupation_measurement_unavailable", "no_value": True, "contextual_class": bcls, "contextual_warning_contains": "NOT the requested occupation"},
         ["compensation:no_silent_broader_substitution", "fallback:insufficient_occupation_specificity", f"jurisdiction:{cc}"])
    case(f"{key}-other-country-never-falls-back", "country", f"g_{key}_detail", {"title": f"{base} detail", "title_language": "en", "country": other, "pay_period": period, "measure": "median"},
         {"outcome": "abstain", "evidence_class": "C4", "abstention": "no_evidence_for_occupation_in_country", "no_value": True}, ["fallback:unavailable_national_evidence", "compensation:no_cross_country_substitution", f"jurisdiction:{cc}"])
    case(f"{key}-operational-withheld", "operational", f"g_{key}_detail", {"title": f"{base} detail", "title_language": "en", "country": cc, "pay_period": period, "measure": "median"},
         {"outcome": "abstain", "abstention": "evidence_exists_but_is_not_operational", "no_value": True, "operational": False, "candidate_presentable": False}, ["source:unapproved_never_operational", "source:unqualified_never_operational", f"jurisdiction:{cc}"], internal=False)

# ---------------------------------------------------------------------------------------------------------------------- cross-cutting compensation scenarios (US)
S, E, CUR = "soc", "2018", "USD"
def us(n): return f"99-{n:04d}"
scen("g_x_meas", "measures and pay periods", [(S, E, us(101))], ["syn g x meas"], [
    rec("fx_g_us", S, E, us(101), "detailed", "US", CUR, "annual", "median", "60000", lower_value="40000", upper_value="90000", bounds_semantic="percentile_10_90"),
    rec("fx_g_us", S, E, us(101), "detailed", "US", CUR, "annual", "mean", "64000"),
    rec("fx_g_us", S, E, us(101), "detailed", "US", CUR, "annual", "percentile", "48000", percentile=25),
    rec("fx_g_us", S, E, us(101), "detailed", "US", CUR, "hourly", "median", "29.50")])
req = lambda scenario_title, **kw: {"title": scenario_title, "title_language": "en", "country": "US", **kw}
case("x-default-measures-not-combined", "measurement", "g_x_meas", req("syn g x meas"), {"outcome": "conflict", "no_value": True}, ["compensation:mean_vs_median", "compensation:hourly_vs_annual", "compensation:unsupported_comparison_rejected"])
case("x-median-annual", "measurement", "g_x_meas", req("syn g x meas", measure="median", pay_period="annual"), {"outcome": "evidence", "value": "60000", "pay_period": "annual", "bounds": "percentile_10_90"}, ["compensation:exact_measurement", "compensation:mean_vs_median"])
case("x-mean-annual", "measurement", "g_x_meas", req("syn g x meas", measure="mean", pay_period="annual"), {"outcome": "evidence", "value": "64000"}, ["compensation:mean_vs_median"])
case("x-percentile-25", "measurement", "g_x_meas", req("syn g x meas", measure="percentile", percentile=25, pay_period="annual"), {"outcome": "evidence", "value": "48000"}, ["compensation:percentile"])
case("x-hourly", "measurement", "g_x_meas", req("syn g x meas", measure="median", pay_period="hourly"), {"outcome": "evidence", "value": "29.50", "pay_period": "hourly"}, ["compensation:hourly_vs_annual"])
case("x-unsupported-percentile", "measurement", "g_x_meas", req("syn g x meas", measure="percentile", percentile=99, pay_period="annual"), {"outcome": "abstain", "abstention": "exact_occupation_measurement_unavailable", "no_value": True}, ["compensation:unsupported_measurement"])
case("x-weekly-unavailable-no-annualisation", "measurement", "g_x_meas", req("syn g x meas", measure="median", pay_period="weekly"), {"outcome": "abstain", "no_value": True}, ["compensation:weekly_vs_annual", "compensation:no_hidden_period_conversion"])
scen("g_x_week", "UK-style weekly pay only", [("uk_soc", "2020", "9101")], ["syn g x week"], [rec("fx_g_gb", "uk_soc", "2020", "9101", "detailed", "GB", "GBP", "weekly", "median", "812.40")])
case("x-weekly-kept-weekly", "measurement", "g_x_week", {"title": "syn g x week", "title_language": "en", "country": "GB", "measure": "median", "pay_period": "weekly"}, {"outcome": "evidence", "value": "812.40", "pay_period": "weekly", "currency": "GBP"}, ["compensation:weekly_vs_annual", "compensation:no_hidden_period_conversion"])
case("x-annual-never-derived-from-weekly", "measurement", "g_x_week", {"title": "syn g x week", "title_language": "en", "country": "GB", "measure": "median", "pay_period": "annual"}, {"outcome": "abstain", "no_value": True}, ["compensation:weekly_vs_annual", "compensation:no_hidden_period_conversion"])
scen("g_x_pop", "full-time versus all-employee populations", [(S, E, us(102))], ["syn g x pop"], [
    rec("fx_g_us", S, E, us(102), "detailed", "US", CUR, "annual", "median", "70000", population_scope="full_time_employees"),
    rec("fx_g_us", S, E, us(102), "detailed", "US", CUR, "annual", "median", "62000", population_scope="employees")])
case("x-populations-not-combined", "measurement", "g_x_pop", req("syn g x pop", measure="median", pay_period="annual"), {"outcome": "conflict", "no_value": True}, ["compensation:full_time_vs_part_time"])
case("x-full-time-only", "measurement", "g_x_pop", req("syn g x pop", measure="median", pay_period="annual", population_scope="full_time_employees"), {"outcome": "evidence", "value": "70000", "population_scope": "full_time_employees"}, ["compensation:full_time_vs_part_time"])
case("x-all-employees-only", "measurement", "g_x_pop", req("syn g x pop", measure="median", pay_period="annual", population_scope="employees"), {"outcome": "evidence", "value": "62000", "population_scope": "employees"}, ["compensation:full_time_vs_part_time"])
scen("g_x_reg", "national and regional evidence", [(S, E, us(103))], ["syn g x reg"], [
    rec("fx_g_us", S, E, us(103), "detailed", "US", CUR, "annual", "median", "60000"),
    rec("fx_g_us", S, E, us(103), "detailed", "US", CUR, "annual", "median", "66000", geography_level="regional", region="Texas")])
case("x-national-by-default", "measurement", "g_x_reg", req("syn g x reg", measure="median", pay_period="annual"), {"outcome": "evidence", "value": "60000", "geography_level": "national"}, ["compensation:national_vs_regional"])
case("x-regional-when-requested", "measurement", "g_x_reg", req("syn g x reg", measure="median", pay_period="annual", region="Texas"), {"outcome": "evidence", "value": "66000", "geography_level": "regional", "region": "Texas"}, ["compensation:national_vs_regional"])
case("x-regional-never-becomes-national", "measurement", "g_x_reg", req("syn g x reg", measure="median", pay_period="annual", region="Ohio"), {"outcome": "abstain", "abstention": "no_evidence_for_requested_region", "no_value": True}, ["compensation:national_vs_regional"])
scen("g_x_ed18", "taxonomy edition 2018", [(S, "2018", us(201))], ["syn g x ed18"], [rec("fx_g_us", S, "2018", us(201), "detailed", "US", CUR, "annual", "median", "61000")])
scen("g_x_ed10", "taxonomy edition 2010 with the same code", [(S, "2010", us(201))], ["syn g x ed10"], [rec("fx_g_us", S, "2010", us(201), "detailed", "US", CUR, "annual", "median", "50000")])
case("x-edition-2018", "classification", "g_x_ed18", {"taxonomy_scheme": S, "taxonomy_edition": "2018", "taxonomy_code": us(201), "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "61000"}, ["occupation:taxonomy_edition", "compensation:different_taxonomy_editions"])
case("x-edition-2010", "classification", "g_x_ed10", {"taxonomy_scheme": S, "taxonomy_edition": "2010", "taxonomy_code": us(201), "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "50000"}, ["occupation:taxonomy_edition", "compensation:different_taxonomy_editions"])
case("x-edition-missing-is-ambiguous", "classification", "g_x_ed18", {"taxonomy_scheme": S, "taxonomy_code": us(201), "country": "US"}, {"outcome": "ambiguous", "no_value": True}, ["occupation:ambiguous_code_across_editions", "occupation:conflicting_candidates"])
scen("g_x_periods", "two reference years", [(S, E, us(104))], ["syn g x periods"], [
    rec("fx_g_us", S, E, us(104), "detailed", "US", CUR, "annual", "median", "58000", year=2023), rec("fx_g_us", S, E, us(104), "detailed", "US", CUR, "annual", "median", "60000", year=2025)])
case("x-latest-period-by-default", "measurement", "g_x_periods", req("syn g x periods", measure="median", pay_period="annual"), {"outcome": "evidence", "value": "60000", "reference_year": 2025}, ["compensation:publication_periods"])
case("x-requested-period", "measurement", "g_x_periods", req("syn g x periods", measure="median", pay_period="annual", reference_year=2023), {"outcome": "evidence", "value": "58000", "reference_year": 2023}, ["compensation:publication_periods"])
case("x-absent-period-abstains", "measurement", "g_x_periods", req("syn g x periods", measure="median", pay_period="annual", reference_year=2024), {"outcome": "abstain", "abstention": "no_evidence_for_requested_reference_year", "no_value": True}, ["compensation:publication_periods"])
scen("g_x_vintage", "provisional then revised vintage", [(S, E, us(105))], ["syn g x vintage"], [
    rec("fx_g_us", S, E, us(105), "detailed", "US", CUR, "annual", "median", "59000", data_vintage="2025-provisional"), rec("fx_g_us", S, E, us(105), "detailed", "US", CUR, "annual", "median", "60500", data_vintage="2026-revised")])
case("x-revised-vintage-wins-and-is-labelled", "measurement", "g_x_vintage", req("syn g x vintage", measure="median", pay_period="annual"), {"outcome": "evidence", "value": "60500", "limitation_contains": "data vintage: 2026-revised"}, ["compensation:source_revisions"])
scen("g_x_none", "no measurement", [(S, E, us(106))], ["syn g x none"], [])
case("x-missing-measurement-abstains", "measurement", "g_x_none", req("syn g x none"), {"outcome": "abstain", "evidence_class": "C4", "abstention": "no_evidence_for_occupation_in_country", "no_value": True}, ["compensation:missing_measurements", "fallback:c4_abstains"])
scen("g_x_supp", "publisher-suppressed measurement", [(S, E, us(107))], ["syn g x supp"], [rec("fx_g_us", S, E, us(107), "detailed", "US", CUR, "annual", "median", None, value_status="suppressed")])
case("x-suppressed-never-zero", "measurement", "g_x_supp", req("syn g x supp", measure="median", pay_period="annual"), {"outcome": "abstain", "abstention": "source_value_suppressed", "no_value": True}, ["compensation:suppressed_measurements"])
scen("g_x_tie", "two national sources disagree", [(S, E, us(108))], ["syn g x tie"], [
    rec("fx_g_us", S, E, us(108), "detailed", "US", CUR, "annual", "median", "60000"), rec("fx_g_us2", S, E, us(108), "detailed", "US", CUR, "annual", "median", "63000")])
case("x-conflicting-sources-preserved", "conflict", "g_x_tie", req("syn g x tie", measure="median", pay_period="annual"), {"outcome": "conflict", "abstention": "comparable_sources_of_equal_precedence_disagree", "no_value": True}, ["compensation:conflicting_sources"])
scen("g_x_natintl", "national and international evidence for Germany", [("isco", "08", "9810"), ("kldb", "2010", "98100")], ["syn g x natintl"], [
    rec("fx_g_de", "kldb", "2010", "98100", "detailed", "DE", "EUR", "annual", "median", "55000"), rec("fx_g_eu", "isco", "08", "9810", "detailed", "DE", "EUR", "annual", "median", "52000")])
case("x-national-outranks-international", "country", "g_x_natintl", {"title": "syn g x natintl", "title_language": "en", "country": "DE", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "evidence_class": "C1", "value": "55000", "corroborating": 1}, ["fallback:conflicting_national_and_international", "fallback:c3_not_promoted_to_c1"])
scen("g_x_intl", "authorised international fallback only", [("isco", "08", "9811")], ["syn g x intl"], [rec("fx_g_eu", "isco", "08", "9811", "detailed", "DE", "EUR", "annual", "median", "52000")])
case("x-international-fallback-stays-c3", "country", "g_x_intl", {"title": "syn g x intl", "title_language": "en", "country": "DE", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "evidence_class": "C3", "value": "52000", "limitation_contains": "international harmonised"}, ["fallback:authorised_international", "fallback:c3_not_promoted_to_c1"])
scen("g_x_unmapped", "harmonised evidence reached only through an unverified mapping", [("kldb", "2010", "98200")], ["syn g x unmapped"], [],
     [rel("g_x_unmapped_target", status="partial", typ="related", basis="curated_manual", ft=["kldb", "2010"], tt=["isco", "08"])])
scen("g_x_unmapped_target", "harmonised target occupation", [("isco", "08", "9820")], ["syn g x unmapped target"], [rec("fx_g_eu", "isco", "08", "9820", "detailed", "DE", "EUR", "annual", "median", "50000")])
case("x-unapproved-harmonised-mapping-carries-nothing", "country", "g_x_unmapped", {"title": "syn g x unmapped", "title_language": "en", "country": "DE", "measure": "median", "pay_period": "annual"}, {"outcome": "abstain", "no_value": True}, ["fallback:unapproved_harmonised_mapping"])
case("x-fx-conversion-not-configured", "comparison", "g_x_meas", req("syn g x meas", measure="median", pay_period="annual", comparison_mode="fx_converted"), {"outcome": "not_configured", "no_value": True}, ["fallback:missing_currency_conversion", "compensation:no_unauthorised_currency_conversion"])
case("x-ppp-conversion-not-configured", "comparison", "g_x_meas", req("syn g x meas", measure="median", pay_period="annual", comparison_mode="ppp_adjusted"), {"outcome": "not_configured", "no_value": True}, ["fallback:missing_ppp_conversion"])
case("x-unsupported-geography", "country", "g_x_meas", {"title": "syn g x meas", "title_language": "en", "country": "ZZ"}, {"outcome": "unsupported", "no_value": True}, ["fallback:unsupported_geography"])
case("x-valid-code-unlisted-country", "country", "g_x_meas", {"title": "syn g x meas", "title_language": "en", "country": "JP"}, {"outcome": "unsupported", "no_value": True}, ["fallback:unsupported_geography"])
scen("g_x_cur", "two currencies", [(S, E, us(109))], ["syn g x cur"], [rec("fx_g_us", S, E, us(109), "detailed", "US", "USD", "annual", "median", "60000"), rec("fx_g_us2", S, E, us(109), "detailed", "US", "EUR", "annual", "median", "55000")])
case("x-currencies-never-combined", "comparison", "g_x_cur", req("syn g x cur", measure="median", pay_period="annual"), {"outcome": "conflict", "no_value": True}, ["compensation:no_unauthorised_currency_conversion", "compensation:unsupported_comparison_rejected"])
scen("g_x_nocite", "source without attribution", [(S, E, us(111))], ["syn g x nocite"], [rec("fx_g_unattrib", S, E, us(111), "detailed", "US", CUR, "annual", "median", "60000")])
case("x-incomplete-provenance-withheld", "operational", "g_x_nocite", req("syn g x nocite", measure="median", pay_period="annual"), {"outcome": "abstain", "abstention": "evidence_withheld_citation_incomplete", "no_value": True}, ["source:incomplete_provenance"])

# ------------------------------------------------------------------------------------------------------------------------------ occupation classification
scen("g_x_amb_a", "ambiguous title A", [(S, E, us(301))], ["syn g shared title"], [rec("fx_g_us", S, E, us(301), "detailed", "US", CUR, "annual", "median", "50000")])
scen("g_x_amb_b", "ambiguous title B", [(S, E, us(302))], ["syn g shared title"], [rec("fx_g_us", S, E, us(302), "detailed", "US", CUR, "annual", "median", "80000")])
case("o-ambiguous-title-no-salary", "classification", "g_x_amb_a", req("syn g shared title"), {"outcome": "ambiguous", "no_value": True}, ["occupation:ambiguous_title", "occupation:conflicting_candidates"])
case("o-unsupported-title", "classification", "g_x_amb_a", req("syn g never heard of it"), {"outcome": "not_found", "no_value": True}, ["occupation:unsupported_title"])
case("o-missing-classification", "classification", "g_x_amb_a", {"country": "US"}, {"outcome": "insufficient_context", "no_value": True}, ["occupation:missing_classification"])
case("o-wrong-country-title", "classification", "g_x_amb_a", {"title": "syn g shared title", "title_language": "en", "country": "ZZ"}, {"outcome": "unsupported", "no_value": True}, ["occupation:wrong_country"])
scen("g_x_alias", "occupation reached through a proposed alias", [(S, E, us(303))], ["syn g proposed alias"], [rec("fx_g_us", S, E, us(303), "detailed", "US", CUR, "annual", "median", "61000")])
case("o-unqualified-alias-resolves-but-is-never-operational", "classification", "g_x_alias", req("syn g proposed alias", measure="median", pay_period="annual"), {"outcome": "evidence", "occupation_status": "resolved", "value": "61000", "operational": False, "candidate_presentable": False}, ["occupation:curated_alias_proposal", "occupation:unqualified_alias"])
case("o-detailed-vs-broad-identity", "classification", "g_us_broad", {"title": "syn g us broad", "title_language": "en", "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "evidence_class": "C2", "specificity": "exact"}, ["occupation:broad_occupation", "occupation:detailed_occupation"])

# ----------------------------------------------------------------------------------------------------------------------------------------- multilingual
ML = [("en", "syn g multi"), ("de", "syn g mehrfach"), ("fr", "syn g multiple fr"), ("es", "syn g multiple es"), ("pt", "syn g multiplo"), ("it", "syn g multiplo it"), ("nl", "syn g meervoudig"), ("ru", "синт g мульти"), ("fr", "syn g café")]
scen("g_ml", "multilingual official titles", [(S, E, us(401))], [{"text": t, "language": lng} for lng, t in ML], [rec("fx_g_us", S, E, us(401), "detailed", "US", CUR, "annual", "median", "61000")])
for lng, t in ML[:8]:
    case(f"ml-title-{lng}", "multilingual", "g_ml", {"title": t, "title_language": lng, "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "61000"}, ["multilingual:official_title", "multilingual:authorised_alias"])
case("ml-accent-folding", "multilingual", "g_ml", {"title": "syn g cafe", "title_language": "fr", "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "61000"}, ["multilingual:accent_normalisation"])
case("ml-title-only-in-other-language-is-not-found", "multilingual", "g_ml", {"title": "syn g mehrfach", "title_language": "en", "country": "US"}, {"outcome": "not_found", "no_value": True}, ["multilingual:unsupported_translation", "multilingual:no_lexical_equivalence"])
case("ml-cross-language-needs-opt-in", "multilingual", "g_ml", {"title": "syn g mehrfach", "title_language": "en", "allow_cross_language": True, "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "61000"}, ["multilingual:ambiguous_translation"])
case("ml-unsupported-language", "multilingual", "g_ml", {"title": "syn g multi", "title_language": "zh", "country": "US"}, {"outcome": "unsupported", "no_value": True}, ["multilingual:unsupported_translation"])
case("ml-language-never-selects-the-country", "multilingual", "g_ml", {"title": "syn g multiple es", "title_language": "es", "country": "MX", "measure": "median", "pay_period": "annual"}, {"outcome": "abstain", "abstention": "no_evidence_for_occupation_in_country", "no_value": True}, ["multilingual:incorrect_language_country_assumption"])
case("ml-spanish-title-us-country-keeps-us", "multilingual", "g_ml", {"title": "syn g multiple es", "title_language": "es", "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "61000", "currency": "USD"}, ["multilingual:incorrect_language_country_assumption"])
scen("g_ml_fa", "false friend A (English meaning)", [(S, E, us(402))], [{"text": "syn g pie", "language": "en"}], [rec("fx_g_us", S, E, us(402), "detailed", "US", CUR, "annual", "median", "40000")])
scen("g_ml_fb", "false friend B (French meaning)", [(S, E, us(403))], [{"text": "syn g pie", "language": "fr"}], [rec("fx_g_us", S, E, us(403), "detailed", "US", CUR, "annual", "median", "70000")])
case("ml-false-friend-english", "multilingual", "g_ml_fa", {"title": "syn g pie", "title_language": "en", "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "40000"}, ["multilingual:cross_language_collision"])
case("ml-false-friend-french", "multilingual", "g_ml_fb", {"title": "syn g pie", "title_language": "fr", "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "70000"}, ["multilingual:cross_language_collision"])
case("ml-false-friend-without-language-is-ambiguous", "multilingual", "g_ml_fa", {"title": "syn g pie", "country": "US"}, {"outcome": "ambiguous", "no_value": True}, ["multilingual:cross_language_collision", "multilingual:ambiguous_translation"])
scen("g_ml_unk", "alias with unrecorded language", [(S, E, us(404))], [{"text": "syn g unknown language", "language": None}], [rec("fx_g_us", S, E, us(404), "detailed", "US", CUR, "annual", "median", "45000")])
case("ml-unverified-language-alias-needs-context", "multilingual", "g_ml_unk", {"title": "syn g unknown language", "title_language": "en", "country": "US"}, {"outcome": "insufficient_context", "no_value": True}, ["multilingual:unqualified_mapping"])
case("ml-unverified-language-alias-opt-in", "multilingual", "g_ml_unk", {"title": "syn g unknown language", "title_language": "en", "accept_unverified_language": True, "country": "US", "measure": "median", "pay_period": "annual"}, {"outcome": "evidence", "value": "45000"}, ["multilingual:unqualified_mapping"])


def build() -> dict:
    taxonomies = {}
    for _, (cc, scheme, ed, pattern, *_r) in JUR.items():
        taxonomies[(scheme, ed)] = pattern
    taxonomies[("soc", "2010")] = "[0-9]{2}-[0-9]{4}"
    taxonomies[("uk_soc", "2020")] = "[0-9]{1,4}"
    sources = [{"source_id": sid, "publisher": f"Synthetic {name} (fixture)", "dataset_name": f"Synthetic table {sid}", "source_url": f"https://example.invalid/{sid}", "precedence_category": cat} for sid, name, cat in SOURCES]
    sources.append({"source_id": "fx_g_unattrib", "publisher": None, "dataset_name": None, "source_url": None, "precedence_category": NAT})
    sources.append({"source_id": "fx_occ", "publisher": "Synthetic occupation labels (fixture)", "dataset_name": "Synthetic alias fixture", "source_url": None, "precedence_category": "unknown"})
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case id"
    tags = sorted({t for c in CASES for t in c["tags"]})
    return {"schema": "p10c-g/1", "corpus_version": VERSION, "note": "SYNTHETIC global evaluation corpus (P10C-G). Every source, occupation, alias and amount is invented; every source is a synthetic fixture that can never be approved or serve as evidence. Jurisdictions are evaluation jurisdictions, not claims that official data is qualified. No network, no clock, no randomness.",
            "taxonomies": [{"scheme": s, "edition": e, "status": "unknown", "acquisition_status": "not_acquired", "code_pattern": p} for (s, e), p in sorted(taxonomies.items())],
            "sources": sources, "source_editions": EDITIONS, "scenarios": SCENARIOS, "cases": CASES, "tags": tags}


def main(argv=None) -> int:
    text = json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    if argv and "--check" in argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("global corpus is up to date" if ok else "global corpus differs from the generator output")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(CASES)} cases, {len(SCENARIOS)} scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
