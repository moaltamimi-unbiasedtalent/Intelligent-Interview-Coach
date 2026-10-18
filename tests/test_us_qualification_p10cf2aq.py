"""P10C-F2A-Q: US evidence qualification review, count reconciliation, curated-alias governance and the broader-group rule. FULLY OFFLINE: synthetic workbooks and throwaway SQLite databases only;
nothing here is official data, a real salary or an approval."""

from __future__ import annotations

import importlib.util
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from src.knowledge_foundation import us_qualification as Q
from src.knowledge_foundation import us_sources as U
from src.knowledge_foundation.aliases import AliasError, AliasStore
from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver
from src.knowledge_foundation.compensation.store import CompensationStoreV2
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver, ResolutionOutcome
from src.persistence import init_db, make_engine, make_session_factory
from tests.test_us_sources_p10cf2a import _approve, _definitions, _oews, _row, _structure, _world

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def sf(tmp_path):
    e = make_engine(f"sqlite:///{tmp_path / 'q.db'}")
    init_db(e)
    return make_session_factory(e)


@pytest.fixture()
def files(tmp_path):
    s, d, o = tmp_path / "s.xlsx", tmp_path / "d.xlsx", tmp_path / "o.xlsx"
    _structure(s)
    _definitions(d)
    _oews(o, [_row("00-0000", "total"), _row("11-0000", "major"), _row("11-1000", "minor"), _row("11-1010", "broad"), _row("11-1010", "detailed"), _row("11-1011", "detailed"),
              _row("11-1012", "detailed", ANNUAL="TRUE", H_MEAN="*", H_PCT10="*", H_PCT25="*", H_MEDIAN="*", H_PCT75="*", H_PCT90="*"),
              _row("11-1021", "detailed", HOURLY="TRUE", A_MEAN="*", A_PCT10="*", A_PCT25="*", A_MEDIAN="*", A_PCT75="*", A_PCT90="*"), _row("21-1018", "detailed")])
    return s, d, o


@pytest.fixture()
def world(sf, files):
    tax, reg, g, st, defs = _world(sf, files)
    U.populate_soc_graph(g, st, defs)
    rows, _ = U.parse_oews_national(files[2])
    recs, rep = U.oews_v2_records(rows, {n.code: n.level for n in st}, archive_sha256="a" * 64)
    store = CompensationStoreV2(sf, reg, g)
    _approve(reg, U.OEWS_SOURCE)
    store.import_records(recs, source_ref=U.OEWS_SOURCE, source_edition="May 2025", mode="production", transformation=U.TRANSFORMATION)
    occ = OccupationResolver(g, AliasStore(sf), registry=reg)
    return type("W", (), dict(sf=sf, reg=reg, g=g, st=st, defs=defs, store=store, rows=rows, recs=recs, rep=rep, occ=occ, res=CompensationResolver(store, occ, g, reg), aliases=AliasStore(sf)))


def _ask(w, code=None, title=None, period="annual", measure="median", country="US", edition="2018", scheme="soc", allow=True):
    occ = MultilingualRequest(taxonomy_scheme=scheme, taxonomy_code=code, taxonomy_edition=edition) if code else MultilingualRequest(title=title, title_language="en", taxonomy_scheme=scheme, taxonomy_edition=edition)
    return w.res.resolve(CompensationRequest(occupation=occ, country=country, require_operational=False, pay_period=period, measure=measure, allow_broader_occupation=allow))


# -------------------------------------------------------------------------------------------------------------------------------- record review (engineering)
def _good(**kw):
    rec = dict(source_ref="bls_oews", source_edition="May 2025", value=Decimal("41392"), value_status="reported", measure="median", pay_period="annual", pay_basis="gross", currency="USD",
               earnings_concept="wage_statistic", population_scope="employees", evidence_method="survey", geography_level="national", country="US", region=None, occupation_level="detailed",
               reference_period="May 2025", reference_year=2025, publication_date=object(), batch_id=1,
               provenance={"transformation": "t", "manifest_file_id": "f", "archive_sha256": "a" * 64, "archive_member": "m", "sheet": "s", "source_rows": [2], "source_field": "A_MEDIAN", "emp_prse": 1.0, "tot_emp": 10, "mean_prse": 0.5})
    rec.update(kw)
    return rec


