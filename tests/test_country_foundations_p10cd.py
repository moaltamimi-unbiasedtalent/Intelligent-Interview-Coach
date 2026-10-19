"""P10C-D: Canada (GKB-8), Mexico (GKB-9) and Brazil (GKB-10) foundations. FULLY OFFLINE: throwaway SQLite databases and the committed SYNTHETIC corpus (invented editions fx-ed1 and fx-ed2,
invented codes, labels and amounts in synthetic-fixture sources that can never be approved). Nothing here is a real taxonomy, dataset, figure or approval, and nothing is imported by a
candidate-facing path or changes a gate."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from src.knowledge_foundation import readiness as RD
from src.knowledge_foundation.aliases import AliasStore
from src.knowledge_foundation.compensation import country_adapters as CA
from src.knowledge_foundation.compensation.countries import PROFILES, normalize_region, profile_for
from src.knowledge_foundation.compensation.country_fixtures import CORPUS_PATH, evaluate_blocks, evaluate_cases, load_corpus, load_world
from src.knowledge_foundation.compensation.country_import import CountryImportNotApproved, import_crosswalk, import_taxonomy_nodes
from src.knowledge_foundation.compensation.money import validate_currency
from src.knowledge_foundation.compensation.policy import PrecedencePolicy, classify_evidence
from src.knowledge_foundation.compensation.record import CompensationRecordV2, record_key_for
from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest
from src.knowledge_foundation.compensation.store import CompensationStoreV2
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.occupation_resolver import MultilingualRequest
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
from src.persistence import CompensationRecordV2Row, init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
MAPS = dict(statistic_map={"MED": ("median", 0), "P10": ("percentile", 10)}, period_map={"HR": "hourly", "MES": "monthly", "YR": "annual"})


@pytest.fixture()
def sf(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'd.db'}")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture()
def world(sf):
    return load_world(sf)


@pytest.fixture()
def sandbox(sf):
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    tax.ensure("noc", "fx-a", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{5}")
    tax.ensure("noc", "fx-b", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{5}")
    reg.register("fx_tax", origin="synthetic_fixture", publisher="P", dataset_name="D")
    reg.register("real_tax", origin="official_local", publisher="P", dataset_name="D", precedence_category="national_official_occupation_statistics", validation_status="unvalidated")
    return type("NS", (), dict(sf=sf, tax=tax, reg=reg, g=g, a=AliasStore(sf), store=CompensationStoreV2(sf, reg, g)))


def approve(reg, sid, runtime=False):
    reg.set_licence(sid, licence_id="Synthetic licence", licence_status="verified", attribution_required="yes", redistribution="yes")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion") + (("approved_for_runtime_use",) if runtime else ()):
        reg.transition(sid, step)


# ====================================================================================================================================== readiness (GKB checkpoint)
def test_the_readiness_report_is_deterministic_and_matches_the_committed_artifact():
    a = RD.assess(ROOT)
    assert a == RD.assess(ROOT) and a == json.loads((ROOT / "docs/capstone/p10/p10c_d/SOURCE_READINESS.json").read_text())
    assert set(a["countries"]) == {"US", "GB", "CA", "MX", "BR"} and "not completed country coverage" in a["note"]


def test_no_country_is_operational_and_every_blocker_has_an_owner_decision():
    a = RD.assess(ROOT)
    for c, v in a["countries"].items():
        assert v["operational_today"] is False and v["compensation_v2_records_linkable_today"] == 0 and v["approved_compensation_v2_sources"] == 0, c
        assert v["graph_nodes_for_taxonomy"] == 0 and v["crosswalk_held"] is False and v["taxonomy_edition_known"] is False and v["adapter_without_linkage_is_not_coverage"] is True
        assert all(b["decision"].startswith("D-") for b in v["blockers"]) and {b["kind"] for b in v["blockers"]} >= {"taxonomy_acquisition", "edition", "graph", "crosswalk", "licensing", "approval"}
        assert all(s["approval_status"] in ("licensing_pending", "restricted") and s["licence_status"] != "verified" for s in v["registry_sources"].values())
    assert a["countries"]["US"]["local_v1_records"] == 1386 and a["countries"]["GB"]["local_v1_records"] == 527 and a["countries"]["CA"]["local_v1_records"] == 0
    ids = {b["id"] for b in a["countries"]["US"]["blockers"]}
    assert {"US-D1", "US-D2", "US-T1", "US-G1", "US-X1"} <= ids and {"GB-D1", "GB-D2"} <= {b["id"] for b in a["countries"]["GB"]["blockers"]}
    assert [s["step"] for s in a["remediation_plan"]] == [1, 2, 3, 4, 5, 6] and a["remediation_plan"][0]["engineering_possible_now"] is False


def test_candidate_sources_are_names_only_with_every_other_fact_unknown():
    c = json.loads((ROOT / "src/knowledge_foundation/data/country_source_candidates.json").read_text())
    assert "CANDIDATE" in c["note"] and "UNKNOWN" in c["note"] and len(c["candidates"]) == 8
    assert {x["country"] for x in c["candidates"]} == {"CA", "MX", "BR"} and all("(candidate)" in x["publisher"] and "(candidate)" in x["dataset"] for x in c["candidates"])
    assert not {"licence", "taxonomy_edition", "dataset_edition", "approval_status"} & set(c["candidates"][0]) and {"licence", "taxonomy_edition", "reference_period", "pay_period", "gross_net_basis"} <= set(c["unknown_fields_for_every_candidate"])
    reg = {s["source_id"] for s in json.loads((ROOT / "src/knowledge_foundation/data/source_registry_baseline.json").read_text())["sources"]}
    assert not reg & {x["candidate_id"] for x in c["candidates"]}                                       # candidates are not silently registered, let alone approved


def test_the_readiness_script_validates_output_first_and_reads_no_local_store(tmp_path):
    import subprocess, sys
    for target in ("data/x.json", "evaluations/y.json"):
        r = subprocess.run([sys.executable, str(ROOT / "scripts/gkb8_source_readiness.py"), "--out", str(ROOT / target)], capture_output=True, text=True, cwd=tmp_path)
        assert r.returncode == 2 and "refusing" in r.stderr and not (ROOT / target).exists()
    out = tmp_path / "o/r.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/gkb8_source_readiness.py"), "--out", str(out)], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and json.loads(out.read_text())["countries"]["CA"]["operational_today"] is False


# ====================================================================================================================================== country profiles
def test_profiles_hold_only_non_data_facts_and_validate_regions_without_guessing():
    assert {c: (p.taxonomy_scheme, p.currency) for c, p in PROFILES.items()} == {"CA": ("noc", "CAD"), "MX": ("sinco", "MXN"), "BR": ("cbo", "BRL")}
    assert [len(PROFILES[c].regions) for c in ("CA", "MX", "BR")] == [13, 32, 27] and all(validate_currency(p.currency) for p in PROFILES.values())
    assert normalize_region("CA", "on") == "CA-ON" and normalize_region("CA", "CA-ON") == "CA-ON" and normalize_region("MX", " jal ") == "MX-JAL" and normalize_region("BR", "sp") == "BR-SP"
    for bad in ("Ontario", "ZZ", "", None, "MX-ON", "CA-SP"):
        assert normalize_region("CA", bad) is None
    assert normalize_region("DE", "BY") is None and normalize_region(None, "ON") is None and profile_for("us") is None and profile_for("br").name == "Brazil"
    assert "SP" not in PROFILES["CA"].regions and "ON" not in PROFILES["BR"].regions                           # no cross-country region leakage
    assert not hasattr(PROFILES["CA"], "edition") and not hasattr(PROFILES["CA"], "languages") and not hasattr(PROFILES["CA"], "code_pattern")        # editions, formats and languages come from evidence


# ====================================================================================================================================== adapters
def _rows(**kw):
    base = {"code": "90001", "statistic": "MED", "period": "HR", "value": "38.50"}
    base.update(kw)
    return [base]


def test_canada_keeps_hourly_hourly_and_provincial_separate_from_national():
    recs, rej = CA.canada_records(_rows() + _rows(region="ON", value="41.25") + _rows(region="CA-QC", value="39"), source_ref="s", source_edition="E", taxonomy_edition="fx-ed1", reference_year=2025,
                                  level_by_code_length={5: "detailed"}, **MAPS)
    by = {r.region: r for r in recs}
    assert not rej and by[None].geography_level == "national" and by["CA-ON"].geography_level == "regional" and by["CA-QC"].value == Decimal("39")
    assert all(r.pay_period == "hourly" and r.currency == "CAD" and r.country == "CA" and r.taxonomy_scheme == "noc" and r.earnings_concept == "unknown" for r in recs)
    assert not any(r.pay_period == "annual" for r in recs) and by["CA-ON"].occupation_level == "detailed"


def test_adapters_reject_what_they_cannot_represent_with_reason_codes():
    kw = dict(source_ref="s", source_edition="E", taxonomy_edition="fx-ed1", reference_year=2025, level_by_code_length={5: "detailed"}, **MAPS)
    rows = _rows(currency="USD") + _rows(region="XX") + _rows(statistic="AVG") + _rows(period="WK") + _rows(code="1234", ) + _rows(value="abc") + _rows(code=" ") + _rows(value="*") + _rows(value="0")
    recs, rej = CA.canada_records(rows, code_pattern="[0-9]{5}", **kw)
    assert dict(rej) == {"currency_mismatch": 1, "region_unrecognised": 1, "unsupported_statistic": 1, "unsupported_period": 1, "invalid_native_code": 1, "malformed_amount": 2, "missing_native_code": 1}
    assert len(recs) == 1 and recs[0].value_status == "suppressed" and recs[0].value is None                      # a marker is a status, never zero


def test_a_level_is_never_assumed_and_an_unclassifiable_row_is_rejected_at_import(sandbox):
    recs, _ = CA.canada_records(_rows(), source_ref="fx_tax", source_edition="E", taxonomy_edition="fx-a", reference_year=2025, **MAPS)        # no published level and no caller rule
    assert recs[0].occupation_level == "unknown"
    sandbox.reg.register("fx_c", origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_official_occupation_statistics")
    import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, [{"code": "90001", "label": "Synthetic"}], scheme="noc", edition="fx-a", source_ref="fx_tax", mode="fixture")
    rep = sandbox.store.import_records([r.model_copy(update={"source_ref": "fx_c"}) for r in recs], source_ref="fx_c", source_edition="E", mode="fixture")
    assert rep.added == 0 and rep.rejections == {"evidence_class_undeterminable": 1}


def test_mexico_and_brazil_require_the_earnings_definition_and_population():
    kw = dict(source_ref="s", source_edition="E", taxonomy_edition="fx-ed1", reference_year=2025, period_map={"MES": "monthly"}, statistic_map={"MED": ("median", 0)},
              concept_map={"IND": "individual_earnings", "HOG": "household_income", "SAL": "wage_statistic"}, population_map={"TODOS": "all_workers", "FORMAL": "formal_sector"},
              method_map={"ENC": "survey", "ADM": "administrative_records"})
    mx = [{"code": "9301", "statistic": "MED", "period": "MES", "value": "12000", "concept": "IND", "population": "TODOS", "method": "ENC"},
          {"code": "9301", "statistic": "MED", "period": "MES", "value": "1", "population": "TODOS", "method": "ENC"},
          {"code": "9301", "statistic": "MED", "period": "MES", "value": "1", "concept": "IND", "method": "ENC"},
          {"code": "9301", "statistic": "MED", "period": "MES", "value": "1", "concept": "ZZZ", "population": "TODOS", "method": "ENC"},
          {"code": "9301", "statistic": "MED", "period": "MES", "value": "1", "concept": "IND", "population": "TODOS", "method": "QQQ"}]
    recs, rej = CA.mexico_records(mx, **kw)
    assert len(recs) == 1 and recs[0].currency == "MXN" and recs[0].pay_period == "monthly" and recs[0].earnings_concept == "individual_earnings" and recs[0].evidence_method == "survey"
    assert dict(rej) == {"concept_missing": 1, "population_missing": 1, "concept_unmapped": 1, "method_unmapped": 1}
    br = [{"code": "2124-90", "statistic": "MED", "period": "MES", "value": "7000.50", "concept": "SAL", "population": "FORMAL", "method": "ADM"},
          {"code": "2124-90", "statistic": "MED", "period": "MES", "value": "7000", "concept": "SAL", "population": "FORMAL"}]
    recs, rej = CA.brazil_records(br, **kw)
    assert [r.native_code for r in recs] == ["2124-90"] and recs[0].currency == "BRL" and recs[0].value == Decimal("7000.50") and dict(rej) == {"method_missing": 1}          # the hyphenated code stays a string
    assert CA.canada_records(_rows(), source_ref="s", source_edition="E", taxonomy_edition="x", reference_year=2025, **MAPS)[0][0].earnings_concept == "unknown"     # Canada does not require it


def test_adapter_vocabulary_maps_are_validated_up_front():
    for bad in ({"concept_map": {"X": "salary_but_not_really"}}, {"population_map": {"X": "everyone"}}, {"method_map": {"X": "vibes"}}, {"period_map": {"HR": "fortnightly"}}):
        kw = {**dict(source_ref="s", source_edition="E", taxonomy_edition="x", reference_year=2025, **MAPS), **bad}
        with pytest.raises(ValueError):
            CA.mexico_records(_rows(), **kw)


def test_household_income_is_never_occupation_compensation():
    base = dict(taxonomy_scheme="sinco", taxonomy_edition="fx-ed1", native_code="9301", country="MX", currency="MXN", pay_period="monthly", measure="median", value=Decimal("1"),
                source_ref="s", source_edition="E", reference_year=2025)
    assert CompensationRecordV2(earnings_concept="household_income", **base).earnings_concept == "household_income"      # representable (an adapter may map it) ...
    from src.persistence import CompensationRecordV2Row as Row
    assert any(c.name == "ck_cv2_not_household_income" for c in Row.__table__.constraints)                                # ... but the database refuses to store it


# ====================================================================================================================================== importers and gates
def test_taxonomy_import_is_registry_gated_and_edition_aware(sandbox):
    rows = [{"code": "90001", "label": "Synthetic one", "labels": [{"text": "syn one", "language": "en"}, {"text": "syn un", "language": "fr"}]}, {"code": "9", "label": "bad code"}, {"code": "90002", "label": ""}]
    with pytest.raises(CountryImportNotApproved):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows, scheme="noc", edition="fx-a", source_ref="nope", mode="fixture")
    with pytest.raises(CountryImportNotApproved):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows, scheme="noc", edition="fx-a", source_ref="real_tax", mode="production")           # licensing pending
    with pytest.raises(CountryImportNotApproved):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows, scheme="noc", edition="fx-a", source_ref="fx_tax", mode="production")             # a synthetic source never
    with pytest.raises(CountryImportNotApproved):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows, scheme="noc", edition="fx-a", source_ref="real_tax", mode="fixture")              # fixture mode needs a synthetic source
    with pytest.raises(CountryImportNotApproved):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows, scheme="noc", edition="fx-zzz", source_ref="fx_tax", mode="fixture")              # edition not registered
    assert sandbox.g.counts()["occupations"] == 0
    rep = import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows, scheme="noc", edition="fx-a", source_ref="fx_tax", mode="fixture")
    assert (rep.added, rep.existing, rep.rejections) == (1, 0, {"invalid_native_code": 1, "missing_label": 1})
    assert import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, rows[:1], scheme="noc", edition="fx-a", source_ref="fx_tax", mode="fixture").existing == 1       # idempotent
    labels = sandbox.a.aliases_for(sandbox.g.find_by_identifier("noc", "90001", "fx-a")[0]["occupation_key"])
    assert {(x["language"], x["language_basis"], x["alias_type"], x["evidence_eligible_origin"]) for x in labels} == {("en", "fixture_declared", "official_preferred", False), ("fr", "fixture_declared", "official_preferred", False)}


def test_a_production_taxonomy_import_needs_approval_and_a_known_edition(sandbox):
    approve(sandbox.reg, "real_tax")
    sandbox.tax.ensure("noc", "unknown")
    with pytest.raises(CountryImportNotApproved):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, [{"code": "90001", "label": "x"}], scheme="noc", edition="unknown", source_ref="real_tax", mode="production")
    rep = import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, [{"code": "90001", "label": "x", "labels": [{"text": "official x", "language": "en"}, {"text": "no language"}]}],
                                scheme="noc", edition="fx-a", source_ref="real_tax", mode="production", language_basis="source_file")
    assert rep.added == 1 and rep.rejections == {"label_without_language": 1}
    assert sandbox.a.aliases_for(sandbox.g.find_by_identifier("noc", "90001", "fx-a")[0]["occupation_key"])[0]["language_basis"] == "source_file"


def test_the_same_native_code_in_two_editions_never_collides_and_unknown_matches_nothing(sandbox):
    for ed in ("fx-a", "fx-b"):
        import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, [{"code": "90010", "label": f"Synthetic {ed}"}], scheme="noc", edition=ed, source_ref="fx_tax", mode="fixture")
    hits = sandbox.g.find_by_identifier("noc", "90010")
    assert len({h["occupation_key"] for h in hits}) == 2 and [h["edition"] for h in hits] == ["fx-a", "fx-b"]
    assert sandbox.g.find_by_identifier("noc", "90010", "unknown") == [] and sandbox.g.find_by_identifier("noc", "90010", "fx-c") == []


def test_crosswalk_import_states_only_what_a_registered_source_says(sandbox):
    for code, scheme, ed in (("90001", "noc", "fx-a"), ("9801", "isco", "08"), ("9802", "isco", "08")):
        sandbox.tax.ensure(scheme, ed)
        sandbox.g.add_occupation(f"Synthetic {code}", [(scheme, ed, code)])
    reg = sandbox.reg
    row = lambda t, s, to="9801": {"from_code": "90001", "to_code": to, "relationship_type": t, "mapping_status": s}  # noqa: E731
    for src, mode in (("nope", "fixture"), ("real_tax", "production"), ("fx_tax", "production"), ("real_tax", "fixture")):
        with pytest.raises(CountryImportNotApproved):
            import_crosswalk(sandbox.g, reg, [row("broader", "verified")], source_ref=src, from_taxonomy=("noc", "fx-a"), to_taxonomy=("isco", "08"), mode=mode)
    kw = dict(source_ref="fx_tax", from_taxonomy=("noc", "fx-a"), to_taxonomy=("isco", "08"), mode="fixture")
    rep = import_crosswalk(sandbox.g, reg, [row("broader", "verified"), row("equivalent", "partial", "9802"), row("similar", "verified", "9802"), row("broader", "bogus", "9802"),
                                           row("broader", "verified", "9999"), {**row("broader", "verified"), "from_code": "1"}], **kw)
    assert rep.added == 1 and rep.rejections == {"equivalence_requires_a_verified_statement": 1, "invalid_relationship_vocabulary": 2, "to_code_not_in_graph": 1, "from_code_not_in_graph": 1}
    again = import_crosswalk(sandbox.g, reg, [row("broader", "verified")], **kw)
    assert again.existing == 1 and again.added == 0
    clash = import_crosswalk(sandbox.g, reg, [row("narrower", "verified")], **kw)
    assert clash.rejections == {"conflicting_statement": 1}                                                   # never overwritten
    rel = sandbox.g.relationships(sandbox.g.find_by_identifier("noc", "90001", "fx-a")[0]["occupation_key"])[0]
    assert rel["relationship_type"] == "broader" and rel["mapping_status"] == "verified" and rel["basis"] == "source_provided"
    unknown = import_crosswalk(sandbox.g, reg, [row("broader", "verified", "9802")], source_ref="fx_tax", from_taxonomy=("noc", "unknown"), to_taxonomy=("isco", "08"), mode="fixture")
    assert unknown.added == 0 and unknown.rejections == {"taxonomy_edition_unknown": 1}
    related = import_crosswalk(sandbox.g, reg, [row("related", "partial", "9802")], **kw)
    assert related.added == 1 and any(r["relationship_type"] == "related" and r["mapping_status"] == "partial" for r in sandbox.g.relationships(sandbox.g.find_by_identifier("noc", "90001", "fx-a")[0]["occupation_key"]))


def test_a_country_compensation_import_cannot_use_an_unapproved_or_synthetic_production_source(world):
    rows, _ = CA.canada_records(_rows(), source_ref="fx_ca_pes", source_edition="E9", taxonomy_edition="fx-ed1", reference_year=2025, level_by_code_length={5: "detailed"}, **MAPS)
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved
    for src in ("fx_ca_pes", "nope"):
        with pytest.raises(CompensationSourceNotApproved):
            world.store.import_records(rows, source_ref=src, source_edition="E9", mode="production")
    assert world.reg.can_ingest("fx_ca_pes") is False and world.reg.can_serve_as_evidence("fx_ca_pes") is False


def test_a_real_origin_source_can_be_imported_in_production_only_after_the_lifecycle(sandbox):
    approve(sandbox.reg, "real_tax")
    import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, [{"code": "90001", "label": "x"}], scheme="noc", edition="fx-a", source_ref="fx_tax", mode="fixture")
    recs, _ = CA.canada_records(_rows(), source_ref="real_tax", source_edition="E1", taxonomy_edition="fx-a", reference_year=2025,
                                level_by_code_length={5: "detailed"}, **MAPS)
    rep = sandbox.store.import_records(recs, source_ref="real_tax", source_edition="E1", mode="production", transformation="mechanism test")
    assert rep.added == 1                                                                                      # the MECHANISM works once governed; no real data is involved
    assert sandbox.store.records_for([1], "CA")[0]["currency"] == "CAD"


# ====================================================================================================================================== synthetic corpus
def test_the_corpus_is_synthetic_only_and_makes_no_claim_about_real_taxonomies():
    c = load_corpus()
    assert "SYNTHETIC" in c["note"] and "no code format, edition or figure is a claim" in c["note"]
    assert all(s["source_id"].startswith("fx_") for s in c["sources"]) and {t["edition"] for t in c["taxonomies"]} == {"fx-ed1", "fx-ed2"}
    assert all(n["label"].endswith("[synthetic fixture]") for b in c["nodes"] for n in b["rows"]) and len(c["cases"]) >= 60 and CORPUS_PATH.exists()


def test_every_import_block_and_every_case_matches_and_no_value_is_invented(world):
    assert [b for b in evaluate_blocks(world) if not b["ok"]] == []
    results = evaluate_cases(world)
    assert [r for r in results if not r["ok"]] == []
    assert not any(r["invented_value"] for r in results) and not any(r["operational"] or r["presentable"] for r in results)
    cats = {r["category"] for r in results}
    for needed in ("canada_national", "canada_provincial", "canada_language", "noc_editions", "mexico", "mexico_regional", "mexico_concepts", "brazil", "brazil_regional", "crosswalk", "conflict", "c4",
                   "citation", "approval", "stale", "statistical", "geography_independence", "comparison", "unsupported", "unsupported_occupation", "precedence"):
        assert needed in cats, needed


def _resolve(world, **kw):
    q = dict(kw)
    occ = MultilingualRequest(title=q.pop("title", None), title_language=q.pop("lang", "en"), **{k: q.pop(k) for k in ("taxonomy_scheme", "taxonomy_code", "taxonomy_edition") if k in q})
    return world.resolver.resolve(CompensationRequest(occupation=occ, require_operational=q.pop("op", False), **q))


def test_regional_evidence_is_only_returned_for_its_region_and_never_becomes_national(world):
    reg = _resolve(world, title="syn ca provonly", country="CA", region="ON")
    nat = _resolve(world, title="syn ca provonly", country="CA")
    assert reg.outcome is CompensationOutcome.EVIDENCE and reg.geography_level == "regional" and reg.region == "CA-ON" and any("REGIONAL" in x for x in reg.coverage_limitations)
    assert nat.outcome is CompensationOutcome.ABSTAIN and nat.value is None                                      # a national figure is not inferred from a province
    other = _resolve(world, title="syn ca provonly", country="CA", region="AB")
    assert other.outcome is CompensationOutcome.ABSTAIN and other.abstention_reason == "no_evidence_for_requested_region"
    both = _resolve(world, title="syn mx regional", country="MX")
    assert both.value == "11000" and both.geography_level == "national" and _resolve(world, title="syn mx regional", country="MX", region="JAL").value == "14000"


def test_different_earnings_definitions_populations_and_methods_are_never_combined(world):
    assert _resolve(world, title="syn mx concepts", country="MX").outcome is CompensationOutcome.CONFLICT
    r = _resolve(world, title="syn mx concepts", country="MX")
    assert r.value is None and len(r.conflicts) == 2 and {c["best"]["earnings_concept"] for c in r.conflicts} == {"individual_earnings", "wage_statistic"}
    assert _resolve(world, title="syn br analyst", country="BR").outcome is CompensationOutcome.CONFLICT
    assert _resolve(world, title="syn br analyst", country="BR", evidence_method="survey").value == "7000"
    assert _resolve(world, title="syn br analyst", country="BR", population_scope="formal_sector").value == "8000"
    assert _resolve(world, title="syn br analyst", country="BR", evidence_method="census").outcome is CompensationOutcome.ABSTAIN


def test_household_income_is_stored_nowhere_and_never_presented(world):
    r = _resolve(world, title="syn mx household", country="MX")
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None
    assert any(rep.rejections.get("earnings_concept_not_occupation_compensation") for rep in world.comp_reports)
    with world.sf() as s:
        assert s.scalar(select(CompensationRecordV2Row.id).where(CompensationRecordV2Row.earnings_concept == "household_income")) is None


def test_candidates_reached_through_several_parents_never_resolve_arbitrarily(world):
    r = _resolve(world, title="syn ca multiparent", country="CA")
    # Owner rule (P10C-F2A-Q): an ambiguous hierarchy abstains; each parent's statistic is offered only as separately labelled context, never as the occupation's own value.
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and len(r.contextual_evidence) == 2 and r.abstention_reason == "exact_occupation_measurement_unavailable"
    assert len({c["broader_occupation_code"] for c in r.contextual_evidence}) == 2
    child = _resolve(world, title="syn ca isco child", country="CA")
    assert child.value is None and child.outcome is CompensationOutcome.ABSTAIN and child.occupation_specificity is None
    assert [(c["evidence_class"], c["value"]) for c in child.contextual_evidence] == [("C3", "52000")] and "NOT the requested occupation" in child.contextual_evidence[0]["warning"]


def test_a_noc_edition_is_never_matched_to_another_or_to_unknown(world):
    one = _resolve(world, taxonomy_scheme="noc", taxonomy_code="90010", taxonomy_edition="fx-ed1", country="CA")
    two = _resolve(world, taxonomy_scheme="noc", taxonomy_code="90010", taxonomy_edition="fx-ed2", country="CA")
    none = _resolve(world, taxonomy_scheme="noc", taxonomy_code="90010", country="CA")
    unknown = _resolve(world, taxonomy_scheme="noc", taxonomy_code="90010", taxonomy_edition="unknown", country="CA")
    assert one.value == "28" and two.outcome is CompensationOutcome.ABSTAIN and none.outcome is CompensationOutcome.AMBIGUOUS and unknown.outcome is CompensationOutcome.NOT_FOUND
    assert one.occupation_key != two.occupation_key


def test_the_interface_language_never_selects_the_employment_country(world):
    fields = set(CompensationRequest.__dataclass_fields__)
    assert not fields & {"language", "locale", "ui_language", "interface_language"} and "country" in fields
    cases = [("syn analyste ca", "fr", "CA", "38.50"), ("syn analyst mx de", "de", "MX", "12000"), ("syn analista ca", "pt", "CA", "38.50"), ("syn analista br es", "es", "BR", None), ("syn br analyst", "en", "BR", None)]
    for title, lang, country, value in cases:
        r = _resolve(world, title=title, lang=lang, country=country)
        assert r.country == country and (Decimal(r.value) == Decimal(value) if value else r.value is None)
    for title, lang, country in (("syn analista br", "pt", "MX"), ("syn analista mx", "es", "CA"), ("syn analista br", "pt", "CA"), ("syn analyste ca", "fr", "BR")):
        r = _resolve(world, title=title, lang=lang, country=country)
        assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.country == country           # the same occupation never borrows another country's evidence


def test_cad_mxn_and_brl_are_never_compared_or_converted(world):
    for mode in ("fx_converted", "ppp_adjusted"):
        for title, country in (("syn ca analyst", "CA"), ("syn mx analyst", "MX"), ("syn br analyst", "BR")):
            r = _resolve(world, title=title, country=country, comparison_mode=mode)
            assert r.outcome is CompensationOutcome.NOT_CONFIGURED and r.value is None
    assert {_resolve(world, title=t, country=c).currency for t, c in (("syn ca analyst", "CA"), ("syn mx analyst", "MX"))} == {"CAD", "MXN"}


def test_the_default_withholds_country_evidence_that_is_not_operational(world):
    for title, country in (("syn ca analyst", "CA"), ("syn mx analyst", "MX"), ("syn br regional", "BR")):
        r = _resolve(world, title=title, country=country, op=True)
        assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.abstention_reason == "evidence_exists_but_is_not_operational" and r.evidence_class == "C4"


# ====================================================================================================================================== policy, keys, comparability
def test_policy_p10c_d_classes_regional_figures_by_occupation_specificity_and_nothing_else_changes():
    p = PrecedencePolicy.load()
    assert p.version == "p10c-e/1" and "regional_geography" in p.raw and p.raw["country_overrides"].startswith("none")
    assert classify_evidence(p, "national_public_employment_service", "detailed", "regional") == "C1" and classify_evidence(p, "national_official_occupation_statistics", "broad", "regional") == "C2"
    assert classify_evidence(p, "national_official_occupation_statistics", "unknown", "regional") is None and classify_evidence(p, "authorized_secondary", "detailed", "regional") is None
    assert classify_evidence(p, "eurostat_harmonised", "broad", "regional") is None                                # a harmonised source is never regionally classed


def test_record_keys_of_unknown_definitions_equal_the_p10c_c_formula_and_known_ones_differ():
    base = dict(taxonomy_scheme="soc", taxonomy_edition="2018", native_code="99-0100", country="US", currency="USD", pay_period="annual", measure="median", value=Decimal("1"), source_ref="fx",
                source_edition="E1", reference_year=2025)
    r = CompensationRecordV2(**base)
    legacy = "cv2_" + hashlib.sha256("\x1f".join(["fx", "E1", "7", "99-0100", "US", "", "2025", "annual", "USD", "unknown", "median", "0", ""]).encode()).hexdigest()[:40]
    assert record_key_for(r, 7) == legacy
    assert len({record_key_for(CompensationRecordV2(**base, earnings_concept=c), 7) for c in ("individual_earnings", "wage_statistic")} | {legacy}) == 3
    assert CompensationRecordV2(**base).comparability_key() != CompensationRecordV2(**base, evidence_method="survey").comparability_key()


def test_the_resolver_still_treats_unknown_definitions_as_comparable_only_with_unknown(world):
    r = _resolve(world, title="syn ca precedence", country="CA")
    assert r.outcome is CompensationOutcome.EVIDENCE and r.value == "42" and r.evidence_class == "C1" and len(r.corroborating) == 1 and r.earnings_concept == "unknown"


# ====================================================================================================================================== concurrency and performance
def test_concurrent_duplicate_country_imports_yield_one_set(sandbox):
    import_taxonomy_nodes(sandbox.g, sandbox.a, sandbox.reg, [{"code": "90001", "label": "x"}], scheme="noc", edition="fx-a", source_ref="fx_tax", mode="fixture")
    sandbox.reg.register("fx_cmp", origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_official_occupation_statistics")
    recs, _ = CA.canada_records(_rows() + _rows(region="ON"), source_ref="fx_cmp", source_edition="E1", taxonomy_edition="fx-a", reference_year=2025, level_by_code_length={5: "detailed"}, **MAPS)
    gate, out = threading.Barrier(5), []

    def go():
        gate.wait()
        try:
            out.append(sandbox.store.import_records(recs, source_ref="fx_cmp", source_edition="E1", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sandbox.store.counts() == {"records": 2, "batches": 1} and any(not isinstance(r, str) and r.added == 2 for r in out)


def test_large_multi_edition_country_datasets_resolve_quickly_with_bounded_queries(sf):
    import time
    from src.knowledge_foundation.compensation.resolver import CompensationResolver
    from src.knowledge_foundation.occupation_resolver import OccupationResolver
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    for ed in ("fx-a", "fx-b"):
        tax.ensure("noc", ed, status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{5}")
    reg.register("fx_t", origin="synthetic_fixture", publisher="P", dataset_name="D")
    reg.register("fx_p", origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_public_employment_service")
    store, a = CompensationStoreV2(sf, reg, g), AliasStore(sf)
    n = 400
    for ed in ("fx-a", "fx-b"):
        import_taxonomy_nodes(g, a, reg, [{"code": f"{90000 + i}", "label": f"Synthetic {ed} {i}"} for i in range(n)], scheme="noc", edition=ed, source_ref="fx_t", mode="fixture")
    rows = [{"code": f"{90000 + i}", "statistic": "MED", "period": "HR", "value": str(20 + i % 30), **({"region": r} if r else {})} for i in range(n) for r in (None, "ON", "QC", "BC")]
    recs, rej = CA.canada_records(rows, source_ref="fx_p", source_edition="E1", taxonomy_edition="fx-a", reference_year=2025, level_by_code_length={5: "detailed"}, **MAPS)
    t0 = time.perf_counter()
    rep = store.import_records(recs, source_ref="fx_p", source_edition="E1", mode="fixture")
    assert not rej and rep.added == n * 4 and time.perf_counter() - t0 < 60
    counter = {"n": 0}

    @event.listens_for(sf.kw["bind"], "before_cursor_execute")
    def _c(conn, cur, st, par, ctx, many):
        counter["n"] += 1
    res = CompensationResolver(store, OccupationResolver(g, a), g, reg)
    t1 = time.perf_counter()
    peak = 0
    for i in range(0, n, 10):
        before = counter["n"]
        r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="noc", taxonomy_code=f"{90000 + i}", taxonomy_edition="fx-a"), country="CA", region="QC", require_operational=False))
        peak = max(peak, counter["n"] - before)
        assert r.outcome is CompensationOutcome.EVIDENCE and r.region == "CA-QC"
    assert (time.perf_counter() - t1) * 1000 / 40 < 100 and peak < 40
    other = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="noc", taxonomy_code="90005", taxonomy_edition="fx-b"), country="CA", require_operational=False))
    assert other.outcome is CompensationOutcome.ABSTAIN                                                        # same code, other edition: a different occupation with no evidence


# ====================================================================================================================================== isolation and gates
def test_nothing_new_is_imported_by_a_runtime_or_candidate_path_and_v1_is_unchanged():
    offenders = []
    for pkg in ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents", "src/billing"):
        for f in (ROOT / pkg).rglob("*.py"):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []
    for rel in ("src/copilot/knowledge/compensation.py", "src/copilot/knowledge/retrieval.py", "src/copilot/knowledge/router.py", "src/copilot/knowledge/governed_datasets.py"):
        assert "knowledge_foundation" not in (ROOT / rel).read_text(), rel
    from src.copilot import constants
    assert set(constants.COUNTRY_SOURCE_PRIORITY) == {"DE", "US", "UK", "EU"}


def test_no_country_module_converts_downloads_or_reads_a_protected_store():
    banned = {"requests", "httpx", "urllib", "stripe", "openai", "boto3", "aiohttp", "socket", "pandas"}
    for f in (ROOT / "src/knowledge_foundation/compensation").glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & banned, (f.name, mods & banned)
        src = f.read_text(encoding="utf-8")
        assert "data/knowledge" not in src and "COMPENSATION_DB_PATH" not in src, f.name
        for n in ast.walk(tree):
            assert not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and any(isinstance(x, ast.Constant) and x.value in (12, 52, 260, 2080, 40) for x in (n.left, n.right))), (f.name, n.lineno)


def test_all_gates_stay_off():
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    assert not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED])
    for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, g) is False


def test_no_client_path_can_import_or_approve_country_data():
    for f in (ROOT / "src/api").rglob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert not any(x in t for x in ("import_taxonomy_nodes", "import_crosswalk", "CompensationStoreV2", "country_records", "canada_records")), f


def test_the_coverage_matrix_levels_for_the_three_countries_are_unchanged_and_nothing_is_qualified():
    rows = {r["code"]: r for r in json.loads((ROOT / "src/knowledge_foundation/data/coverage_matrix.json").read_text())["geographies"]}
    assert (rows["CA"]["taxonomy_level"], rows["CA"]["compensation_level"]) == ("source_identified", "source_identified") and rows["MX"]["compensation_level"] == rows["BR"]["compensation_level"] == "targeted"
    for c in ("CA", "MX", "BR"):
        assert "qualified" not in (rows[c]["taxonomy_level"], rows[c]["crosswalk_level"], rows[c]["compensation_level"], rows[c]["outlook_level"]) and rows[c]["source_languages"] == [] and rows[c]["source_ids"] == []
        assert "P10C-D" in rows[c]["limitations"] and "nothing is qualified" in rows[c]["limitations"]


# ====================================================================================================================================== migration 0038
def test_migration_0038_adds_the_definition_columns_keeps_rows_and_checks_and_is_reversible(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    from src import persistence as P
    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0039_speech_governance"]
    command.upgrade(cfg, "0037_compensation_v2")
    eng = create_engine(url)
    assert "earnings_concept" not in {c["name"] for c in inspect(eng).get_columns("compensation_v2_records")}
    command.upgrade(cfg, "head")
    insp = inspect(eng)
    cols = {c["name"]: c for c in insp.get_columns("compensation_v2_records")}
    model = P.CompensationRecordV2Row.__table__
    assert set(cols) == {c.name for c in model.columns} and {"earnings_concept", "population_scope", "evidence_method"} <= set(cols)
    uq = {u["name"]: u["column_names"] for u in insp.get_unique_constraints("compensation_v2_records")}
    assert {"earnings_concept", "population_scope", "evidence_method"} <= set(uq["uq_comp_v2_natural_key"]) and "uq_comp_v2_record_key" in uq
    assert {"ix_comp_v2_lookup", "ix_comp_v2_source"} <= {i["name"] for i in insp.get_indexes("compensation_v2_records")}
    sql = sqlite3.connect(url.replace("sqlite:///", "")).execute("select sql from sqlite_master where name = 'compensation_v2_records'").fetchone()[0]
    for name in ("ck_cv2_value_not_zero_or_invented", "ck_cv2_percentile", "ck_cv2_bounds", "ck_cv2_evidence_class", "ck_cv2_provenance_present", "ck_cv2_currency", "ck_cv2_earnings_concept",
                 "ck_cv2_not_household_income", "ck_cv2_population_scope", "ck_cv2_evidence_method"):
        assert name in sql, name                                                                                # the rebuild preserved every CHECK
    command.downgrade(cfg, "0037_compensation_v2")
    after = {c["name"] for c in inspect(eng).get_columns("compensation_v2_records")}
    assert "earnings_concept" not in after and "value_units" in after
    assert "ck_cv2_value_not_zero_or_invented" in sqlite3.connect(url.replace("sqlite:///", "")).execute("select sql from sqlite_master where name = 'compensation_v2_records'").fetchone()[0]
    command.upgrade(cfg, "head")


def test_the_migrated_table_still_refuses_invented_and_household_rows_and_preserves_existing_rows(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0037_compensation_v2")
    eng = create_engine(url)
    base = ("insert into compensation_v2_records (record_key, occupation_id, taxonomy_id, native_code, country, currency, pay_period, value_status, value_units, source_ref, source_edition, reference_year, "
            "evidence_class, precedence_category, provenance, created_at {extra}) values ('{key}', 1, 1, 'n{key}', 'US', 'USD', 'annual', 'reported', {units}, 's', 'e', 2025, 'C1', 'x', '{{}}', '2026-01-01' {vals})")
    with eng.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text("insert into graph_occupations (id, occupation_key, canonical_label, status, legacy_keys, created_at) values (1, 'k', 'l', 'active', '[]', '2026-01-01')"))
        c.execute(text("insert into occupation_taxonomies (id, scheme, edition, status, acquisition_status, geographies, created_at) values (1, 'soc', '2018', 'unknown', 'not_acquired', '[]', '2026-01-01')"))
        c.execute(text(base.format(key="old", units=5000, extra="", vals="")))
    command.upgrade(cfg, "head")
    with eng.begin() as c:
        row = c.execute(text("select earnings_concept, population_scope, evidence_method, value_units from compensation_v2_records")).one()
    assert tuple(row) == ("unknown", "unknown", "unknown", 5000)                                               # an existing row keeps unknown definitions
    for extra, vals, units in ((", earnings_concept", ", 'household_income'", 5), ("", "", 0), (", population_scope", ", 'everyone'", 5), (", evidence_method", ", 'vibes'", 5)):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(base.format(key=f"bad{extra}{units}", units=units, extra=extra, vals=vals)))
    command.downgrade(cfg, "0037_compensation_v2")
    with eng.begin() as c:
        assert c.execute(text("select value_units from compensation_v2_records")).scalar() == 5000


def test_the_committed_corpus_is_stable_json():
    c = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert c["schema"] == "country_fixture_corpus/1" and len(c["compensation"]) == 10 and len(c["crosswalks"]) == 3


def test_the_downgrade_refuses_before_changing_anything_when_definition_distinct_rows_exist(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    ins = ("insert into compensation_v2_records (record_key, occupation_id, taxonomy_id, native_code, country, currency, pay_period, value_status, value_units, source_ref, source_edition, reference_year, "
           "evidence_class, precedence_category, provenance, created_at, earnings_concept) values ('{k}', 1, 1, 'n', 'MX', 'MXN', 'monthly', 'reported', 5, 's', 'e', 2025, 'C1', 'x', '{{}}', '2026-01-01', '{c}')")
    with eng.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text("insert into graph_occupations (id, occupation_key, canonical_label, status, legacy_keys, created_at) values (1, 'k', 'l', 'active', '[]', '2026-01-01')"))
        c.execute(text("insert into occupation_taxonomies (id, scheme, edition, status, acquisition_status, geographies, created_at) values (1, 'sinco', 'fx', 'unknown', 'not_acquired', '[]', '2026-01-01')"))
        c.execute(text(ins.format(k="a", c="individual_earnings")))
        c.execute(text(ins.format(k="b", c="wage_statistic")))
    with pytest.raises(RuntimeError, match="downgrade refused"):
        command.downgrade(cfg, "0037_compensation_v2")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from compensation_v2_records")).scalar() == 2 and c.execute(text("select version_num from alembic_version")).scalar() == "0038_compensation_concepts"
