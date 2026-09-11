"""Phase 7B — canonical normalization mappers + build orchestration.

Covers the source→canonical mapping (``knowledge/normalize.py``) and the build orchestrator
(``scripts/knowledge/build_normalized_knowledge.py``) with SMALL synthetic fixtures — never
the full 462MB raw tree. Deterministic; no network; no provider calls; nothing touches the
runtime knowledge/Chroma stores.

Exercises: canonical-id stability + no ISCO-group merge, ESCO per-alias parsing, fact typing,
crosswalk priority, alias ambiguity (one alias → many occupations), provenance completeness,
compensation semantics (weekly never annualised; unknown-currency rejection), labour-market
geography classification (EU aggregate ≠ country; NUTS region ≠ country), requirement-level vs
seniority separation, dedup, Parquet round-trip, build metadata + idempotent rebuild + rejections.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from src.copilot.knowledge import canonical as C
from src.copilot.knowledge import normalize as N
from src.copilot.knowledge.compensation import CompensationRecord as SrcComp
from src.copilot.knowledge.roles import Mapping, NormalisedOccupation, Skill
from src.copilot.knowledge.structured_ext import (
    Competency,
    LabourForecast,
    LabourShortage,
    LabourVacancy,
)

_ROOT = Path(__file__).resolve().parent.parent


def _load_builder():
    path = _ROOT / "scripts" / "knowledge" / "build_normalized_knowledge.py"
    spec = importlib.util.spec_from_file_location("build_normalized_knowledge", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_normalized_knowledge"] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------------
# Occupation mapping
# --------------------------------------------------------------------------------------

def _esco(uri="http://data.europa.eu/esco/occupation/x", title="Data Scientist",
          isco="2511", aliases=None, skills=None):
    return NormalisedOccupation(
        occupation_code=uri, title=title, source_id="esco", isco_code=isco,
        aliases=aliases if aliases is not None else ["data analyst", "ML engineer"],
        skills=skills if skills is not None else [Skill(name="Python", skill_type="technology"),
                                                  Skill(name="statistics", skill_type="essential")],
        knowledge=["mathematics"], tasks=["build models"], activities=["analyse data"],
        entry_education="Bachelor's degree",
        mappings=[Mapping(scheme="isco", code=isco)] if isco else [])


def test_esco_occupation_maps_to_canonical_with_typed_facts():
    reg = C.CanonicalIdRegistry()
    occ = _esco()
    can, aliases, facts, xwalks, srec = N.occupation_to_canonical(occ, reg, raw_file="data/raw/esco/x.csv")
    assert can.occupation_id.startswith("ask4mo:occ:")
    assert can.esco_uri == occ.occupation_code and can.isco_code == "2511"
    ftypes = {(f.fact_type, f.fact_value) for f in facts}
    assert (C.FactType.TECHNOLOGY_SKILL, "Python") in ftypes
    assert (C.FactType.SKILL, "statistics") in ftypes
    assert (C.FactType.KNOWLEDGE, "mathematics") in ftypes
    assert (C.FactType.TASK, "build models") in ftypes
    assert (C.FactType.WORK_ACTIVITY, "analyse data") in ftypes
    assert (C.FactType.EDUCATION, "Bachelor's degree") in ftypes
    assert srec.record_type == "occupation" and srec.raw_file == "data/raw/esco/x.csv"


def test_esco_aliases_are_parsed_per_alias_not_one_blob():
    reg = C.CanonicalIdRegistry()
    occ = _esco(aliases=["data analyst", "ML engineer", "quant"])
    _, aliases, *_ = N.occupation_to_canonical(occ, reg)
    values = sorted(a.alias for a in aliases)
    assert values == ["ML engineer", "data analyst", "quant"]
    # every alias is a first-class OccupationAlias row (§11), typed as an alternative title.
    assert all(a.relationship == C.AliasRelationship.ALTERNATIVE_TITLE for a in aliases)
    # source aliases are NOT curated (§12).
    assert all(a.source == "esco" and a.source != C.ASK4MO_CURATED_SOURCE for a in aliases)


def test_alias_normalization_dedupes_within_one_occupation():
    reg = C.CanonicalIdRegistry()
    occ = _esco(aliases=["Data Analyst", "data analyst", " data  analyst "])
    _, aliases, *_ = N.occupation_to_canonical(occ, reg)
    assert len(aliases) == 1  # same normalized form collapses


def test_canonical_id_stable_and_no_isco_group_merge():
    """Occupations sharing a broad ISCO group must NOT collapse to one id (§32/§34)."""
    reg = C.CanonicalIdRegistry()
    esco = _esco(uri="http://esco/a", isco="2511")
    onet = NormalisedOccupation(occupation_code="15-2051.00", title="Data Scientists",
                                source_id="onet", isco_code="2511")
    isco = NormalisedOccupation(occupation_code="2511", title="ICT professionals",
                                source_id="isco08", isco_code="2511")
    ids = {N.occupation_to_canonical(o, reg)[0].occupation_id for o in (esco, onet, isco)}
    assert len(ids) == 3, "shared ISCO unit group must not merge distinct occupations"
    # id is stable across a re-map (idempotent), even though ESCO outranks ISCO in derivation.
    again = N.occupation_to_canonical(esco, reg)[0].occupation_id
    assert again in ids


def test_crosswalk_is_official_and_cross_scheme_only():
    reg = C.CanonicalIdRegistry()
    occ = _esco(isco="2511")
    _, _, _, xwalks, _ = N.occupation_to_canonical(occ, reg)
    assert len(xwalks) == 1
    xw = xwalks[0]
    assert xw.source_classification == C.ClassificationScheme.ESCO
    assert xw.target_classification == C.ClassificationScheme.ISCO
    assert xw.official_mapping is True and xw.mapping_type == C.MappingType.EXACT
    # An occupation with no cross-scheme mapping yields no crosswalk (no fabricated links).
    plain = NormalisedOccupation(occupation_code="2511", title="x", source_id="isco08", isco_code="2511")
    assert N.occupation_to_canonical(plain, reg)[3] == []


def test_alias_ambiguity_one_alias_maps_to_multiple_occupations():
    """The same alias string can point at two different canonical occupations (§35)."""
    reg = C.CanonicalIdRegistry()
    a = _esco(uri="http://esco/a", title="Data Scientist", isco="2511", aliases=["analyst"])
    b = _esco(uri="http://esco/b", title="Business Analyst", isco="2421", aliases=["analyst"])
    _, aa, *_ = N.occupation_to_canonical(a, reg)
    _, ab, *_ = N.occupation_to_canonical(b, reg)
    targets = {aa[0].canonical_occupation_id, ab[0].canonical_occupation_id}
    assert aa[0].normalized_alias == ab[0].normalized_alias == "analyst"
    assert len(targets) == 2  # ambiguity preserved, not collapsed


def test_every_fact_and_occupation_carries_provenance():
    reg = C.CanonicalIdRegistry()
    can, aliases, facts, _, srec = N.occupation_to_canonical(
        _esco(), reg, source_meta={"source_url": "http://x", "license": "CC-BY"})
    assert can.source and can.source_record_id
    assert all(f.source and f.source_record_id for f in facts)
    assert all(al.source and al.source_record_id for al in aliases)
    assert can.source_url == "http://x" and can.license == "CC-BY"


# --------------------------------------------------------------------------------------
# Compensation semantics
# --------------------------------------------------------------------------------------

def test_weekly_pay_is_not_annualised_and_native_period_retained():
    reg = C.CanonicalIdRegistry()
    ashe = SrcComp(source_id="ons_ashe", occupation_code="2136", geography="UK", country="UK",
                   year=2025, currency="GBP", pay_period="weekly", statistic_type="median", value=780.0)
    rec, rej = N.compensation_to_canonical(ashe, reg)
    assert rej is None
    assert rec.pay_period == C.PayPeriod.WEEK          # never silently converted to YEAR
    assert rec.amount == 780.0                          # value unchanged
    assert rec.metadata["pay_period_native"] == "weekly"
    assert rec.compensation_type == C.CompensationType.OBSERVED_EARNINGS


def test_hourly_and_annual_are_distinct_and_preserved():
    reg = C.CanonicalIdRegistry()
    hourly = SrcComp(source_id="bls_oews", occupation_code="15-1252", geography="US", country="US",
                     year=2025, currency="USD", pay_period="hourly", statistic_type="mean", value=61.5)
    annual = SrcComp(source_id="bls_oews", occupation_code="15-1252", geography="US", country="US",
                     year=2025, currency="USD", pay_period="annual", statistic_type="median", value=128000.0)
    rh, _ = N.compensation_to_canonical(hourly, reg)
    ra, _ = N.compensation_to_canonical(annual, reg)
    assert rh.pay_period == C.PayPeriod.HOUR and ra.pay_period == C.PayPeriod.YEAR
    assert rh.statistic == C.CompensationStatistic.MEAN
    assert ra.statistic == C.CompensationStatistic.MEDIAN
    assert rh.compensation_id != ra.compensation_id


def test_compensation_missing_currency_or_value_is_rejected():
    reg = C.CanonicalIdRegistry()
    no_cur = SrcComp(source_id="bls_oews", occupation_code="x", currency="", value=1.0)
    no_val = SrcComp(source_id="bls_oews", occupation_code="x", currency="USD", value=None)
    assert N.compensation_to_canonical(no_cur, reg) == (None, "unknown_currency")
    assert N.compensation_to_canonical(no_val, reg) == (None, "invalid_amount")


# --------------------------------------------------------------------------------------
# Labour-market geography (§57)
# --------------------------------------------------------------------------------------

def test_eu_aggregate_is_never_a_country():
    r = N.labour_shortage_to_canonical(
        LabourShortage(source_id="cedefop_clssi", occupation="ICT", country="EU27",
                       shortage_indicator="CLSSI 3.8 (high shortage)", period="2026"))
    assert r.country is None
    assert r.geography_type == C.GeographyType.REGION
    assert r.metadata["geography_label"] == "EU27"


def test_country_name_resolves_but_nuts_region_stays_region():
    country = N.labour_vacancy_to_canonical(
        LabourVacancy(source_id="eurostat_occ_vacancy", occupation="Total", country="Germany",
                      year=2024, indicator="Job vacancy rate", unit="Percentage", value=4.2))
    region = N.labour_vacancy_to_canonical(
        LabourVacancy(source_id="eurostat_occ_vacancy", occupation="Total", country="Bayern",
                      year=2024, indicator="Job vacancy rate", unit="Percentage", value=3.9))
    assert country.country == "DE" and country.geography_type == C.GeographyType.COUNTRY
    assert region.country is None and region.region == "Bayern"       # region, never rolled into DE
    assert region.geography_type == C.GeographyType.REGION


def test_forecast_keeps_native_fraction_and_period():
    r = N.labour_forecast_to_canonical(
        LabourForecast(source_id="bls_projections", occupation="Data Scientists", country="US",
                       employment_change=0.36, horizon="2025-2035", reference_year=2025))
    assert r.metric_type == C.MetricType.GROWTH_RATE and r.value == 0.36
    assert r.country == "US" and r.forecast_period == "2025-2035"


# --------------------------------------------------------------------------------------
# Requirement level vs seniority (regression, §23) + dedup + round-trip
# --------------------------------------------------------------------------------------

def test_requirement_level_and_seniority_never_conflated():
    # The mapper never invents either dimension, and the enums remain disjoint.
    reg = C.CanonicalIdRegistry()
    can, *_ = N.occupation_to_canonical(_esco(), reg)
    assert can.seniority is None  # not fabricated from a title
    with pytest.raises(ValueError):
        C.Seniority("skilled")     # a requirement level is not a seniority
    with pytest.raises(ValueError):
        C.RequirementLevel("senior")


def test_dedupe_is_order_preserving_and_deterministic():
    items = [("a", 1), ("b", 2), ("a", 3), ("c", 4), ("b", 5)]
    out = N.dedupe(items, key=lambda x: x[0])
    assert out == [("a", 1), ("b", 2), ("c", 4)]


def test_parquet_round_trip_for_each_record_type(tmp_path):
    reg = C.CanonicalIdRegistry()
    can, aliases, facts, xwalks, srec = N.occupation_to_canonical(_esco(), reg)
    comp, _ = N.compensation_to_canonical(
        SrcComp(source_id="bls_oews", occupation_code="15-1252", country="US", geography="US",
                year=2025, currency="USD", pay_period="annual", statistic_type="median", value=1.0), reg)
    lm = N.labour_forecast_to_canonical(
        LabourForecast(source_id="bls_projections", occupation="x", country="US",
                       employment_change=0.1, horizon="2025-2035", reference_year=2025))
    cases = [("occ", [can], C.CanonicalOccupation), ("al", aliases, C.OccupationAlias),
             ("fact", facts, C.KnowledgeFact), ("xw", xwalks, C.OccupationCrosswalk),
             ("sr", [srec], C.SourceRecord), ("comp", [comp], C.CompensationRecord),
             ("lm", [lm], C.LabourMarketRecord)]
    for name, recs, model in cases:
        p = tmp_path / f"{name}.parquet"
        try:
            C.write_parquet(recs, p)
        except C.ParquetUnavailableError:
            pytest.skip("pyarrow not installed")
        back = C.read_parquet(p, model)
        assert [r.model_dump() for r in back] == [r.model_dump() for r in recs]


# --------------------------------------------------------------------------------------
# Build orchestrator on tiny fixtures (no real raw tree)
# --------------------------------------------------------------------------------------

def _fixture_sources(bnk):
    """A small in-memory source registry for the orchestrator."""
    def occ_reader():
        return [_esco(uri="http://esco/a", title="Data Scientist", isco="2511"),
                _esco(uri="http://esco/b", title="Nurse", isco="2221", aliases=["RN"])]

    def comp_reader():
        return [SrcComp(source_id="bls_oews", occupation_code="15-1252", country="US",
                        geography="US", year=2025, currency="USD", pay_period="annual",
                        statistic_type="median", value=128000.0)]

    def lm_reader():
        return ([LabourForecast(source_id="bls_projections", occupation="Data Scientists",
                                country="US", employment_change=0.36, horizon="2025-2035",
                                reference_year=2025)],
                [])

    def comp_fw_reader():
        return [Competency(source_id="nice_framework", framework="NICE", area="Work Role",
                           name="Cyber Defense Analyst", description="Defends networks.")]

    return [
        bnk.SourceSpec("esco", "occupation", occ_reader, "data/raw/does-not-exist-esco.csv"),
        bnk.SourceSpec("bls_oews", "compensation", comp_reader, "data/raw/does-not-exist-oews.xlsx"),
        bnk.SourceSpec("bls_projections_lm", "labour_market", lm_reader, "data/raw/does-not-exist.xlsx"),
        bnk.SourceSpec("nice_framework", "competency", comp_fw_reader, "data/raw/does-not-exist.xlsx"),
    ]


def test_build_writes_partitioned_outputs_and_reports(tmp_path, monkeypatch):
    bnk = _load_builder()
    monkeypatch.setattr(bnk, "_sources", lambda: _fixture_sources(bnk))
    out = tmp_path / "normalized"
    result = bnk.build([], output_dir=str(out), validate_only=False)

    assert result.counts["occupations"] == 2
    assert result.counts["occupation_crosswalks"] == 2      # both have ISCO mappings
    assert result.counts["compensation"] == 1
    assert result.counts["labour_market"] == 1
    assert result.counts["competencies"] == 1
    # partitioned fact files exist only where there is data (no empty placeholders).
    assert (out / "occupations.parquet").exists()
    assert (out / "occupation_skills.parquet").exists()
    assert not (out / "abilities.parquet").exists()
    # reports + registry.
    for name in ("build_metadata.json", "canonicalization_report.json",
                 "normalization_rejections.json", "canonical_registry.json"):
        assert (out / name).exists(), name
    meta = json.loads((out / "build_metadata.json").read_text())
    assert meta["pipeline_version"] == bnk.PIPELINE_VERSION
    assert meta["record_counts"]["occupations"] == 2


def test_build_is_idempotent(tmp_path, monkeypatch):
    bnk = _load_builder()
    monkeypatch.setattr(bnk, "_sources", lambda: _fixture_sources(bnk))
    a, b = tmp_path / "a", tmp_path / "b"
    bnk.build([], output_dir=str(a), validate_only=False)
    bnk.build([], output_dir=str(b), validate_only=False)
    for name, model in (("occupations", C.CanonicalOccupation),
                        ("occupation_aliases", C.OccupationAlias),
                        ("compensation", C.CompensationRecord),
                        ("labour_market", C.LabourMarketRecord)):
        pa, pb = a / f"{name}.parquet", b / f"{name}.parquet"
        if not pa.exists():
            continue
        ra = [r.model_dump() for r in C.read_parquet(pa, model)]
        rb = [r.model_dump() for r in C.read_parquet(pb, model)]
        assert ra == rb, f"{name} not reproducible"
    assert json.loads((a / "canonical_registry.json").read_text()) == \
        json.loads((b / "canonical_registry.json").read_text())


def test_build_records_rejections_without_silent_drops(tmp_path, monkeypatch):
    bnk = _load_builder()

    def sources():
        def bad_comp():
            return [SrcComp(source_id="bls_oews", occupation_code="x", currency="", value=1.0)]
        return [bnk.SourceSpec("bls_oews", "compensation", bad_comp, "data/raw/none.xlsx")]

    monkeypatch.setattr(bnk, "_sources", sources)
    out = tmp_path / "n"
    result = bnk.build([], output_dir=str(out), validate_only=False)
    assert result.counts.get("compensation", 0) == 0
    rej = json.loads((out / "normalization_rejections.json").read_text())
    assert rej["total"] == 1 and rej["records"][0]["reason"] == "unknown_currency"


def test_validate_only_does_not_write_outputs(tmp_path, monkeypatch):
    bnk = _load_builder()
    monkeypatch.setattr(bnk, "_sources", lambda: _fixture_sources(bnk))
    out = tmp_path / "n"
    result = bnk.build([], output_dir=str(out), validate_only=True)
    assert result.counts["occupations"] == 2
    assert not out.exists()  # validate-only writes nothing
