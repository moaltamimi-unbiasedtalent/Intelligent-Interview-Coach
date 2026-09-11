"""Phase 7A.1 specialized schemas, canonical-ID stability, and dimension separation.

Covers CompensationRecord / LabourMarketRecord / CredentialRecord / OccupationCrosswalk,
the source-quality category, requirement-level vs seniority, and the critical canonical-ID
persistence invariant (adding a richer classification later must NOT mutate an assigned id).
Deterministic; no network; no provider calls.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.copilot.knowledge import canonical as c


# --- canonical-ID persistence (§21) ------------------------------------------

def test_registry_keeps_id_stable_when_richer_classification_added():
    reg = c.CanonicalIdRegistry()
    first = reg.resolve_or_assign(isco_code="2511")               # seen with ISCO only
    later = reg.resolve_or_assign(isco_code="2511", esco_uri="http://x/esco/1")  # ESCO added
    assert first == later, "canonical id must not change when a richer crosswalk appears"
    # The bare derivation WOULD differ (ESCO has higher precedence) — the registry prevents it.
    assert c.canonical_occupation_id(isco_code="2511", esco_uri="http://x/esco/1") != first
    # Lookup by the newly-added key resolves to the same id.
    assert reg.get(esco_uri="http://x/esco/1") == first


def test_registry_assigns_distinct_ids_to_distinct_occupations():
    reg = c.CanonicalIdRegistry()
    a = reg.resolve_or_assign(onet_soc_code="15-2051.00")
    b = reg.resolve_or_assign(onet_soc_code="29-1141.00")
    assert a != b


def test_registry_round_trips(tmp_path):
    reg = c.CanonicalIdRegistry()
    oid = reg.resolve_or_assign(esco_uri="http://x/esco/9")
    p = tmp_path / "reg.json"
    reg.save(p)
    reloaded = c.CanonicalIdRegistry.load(p)
    assert reloaded.get(esco_uri="http://x/esco/9") == oid


# --- requirement level vs seniority (§23) ------------------------------------

def test_requirement_level_and_seniority_are_separate_dimensions():
    assert c.RequirementLevel.SKILLED.value == "skilled"
    assert c.Seniority.SENIOR.value == "senior"
    # They are different enums — a value from one is not a member of the other.
    with pytest.raises(ValueError):
        c.Seniority("skilled")
    with pytest.raises(ValueError):
        c.RequirementLevel("senior")


# --- source quality category (§28) -------------------------------------------

def test_source_quality_is_categorical_not_numeric():
    assert c.SourceQualityCategory.OFFICIAL_STATISTICS.value == "official_statistics"
    assert c.SourceQualityCategory.AUTHORIZED_MARKET_API.value == "authorized_market_api"
    with pytest.raises(ValueError):
        c.SourceQualityCategory("0.9")


# --- CompensationRecord (§16/§17) --------------------------------------------

def test_compensation_record_keeps_semantics_distinct():
    observed = c.CompensationRecord(
        compensation_id="de-obs", country="de", currency="eur", amount=65000,
        statistic=c.CompensationStatistic.MEDIAN, pay_period=c.PayPeriod.YEAR,
        gross_net=c.GrossNet.GROSS, compensation_type=c.CompensationType.OBSERVED_EARNINGS,
        effective_year=2025, source="destatis", source_record_id="62361-0034",
        source_quality=c.SourceQualityCategory.OFFICIAL_STATISTICS)
    advertised = c.CompensationRecord(
        compensation_id="de-adv", country="DE", currency="EUR",
        compensation_type=c.CompensationType.ADVERTISED_SALARY, source="adzuna",
        source_record_id="job-1", source_quality=c.SourceQualityCategory.AUTHORIZED_MARKET_API)
    assert observed.compensation_type != advertised.compensation_type
    assert observed.statistic == c.CompensationStatistic.MEDIAN  # never conflated with mean
    assert observed.country == "DE" and observed.currency == "EUR"


def test_compensation_rejects_non_canonical_occupation_id():
    with pytest.raises(ValidationError):
        c.CompensationRecord(compensation_id="x", occupation_id="onet:15-2051.00",
                             compensation_type=c.CompensationType.OBSERVED_EARNINGS,
                             source="bls_oews", source_record_id="r")


# --- LabourMarketRecord (§18) ------------------------------------------------

def test_labour_market_record_typed_metric():
    r = c.LabourMarketRecord(labour_market_id="lm1", country="DE",
                             metric_type=c.MetricType.VACANCIES, value=1200.0, unit="count",
                             source="eurostat_occ_vacancy", source_record_id="r")
    assert r.metric_type == c.MetricType.VACANCIES
    with pytest.raises(ValidationError):
        c.LabourMarketRecord(labour_market_id="lm", metric_type="jobs_maybe",
                             source="x", source_record_id="r")


# --- CredentialRecord (§19) --------------------------------------------------

def test_credential_record():
    cr = c.CredentialRecord(credential_id="rn-de", name="Registered Nurse licence",
                            credential_type=c.CredentialType.LICENCE, country="DE",
                            required=True, regulated_profession=True,
                            source="anerkennung", source_record_id="r")
    assert cr.regulated_profession and cr.credential_type == c.CredentialType.LICENCE


# --- OccupationCrosswalk (§20) -----------------------------------------------

def test_crosswalk_same_isco_group_is_not_exact():
    xw = c.OccupationCrosswalk(
        crosswalk_id="x1", source_occupation_id="ask4mo:occ:aaa", target_occupation_id="isco:2511",
        source_classification=c.ClassificationScheme.ONET_SOC,
        target_classification=c.ClassificationScheme.ISCO,
        source_code="15-1252.00", target_code="2511",
        mapping_type=c.MappingType.BROADER, source="onet")
    assert xw.mapping_type == c.MappingType.BROADER  # broad taxonomy ≠ exact identity
    with pytest.raises(ValidationError):
        c.OccupationCrosswalk(crosswalk_id="x", source_occupation_id="a", target_occupation_id="b",
                              source_classification=c.ClassificationScheme.ISCO,
                              target_classification=c.ClassificationScheme.SOC,
                              source_code="1", target_code="2", mapping_type="same")  # bad enum