SRC = {"approval_status": "approved_for_ingestion", "licence_status": "verified"}


def test_a_record_passing_every_rule_is_engineering_checked_without_a_precision_claim():
    out, why = Q.review_record(_good(), source=SRC, file_integrity_ok=True, soc_level="detailed", key_count=1)
    assert out == "ENGINEERING_CHECKED" and "no_precision_claim_made" in why


@pytest.mark.parametrize("patch,reason", [({"measure": "unknown"}, "measurement_definition_incomplete"), ({"pay_basis": "unknown"}, "measurement_definition_incomplete"),
                                           ({"earnings_concept": "unknown"}, "concept_population_or_method_unrecorded"), ({"region": "CA", "geography_level": "regional"}, "geography_not_national_us"),
                                           ({"value": None, "value_status": "suppressed"}, "no_positive_reported_value"), ({"reference_period": None}, "reference_or_publication_period_missing"),
                                           ({"provenance": {}}, "provenance_incomplete"), ({"batch_id": None}, "provenance_incomplete"), ({"occupation_level": "broad"}, "occupation_level_disagrees_with_soc_structure")])
def test_each_failed_rule_gives_a_deterministic_insufficient_reason(patch, reason):
    out, why = Q.review_record(_good(**patch), source=SRC, file_integrity_ok=True, soc_level="detailed", key_count=1)
    assert out == "INSUFFICIENT" and reason in why


def test_unapproved_source_unverified_file_non_canonical_occupation_conflict_and_foreign_source():
    assert Q.review_record(_good(), source={"approval_status": "licensing_pending", "licence_status": "verified"}, file_integrity_ok=True, soc_level="detailed", key_count=1)[1] == ["source_not_approved_for_ingestion_with_verified_licence"]
    assert "original_file_hash_not_verified" in Q.review_record(_good(), source=SRC, file_integrity_ok=False, soc_level="detailed", key_count=1)[1]
    assert "occupation_not_a_canonical_soc_2018_node" in Q.review_record(_good(), source=SRC, file_integrity_ok=True, soc_level=None, key_count=1)[1]
    assert Q.review_record(_good(), source=SRC, file_integrity_ok=True, soc_level="detailed", key_count=2) == ("CONFLICTING", ["record_key_not_unique"])
    assert Q.review_record(_good(source_ref="other"), source=SRC, file_integrity_ok=True, soc_level="detailed", key_count=1)[0] == "QUARANTINED"
    assert "mean_without_published_rse" in Q.review_record(_good(measure="mean", provenance={**_good()["provenance"], "mean_prse": None}), source=SRC, file_integrity_ok=True, soc_level="detailed", key_count=1)[1]


