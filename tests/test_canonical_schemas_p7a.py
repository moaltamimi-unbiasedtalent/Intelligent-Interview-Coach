"""Canonical knowledge-build schema contract (Phase 7A).

Validates the build-layer data contract in ``src/copilot/knowledge/canonical.py``: stable
canonical identity, typed context dimensions, provenance-aware records, confidence
semantics, curated-source governance, build metadata, and JSONL/Parquet round-trips.

Deterministic, no network, no provider calls, no dependency on the user's downloaded
datasets (all fixtures are synthetic).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.copilot.knowledge import canonical as c


# --- canonical identity (§8) -------------------------------------------------

def test_canonical_id_is_stable_and_scheme_prefixed():
    a = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    assert a.startswith("ask4mo:occ:")
    assert a == c.canonical_occupation_id(onet_soc_code="15-2051.00")  # deterministic


def test_canonical_id_precedence_prefers_stable_classification():
    # Adding a lower-precedence ISCO code must not change an ONET-derived id.
    onet_only = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    onet_plus_isco = c.canonical_occupation_id(onet_soc_code="15-2051.00", isco_code="2511")
    assert onet_only == onet_plus_isco
    # A different scheme yields a different id.
    assert c.canonical_occupation_id(esco_uri="http://x/esco/occ/1") != onet_only


def test_canonical_id_falls_back_to_source_native_then_refuses_fabrication():
    native = c.canonical_occupation_id(source="berufenet", source_occupation_id="12345")
    assert native.startswith("ask4mo:occ:")
    with pytest.raises(ValueError):
        c.canonical_occupation_id()  # no key at all → never fabricate


# --- context dimensions (§15 geography, §16 temporal, §17 seniority) ---------

def test_geography_normalizes_country_and_is_structured():
    g = c.Geography(geography_type="state", country="us", state="CA")
    assert g.country == "US" and g.geography_type == c.GeographyType.STATE


def test_temporal_distinguishes_reference_year_from_retrieval():
    t = c.TemporalMetadata(source_version="OEWS 2025", reference_year=2025,
                           retrieved_at="2026-01-15", effective_period="2025")
    assert t.reference_year == 2025 and str(t.retrieved_at) == "2026-01-15"
    with pytest.raises(ValidationError):
        c.TemporalMetadata(reference_year=1500)  # out of bounds


def test_seniority_enum_membership():
    assert c.Seniority("senior") == c.Seniority.SENIOR
    with pytest.raises(ValueError):
        c.Seniority("wizard")


# --- provenance + records (§14, §10, §13) ------------------------------------

def _sr() -> c.SourceRecord:
    return c.SourceRecord(
        source_record_id="onet:occ:15-2051.00", source="onet", record_type="occupation",
        source_identifier="15-2051.00", raw_file="data/raw/onet/31.0/Occupation Data.xlsx",
        source_fingerprint=c.SourceFingerprint(
            relative_path="data/raw/onet/31.0/Occupation Data.xlsx", hash="deadbeefcafe"),
    )


def test_source_fingerprint_rejects_absolute_paths():
    with pytest.raises(ValidationError):
        c.SourceFingerprint(relative_path="/Users/me/data/x.xlsx", hash="abcdef12")
    with pytest.raises(ValidationError):
        c.SourceRecord(source_record_id="r", source="onet", record_type="occupation",
                       raw_file="C:\\data\\x.xlsx")


def test_canonical_occupation_requires_canonical_id_prefix():
    oid = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    occ = c.CanonicalOccupation(occupation_id=oid, canonical_title="Data Scientist",
                                source="onet", onet_soc_code="15-2051.00",
                                source_record_id=_sr().source_record_id,
                                seniority=c.Seniority.SENIOR)
    assert occ.seniority == c.Seniority.SENIOR
    with pytest.raises(ValidationError):
        c.CanonicalOccupation(occupation_id="onet:15-2051.00", canonical_title="x",
                              source="onet", source_record_id="r")


def test_knowledge_fact_is_typed_and_attributed():
    oid = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    f = c.KnowledgeFact(fact_id="f1", occupation_id=oid, fact_type=c.FactType.SKILL,
                        fact_value="Python", source="onet", source_record_id="r",
                        confidence=c.ConfidenceBasis.SOURCE_DIRECT)
    assert f.fact_type == c.FactType.SKILL and f.confidence == c.ConfidenceBasis.SOURCE_DIRECT
    with pytest.raises(ValidationError):
        c.KnowledgeFact(fact_id="f", occupation_id=oid, fact_type="vibes",
                        fact_value="x", source="onet", source_record_id="r")


def test_schema_is_strict_extra_forbidden():
    with pytest.raises(ValidationError):
        c.Geography(country="US", unexpected_field=1)


# --- alias governance (§11, §12, §18) ----------------------------------------

def test_alias_relationship_typed():
    oid = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    a = c.OccupationAlias(alias="ML Engineer", normalized_alias=c.normalize_text("ML Engineer!"),
                          canonical_occupation_id=oid, source="onet", source_record_id="r",
                          relationship=c.AliasRelationship.ALTERNATIVE_TITLE)
    assert a.normalized_alias == "ml engineer"
    assert a.relationship == c.AliasRelationship.ALTERNATIVE_TITLE


def test_curated_manual_alias_must_declare_curated_source():
    oid = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    # curated confidence with an official source is rejected (no masquerading).
    with pytest.raises(ValidationError):
        c.OccupationAlias(alias="x", normalized_alias="x", canonical_occupation_id=oid,
                          source="onet", source_record_id="r",
                          confidence=c.ConfidenceBasis.CURATED_MANUAL)
    # curated confidence with the curated source is allowed.
    ok = c.OccupationAlias(alias="x", normalized_alias="x", canonical_occupation_id=oid,
                           source=c.ASK4MO_CURATED_SOURCE, source_record_id="r",
                           relationship=c.AliasRelationship.CURATED_ALIAS,
                           confidence=c.ConfidenceBasis.CURATED_MANUAL)
    assert ok.source == "ask4mo_curated"


# --- build metadata (§28) ----------------------------------------------------

def test_build_metadata_records_reproducibility_inputs():
    bm = c.BuildMetadata(manifest_version=1, pipeline_version="7b.0",
                         git_commit="abc123", source_versions={"onet": "31.0"},
                         source_checksums=[c.SourceFingerprint(
                             relative_path="data/raw/onet/31.0/Occupation Data.xlsx", hash="deadbeef")],
                         record_counts={"occupations": 1016})
    assert bm.canonical_schema_version == c.CANONICAL_SCHEMA_VERSION
    assert '"source_versions"' in bm.to_json()


# --- serialization round-trips (§9, §19) -------------------------------------

def _occ() -> c.CanonicalOccupation:
    oid = c.canonical_occupation_id(onet_soc_code="15-2051.00")
    return c.CanonicalOccupation(
        occupation_id=oid, canonical_title="Data Scientist", source="onet",
        onet_soc_code="15-2051.00", source_record_id="r", seniority=c.Seniority.SENIOR,
        geography=c.Geography(country="US"),
        classifications=[c.ClassificationRef(scheme=c.ClassificationScheme.ONET_SOC, code="15-2051.00")])


def test_jsonl_round_trip(tmp_path):
    p = tmp_path / "occ.jsonl"
    assert c.write_jsonl([_occ()], p) == 1
    back = c.read_jsonl(p, c.CanonicalOccupation)
    assert back[0].occupation_id == _occ().occupation_id
    assert back[0].classifications[0].code == "15-2051.00"


def test_parquet_round_trip_when_available(tmp_path):
    pytest.importorskip("pyarrow")
    p = tmp_path / "occ.parquet"
    assert c.write_parquet([_occ()], p) == 1
    back = c.read_parquet(p, c.CanonicalOccupation)
    assert back[0].geography.country == "US"
    assert back[0].seniority == c.Seniority.SENIOR