def test_review_script_engineering_checks_but_never_qualifies(world, tmp_path):
    spec = importlib.util.spec_from_file_location("p10c_f2aq_qualify", ROOT / "scripts/p10c_f2aq_qualify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    dry = mod.review_all(world.sf, world.store, world.reg, world.st, False, True, tmp_path)
    assert dry["state_counts_after"] == {"unqualified": len(world.recs)} and dry["outcomes"] == {"ENGINEERING_CHECKED": len(world.recs)}
    real = mod.review_all(world.sf, world.store, world.reg, world.st, True, True, tmp_path)
    again = mod.review_all(world.sf, world.store, world.reg, world.st, True, True, tmp_path)
    assert real["state_counts_after"] == {"engineering_checked": len(world.recs)} and real["qualified"] == 0 and again["moved_to_engineering_checked_this_run"] == 0
    with pytest.raises(ValueError):
        world.store.set_qualification(world.store.records_for([1], "US")[0]["record_key"], "qualified", actor_user_id=None)          # no reviewer, no qualification
    op = _ask(world, code="11-1011")
    assert op.operational is False and op.candidate_presentable is False


# -------------------------------------------------------------------------------------------------------------------------------------- reliability and counts
def test_rse_is_described_never_thresholded(world):
    d = Q.rse_distribution(world.rows, {n.code for n in world.st} - {"21-1018"})
    assert d["occupations"] == 6 and d["emp_prse"]["n"] == 6 and "not_published_for" in d and "median wage" in d["not_published_for"]
    assert "cutoff" not in str(d["emp_prse"]) and set(d["emp_prse"]["descriptive_counts_above"]) == {"10%", "25%", "50%"}
    assert all(r.provenance["emp_prse"] == 1.5 for r in world.recs if r.native_code == "11-1011")


def test_annual_only_count_difference_is_exactly_the_quarantined_rows(files):
    st = U.parse_soc_structure(files[0])
    rows, _ = U.parse_oews_national(files[2])
    rows = rows + [type(rows[0])(row=99, values={**rows[0].values, "OCC_CODE": "25-2052", "O_GROUP": "detailed", "ANNUAL": "TRUE"})]
    t = Q.annual_only_reconciliation(rows, {n.code for n in st}, {"25-2052"})
    assert t["annual_true_rows"] == 2 and t["canonical_annual_only_occupations"] == 1 and [x["occ_code"] for x in t["excluded_rows"]] == ["25-2052"] and t["excluded_rows"][0]["source_row"] == 99


def test_reconciliation_arithmetic_on_the_synthetic_world(world):
    spec = importlib.util.spec_from_file_location("p10c_f2aq_qualify2", ROOT / "scripts/p10c_f2aq_qualify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod.reconcile(world.sf, world.rows, world.st, world.rep)
    assert r["all_match"] and r["database"]["graph_nodes"] == 11 and r["source_rows"]["quarantined"] == ["21-1018"]


def test_duplicate_presentation_does_not_multiply_measurements(world):
    n = len([r for r in world.recs if r.native_code == "11-1010" and r.pay_period == "annual" and r.measure == "median"])
    assert n == 1 and world.rep["duplicate_presentations"] == {"11-1010": ["broad", "detailed"]}
    again = world.store.import_records(world.recs, source_ref=U.OEWS_SOURCE, source_edition="May 2025", mode="production")
    assert again.already_imported and world.store.counts()["records"] == len(world.recs)


# ------------------------------------------------------------------------------------------------------------------------------------------------ alias evidence
def test_alias_evidence_rule_single_ambiguous_and_absent(world):
    cases = {"c1": "Syn Detailed Three", "c2": "Syn", "c3": "Nothing Like It", "c4": "Syn Detailled"}
    p = {x["case"]: x for x in Q.build_alias_proposals(cases, world.st, world.defs)}
    assert p["c1"]["decision"] == "PROPOSED_SINGLE" and p["c1"]["target_code"] == "11-1021" and p["c1"]["qualification_status_target"] == "engineering_checked" and "PENDING_HUMAN_REVIEW" in p["c1"]["approval"]
    assert p["c2"]["decision"] == "AMBIGUOUS" and len(p["c2"]["candidates"]) >= 3                     # several official titles contain it: no alias, no first match
    assert p["c3"]["decision"] == "NO_AUTHORITATIVE_EVIDENCE" and p["c3"]["candidates"] == []
    assert p["c4"]["decision"] == "NO_AUTHORITATIVE_EVIDENCE"                                         # a similar-looking word is not evidence
    assert len(Q.soc_title_candidates("Syn Detailed", world.st)) == 4 and all(n.level == "detailed" for n in Q.soc_title_candidates("Syn Detailed", world.st))


def _alias(w, code, text, **kw):
    node = w.g.find_by_identifier("soc", code, "2018")[0]
    prov = kw.pop("provenance", {"country_applicability": ["US"]})
    return w.aliases.add_alias(node["occupation_key"], text, language="en", language_basis="curated_manual", alias_type="recognized_title", source_ref=U.SOC_SOURCE, taxonomy=("soc", "2018"), provenance=prov, **kw)


def test_alias_resolution_governance(world):
    assert world.occ.resolve(MultilingualRequest(title="Syn Detailed", title_language="en", country="US")).outcome is ResolutionOutcome.INSUFFICIENT_CONTEXT      # the label's language is not recorded
    assert world.occ.resolve(MultilingualRequest(title="Syn Detailed", title_language="en", country="US", accept_unverified_language=True)).outcome is ResolutionOutcome.RESOLVED   # exact official title
    assert world.occ.resolve(MultilingualRequest(title="Syn Worker", title_language="en", country="US")).outcome is ResolutionOutcome.NOT_FOUND            # unsupported alias
    a = _alias(world, "11-1011", "Syn Worker")
    assert a["qualification_status"] == "unqualified"
    r = world.occ.resolve(MultilingualRequest(title="Syn Worker", title_language="en", country="US", taxonomy_scheme="soc", taxonomy_edition="2018"))
    assert r.outcome is ResolutionOutcome.RESOLVED and r.operational is False                                                                           # curated alias, never operational
    wrong_country = world.occ.resolve(MultilingualRequest(title="Syn Worker", title_language="en", country="GB"))
    assert wrong_country.outcome is ResolutionOutcome.NOT_FOUND
    wrong_edition = world.occ.resolve(MultilingualRequest(title="Syn Worker", title_language="en", country="US", taxonomy_scheme="soc", taxonomy_edition="2010"))
    assert wrong_edition.outcome is ResolutionOutcome.NOT_FOUND
    _alias(world, "11-1012", "Syn Worker")                                                                                                              # the same alias on a second occupation
    amb = world.occ.resolve(MultilingualRequest(title="Syn Worker", title_language="en", country="US", taxonomy_scheme="soc", taxonomy_edition="2018"))
    assert amb.outcome is ResolutionOutcome.AMBIGUOUS and len(amb.candidates) == 2                                                                      # no first match, no silent choice
    comp = world.res.resolve(CompensationRequest(occupation=MultilingualRequest(title="Syn Worker", title_language="en"), country="US", require_operational=False, pay_period="annual", measure="median"))
    assert comp.outcome is CompensationOutcome.AMBIGUOUS and comp.value is None


def test_alias_revocation_and_review_authority(world):
    a = _alias(world, "11-1011", "Syn Worker Two")
    with pytest.raises(AliasError):
        world.aliases.set_qualification(a["id"], "qualified", actor_user_id=None)                                                                       # no named reviewer
    assert world.aliases.set_qualification(a["id"], "engineering_checked", actor_user_id=None)["qualification_status"] == "engineering_checked"
    req = MultilingualRequest(title="Syn Worker Two", title_language="en", country="US")
    assert world.occ.resolve(req).outcome is ResolutionOutcome.RESOLVED
    with pytest.raises(AliasError):
        world.aliases.retire_alias(a["id"], reason=" ")
    assert world.aliases.retire_alias(a["id"], reason="synthetic revocation")["status"] == "deprecated"
    assert world.occ.resolve(req).outcome is ResolutionOutcome.NOT_FOUND                                                                                 # revoked: no longer resolves
    assert world.aliases.aliases_for(world.g.find_by_identifier("soc", "11-1011", "2018")[0]["occupation_key"]) is not None


def test_alias_source_must_be_registered_and_fixture_sources_are_not_evidence(world):
    node = world.g.find_by_identifier("soc", "11-1011", "2018")[0]["occupation_key"]
    with pytest.raises(AliasError):
        world.aliases.add_alias(node, "Syn Unregistered", language="en", language_basis="curated_manual", alias_type="recognized_title", source_ref="not_registered")
    world.reg.register("syn_fx", origin="synthetic_fixture", publisher="Synthetic", dataset_name="Synthetic")
    a = world.aliases.add_alias(node, "Syn Fixture Title", language="en", language_basis="curated_manual", alias_type="recognized_title", source_ref="syn_fx")
    assert a["evidence_eligible_origin"] is False


# ---------------------------------------------------------------------------------------------------------------------- broader-group rule and measurement cases
def test_exact_measures_are_returned_and_broad_groups_stay_c2(world):
    ok = _ask(world, code="11-1011")
    assert ok.outcome is CompensationOutcome.EVIDENCE and ok.value == "41392" and ok.evidence_class == "C1" and ok.occupation_specificity == "exact" and ok.contextual_evidence == []
    broad = _ask(world, code="11-1010")
    assert broad.evidence_class == "C2" and broad.occupation_level == "broad"


def test_annual_only_occupation_asked_for_hourly_abstains_and_labels_parent_context(world):
    r = _ask(world, code="11-1012", period="hourly")
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.evidence_class == "C4" and r.abstention_reason == "exact_occupation_measurement_unavailable"
    assert r.measure is None and r.pay_period is None                                                                      # no silent measure substitution, no conversion
    assert len(r.contextual_evidence) == 1
    c = r.contextual_evidence[0]
    assert c["broader_occupation_code"] == "11-1010" and c["broader_occupation_label"] == "Syn Broad" and c["evidence_class"] == "C2" and c["pay_period"] == "hourly" and c["citation"]
    assert c["reference_period"] == "May 2025" and c["measure"] == "median" and "NOT the requested occupation" in c["warning"]
    own = _ask(world, code="11-1012", period="annual")
    assert own.outcome is CompensationOutcome.EVIDENCE and own.occupation_specificity == "exact" and own.value == "41392"        # its own annual value is unaffected


def test_hourly_only_occupation_asked_for_annual_and_parent_without_the_measure(world):
    r = _ask(world, code="11-1021", period="annual")
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.contextual_evidence == [] and r.abstention_reason == "exact_occupation_measurement_unavailable"
    assert _ask(world, code="11-1021", period="hourly").value == "19.9"


def test_no_authorised_fallback_means_no_context_either(world):
    r = _ask(world, code="11-1012", period="hourly", allow=False)
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.contextual_evidence == [] and r.fallback_trace["broader_group_attempted"] is False


def test_unavailable_measure_never_becomes_a_converted_value(world):
    r = _ask(world, code="11-1012", period="hourly")
    assert r.value is None and all(c["pay_period"] == "hourly" for c in r.contextual_evidence)
    assert r.pay_period is None and r.measure is None and r.lower_value is None


def test_noncanonical_invalid_wrong_edition_and_wrong_country_never_return_values(world):
    assert _ask(world, code="21-1018").outcome is CompensationOutcome.NOT_FOUND
    assert _ask(world, code="99-9999").outcome is CompensationOutcome.NOT_FOUND
    assert _ask(world, code="11-1011", edition="2010").outcome is CompensationOutcome.NOT_FOUND
    assert _ask(world, code="11-1011", country="GB").outcome is CompensationOutcome.ABSTAIN
    assert _ask(world, code="55-1011").outcome is CompensationOutcome.ABSTAIN                                                  # military: in the graph, no wage


# ----------------------------------------------------------------------------------------------------------------------------------------- V1 reconciliation
def test_v1_reconciliation_layers_and_v1_is_not_mutated(world, tmp_path):
    spec = importlib.util.spec_from_file_location("p10c_f2a_ingest_t", ROOT / "scripts/p10c_f2a_ingest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    db = tmp_path / "v1.db"
    con = sqlite3.connect(db)
    con.execute("create table compensation_records (source_id, occupation_code, occupation_title, country, region, industry, year, currency, pay_period, statistic_type, value, lower_bound, upper_bound, sample_quality, source_url)")
    ok = next(r for r in world.recs if r.native_code == "11-1011" and r.pay_period == "annual" and r.measure == "median")
    for code, val in (("11-1011", float(ok.value)), ("11-1011", float(ok.value)), ("21-1018", 1.0), ("99-9999", 2.0), ("11-1012", 1.0)):
        con.execute("insert into compensation_records values ('bls_oews', ?, null, 'US', null, null, 2025, 'USD', 'annual', 'median', ?, ?, ?, 'final', null)", (code, val, float(ok.lower_value), float(ok.upper_value)))
    con.commit()
    con.close()
    before = (db.stat().st_size, db.stat().st_mtime_ns)
    out = mod.v1_reconciliation(db, world.recs, world.rep["quarantined_codes"], tmp_path)
    assert out["verdicts"] == {"RECONCILABLE_WITH_OFFICIAL_V2": 1, "DUPLICATE": 1, "INCOMPATIBLE": 1, "UNRESOLVED": 1, "REQUIRES_ADDITIONAL_EVIDENCE": 1}
    assert out["layers"]["qualified_v2_evidence"] == 0 and out["layers"]["runtime_approved"] == 0 and out["v1_db_modified"] is False and before == (db.stat().st_size, db.stat().st_mtime_ns)
