"""P10C-E: wider South America (GKB-11), an ILOSTAT-style international contract (GKB-12) and salary confidence, fallback and comparison (GKB-14). FULLY OFFLINE: throwaway SQLite databases and the
committed SYNTHETIC corpus (invented sources, occupations, indicator codes, units, classification labels and amounts in synthetic-fixture sources that can never be approved). Nothing here is a real
dataset, figure or approval; nothing is imported by a candidate-facing path; no gate changes; no migration exists."""

from __future__ import annotations

import ast
import json
import threading
from decimal import Decimal
from pathlib import Path

import pytest

from src.knowledge_foundation import global_reports as GR
from src.knowledge_foundation.compensation import country_adapters as CA
from src.knowledge_foundation.compensation import international as INTL
from src.knowledge_foundation.compensation.comparison import ComparisonStatus, compare_fx, compare_nominal, compare_ppp
from src.knowledge_foundation.compensation.confidence import EVIDENCE_STATES, assess_evidence_state
from src.knowledge_foundation.compensation.countries import PROFILES, WIDER_SA_PROFILES, normalize_region, profile_for
from src.knowledge_foundation.compensation.country_fixtures import evaluate_blocks, evaluate_cases, evaluate_comparisons, load_corpus, load_world
from src.knowledge_foundation.compensation.policy import POLICY_PATH, PolicyError, PrecedencePolicy
from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver, CompensationResponse
from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved, CompensationStoreV2, evidence_status
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
from src.persistence import init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "src/knowledge_foundation/data/fallback_fixture_corpus.json"
SAM = dict(statistic_map={"MED": ("median", 0), "P10": ("percentile", 10)}, period_map={"MES": "monthly", "HR": "hourly"}, concept_map={"LAB": "employment_income", "HOG": "household_income", "SAL": "wage_statistic"},
           population_map={"ASAL": "employees", "TODOS": "all_workers"}, method_map={"ENC": "survey", "ADM": "administrative_records"}, level_by_code_length={4: "detailed"}, code_pattern="[0-9]{4}")


@pytest.fixture()
def sf(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'e.db'}")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture()
def corpus():
    return load_corpus(CORPUS)


@pytest.fixture()
def world(sf, corpus):
    return load_world(sf, corpus)


def row(**kw):
    base = {"code": "9701", "statistic": "MED", "period": "MES", "value": "1000.50", "concept": "LAB", "population": "ASAL", "method": "ENC", "currency": "CLP", "basis": "gross"}
    base.update(kw)
    return base


def sa(country="CL", rows=None, **kw):
    return CA.south_america_records(country, rows if rows is not None else [row()], source_ref="s", source_edition="E", taxonomy_edition="08", reference_year=2023, **{**SAM, **kw})


def resolve(world, **kw):
    q = dict(kw)
    occ = MultilingualRequest(title=q.pop("title", None), title_language=q.pop("lang", "en"), **{k: q.pop(k) for k in ("taxonomy_scheme", "taxonomy_code", "taxonomy_edition") if k in q})
    return world.resolver.resolve(CompensationRequest(occupation=occ, require_operational=q.pop("op", False), **q))


# ====================================================================================================================================== wider South America profiles (GKB-11)
def test_the_wider_south_america_profiles_cover_exactly_the_eleven_markets_and_leave_brazil_alone():
    assert set(WIDER_SA_PROFILES) == {"AR", "BO", "CL", "CO", "EC", "GY", "PY", "PE", "SR", "UY", "VE"} and "BR" not in WIDER_SA_PROFILES and set(PROFILES) == {"CA", "MX", "BR"}
    assert {c: len(p.regions) for c, p in WIDER_SA_PROFILES.items()} == {"AR": 24, "BO": 9, "CL": 16, "CO": 33, "EC": 24, "GY": 10, "PY": 0, "PE": 0, "SR": 10, "UY": 19, "VE": 25}
    assert all(p.taxonomy_scheme == "isco" and p.enforce_currency is False for p in WIDER_SA_PROFILES.values()) and all("no national occupation classification identified" in p.note for p in WIDER_SA_PROFILES.values())
    assert "vocabulary not yet recorded" in WIDER_SA_PROFILES["PE"].note and "vocabulary not yet recorded" in WIDER_SA_PROFILES["PY"].note and "vocabulary not yet recorded" not in WIDER_SA_PROFILES["CL"].note
    assert profile_for("br") is PROFILES["BR"] and profile_for("cl") is WIDER_SA_PROFILES["CL"] and profile_for("DE") is None


def test_region_values_are_validated_where_a_vocabulary_is_recorded_and_rejected_otherwise():
    assert normalize_region("CL", "rm") == "CL-RM" and normalize_region("AR", "AR-B") == "AR-B" and normalize_region("CO", "dc") == "CO-DC" and normalize_region("EC", "SD") == "EC-SD" and normalize_region("VE", "x") == "VE-X"
    for country, bad in (("CL", "Santiago"), ("CL", "ZZ"), ("AR", "CL-RM"), ("PE", "LIM"), ("PY", "ASU"), ("CL", ""), ("BO", "C-1")):
        assert normalize_region(country, bad) is None
    assert normalize_region("CA", "ON") == "CA-ON" and normalize_region("BR", "SP") == "BR-SP"                  # P10C-D vocabularies unchanged


def test_the_south_america_adapter_requires_the_definition_and_the_source_stated_currency():
    recs, rej = sa(rows=[row(), row(concept=None), row(population=None), row(method=None), row(currency=None), row(currency="clp"), row(concept="XYZ"), row(region="Santiago"), row(code="97")])
    assert len(recs) == 1 and dict(rej) == {"concept_missing": 1, "population_missing": 1, "method_missing": 1, "currency_missing": 1, "schema_invalid:currency": 1, "concept_unmapped": 1, "region_unrecognised": 1,
                                           "invalid_native_code": 1}
    r = recs[0]
    assert (r.taxonomy_scheme, r.taxonomy_edition, r.country, r.currency, r.pay_period, r.earnings_concept, r.population_scope, r.evidence_method, r.pay_basis) == ("isco", "08", "CL", "CLP", "monthly", "employment_income", "employees", "survey", "gross")
    assert r.value == Decimal("1000.50") and r.occupation_level == "detailed" and r.geography_level == "national"


def test_a_dollarised_or_multi_currency_economy_is_not_forced_into_a_fixed_currency():
    for cc, cur in (("EC", "USD"), ("VE", "VES"), ("AR", "ARS")):
        recs, rej = sa(cc, [row(currency=cur)])
        assert not rej and recs[0].currency == cur and recs[0].country == cc
    with pytest.raises(ValueError):
        CA.south_america_records("BR", [row()], source_ref="s", source_edition="E", taxonomy_edition="08", reference_year=2023, **SAM)
    with pytest.raises(ValueError):
        CA.south_america_records("US", [row()], source_ref="s", source_edition="E", taxonomy_edition="08", reference_year=2023, **SAM)


def test_regional_rows_are_validated_per_country_and_a_regional_row_never_becomes_national():
    recs, rej = sa("CL", [row(), row(region="RM", value="1200"), row(region="LIM")])
    assert {r.region for r in recs} == {None, "CL-RM"} and dict(rej) == {"region_unrecognised": 1}
    by = {r.region: r for r in recs}
    assert by[None].geography_level == "national" and by["CL-RM"].geography_level == "regional"
    recs, rej = sa("PE", [row(currency="PEN", region="LIM")])
    assert recs == [] and dict(rej) == {"region_unrecognised": 1}                                                # the vocabulary is not recorded: rejected, never guessed


def test_household_income_can_be_mapped_but_never_becomes_evidence(world):
    recs, rej = sa("CL", [row(concept="HOG", value="9000")])
    assert recs[0].earnings_concept == "household_income"
    rep = world.store.import_records([r.model_copy(update={"source_ref": "fx_sa_stat", "source_edition": "FX-HH"}) for r in recs], source_ref="fx_sa_stat", source_edition="FX-HH", mode="fixture")
    assert rep.added == 0 and rep.rejections == {"earnings_concept_not_occupation_compensation": 1}


def test_wider_south_america_evidence_never_borrows_from_another_country(world):
    cl = resolve(world, title="syn sa regional", country="CL")
    bo = resolve(world, title="syn sa regional", country="BO")
    co = resolve(world, title="syn sa regional", country="CO")
    assert cl.outcome is CompensationOutcome.EVIDENCE and cl.currency == "CLP" and bo.outcome is co.outcome is CompensationOutcome.ABSTAIN and bo.value is None and co.value is None
    assert cl.fallback_trace["other_country_evidence_used"] is False


# ====================================================================================================================================== ILOSTAT-style international contract (GKB-12)
IMAP = {"EAR_MED": {"period": "monthly", "measure": "median", "concept": "employment_income", "population": "employees", "method": "survey", "basis": "gross"}}
ILO = dict(source_ref="s", source_edition="E", indicator_map=IMAP, currency_by_unit={"LCU": None, "USD": "USD", "PPP": None}, local_currency_unit="LCU", currency_by_country={"CL": "CLP"}, classification_map={"ISCO-08": ("isco", "08")})


def irow(**kw):
    base = {"ref_area": "CHL", "classif": "9707", "classification": "ISCO-08", "indicator": "EAR_MED", "unit": "LCU", "time": 2023, "value": "880.5"}
    base.update(kw)
    return base


def test_the_international_contract_assumes_nothing_about_real_indicators_or_units():
    recs, rej = INTL.ilostat_records([irow()], **{**ILO, "indicator_map": {}})
    assert recs == [] and dict(rej) == {"unsupported_statistic": 1}                                           # no map, no record
    recs, rej = INTL.ilostat_records([irow()], **{**ILO, "classification_map": {}})
    assert recs == [] and dict(rej) == {"classification_unmapped": 1}
    recs, rej = INTL.ilostat_records([irow()], **ILO)
    r = recs[0]
    assert (r.country, r.currency, r.pay_period, r.measure, r.earnings_concept, r.population_scope, r.evidence_method, r.pay_basis, r.taxonomy_scheme, r.taxonomy_edition, r.reference_year) == (
        "CL", "CLP", "monthly", "median", "employment_income", "employees", "survey", "gross", "isco", "08", 2023)
    assert r.geography_level == "national" and r.occupation_level == "detailed" and r.value == Decimal("880.5") and "not a national occupation-specific figure" in r.limitations


def test_only_compensation_indicators_become_records_and_unrelated_statistics_are_rejected():
    rows = [irow(indicator="EMP_RATE"), irow(indicator="GDP_PC", unit="USD"), irow(indicator="PRODUCTIVITY", unit="USD"), irow(indicator="UNEMP"), irow(unit="PPP"), irow(unit="XYZ"), irow(ref_area="XXX"),
            irow(classification="ISCO-88"), irow(classif="97a"), irow(value="abc"), irow(time="n/a"), irow(value="*"), irow(ref_area="USA", unit="USD")]
    recs, rej = INTL.ilostat_records(rows, **ILO)
    assert rej["unsupported_statistic"] == 4 and rej["unit_not_a_currency"] == 1 and rej["unsupported_unit"] == 1 and rej["area_unmapped"] == 1 and rej["classification_unmapped"] == 1
    assert rej["invalid_native_code"] == 1 and rej["malformed_amount"] == 1 and rej["invalid_reference_year"] == 1
    assert len(recs) == 2 and {r.value_status for r in recs} == {"suppressed", "reported"} and {r.country for r in recs} == {"CL", "US"}


def test_the_classification_edition_must_be_stated_and_mapped_explicitly():
    recs, _ = INTL.ilostat_records([irow(classification="ISCO-88", classif="9707")], **{**ILO, "classification_map": {"ISCO-08": ("isco", "08"), "ISCO-88": ("isco", "88")}})
    assert recs[0].taxonomy_edition == "88" and recs[0].taxonomy_scheme == "isco"                            # a different edition is a different namespace, never silently ISCO-08


def test_indicator_maps_are_validated_up_front_and_household_income_is_never_a_compensation_indicator():
    for bad in ({"period": "fortnightly"}, {"concept": "household_income"}, {"concept": "unknown"}, {"measure": "average_vibes"}, {"population": "everyone"}, {"method": "rumour"}):
        with pytest.raises(ValueError):
            INTL.ilostat_records([irow()], **{**ILO, "indicator_map": {"EAR_MED": {**IMAP["EAR_MED"], **bad}}})


def test_the_ilostat_iso3_table_is_a_reference_table_for_the_named_markets_only():
    assert INTL.ISO3_TO_ISO2["CHL"] == "CL" and INTL.ISO3_TO_ISO2["ARG"] == "AR" and len(INTL.ISO3_TO_ISO2) == 16 and "DEU" not in INTL.ISO3_TO_ISO2
    recs, rej = INTL.ilostat_records([irow(ref_area="DEU")], **ILO)
    assert recs == [] and rej["area_unmapped"] == 1
    recs, _ = INTL.ilostat_records([irow(ref_area="DEU")], **{**ILO, "area_map": {"DEU": "DE"}, "currency_by_country": {"DE": "EUR"}})
    assert recs[0].country == "DE"


# ====================================================================================================================================== precedence boundary (D-16)
def test_the_policy_marks_the_international_family_as_pending_and_validates_the_boundary(tmp_path):
    p = PrecedencePolicy.load()
    assert p.version == "p10c-e/1" and p.raw["international_families"]["ilostat"]["enabled"] is False and "D-16" in p.raw["international_families"]["ilostat"]["status"]
    fam = {"provenance": {"international_family": "ilostat"}}
    assert p.international_family(fam) == "ilostat" and p.precedence_pending(fam) is True and p.precedence_pending({"provenance": {}}) is False and p.precedence_pending(None) is False
    assert p.precedence_pending({"provenance": {"international_family": "unlisted"}}) is True                  # an unknown family is never treated as decided
    raw = json.loads(POLICY_PATH.read_text())
    for mod in (lambda d: d["international_families"]["ilostat"].__setitem__("enabled", "yes"), lambda d: d["international_families"]["ilostat"].__setitem__("category_when_enabled", "unknown"),
                lambda d: d["international_families"]["ilostat"].__setitem__("category_when_enabled", "bogus")):
        d = json.loads(json.dumps(raw))
        mod(d)
        f = tmp_path / "p.json"
        f.write_text(json.dumps(d))
        with pytest.raises(PolicyError):
            PrecedencePolicy.load(f)


def _family_world(sf, policy=None):
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    reg.register("ilo_like", origin="official_local", publisher="Synthetic international publisher", dataset_name="Synthetic dataset", precedence_category="eurostat_harmonised", validation_status="unvalidated",
                 provenance={"international_family": "ilostat"})
    store = CompensationStoreV2(sf, reg, g, policy)
    g.add_occupation("Synthetic family occupation", [("isco", "08", "9707")])
    return reg, g, store


def _approve(reg, sid, runtime=False):
    reg.set_licence(sid, licence_id="Synthetic licence", licence_status="verified", attribution_required="yes", redistribution="yes")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion") + (("approved_for_runtime_use",) if runtime else ()):
        reg.transition(sid, step)


def test_a_production_import_of_the_pending_international_family_is_refused_even_after_licence_and_approval(sf):
    reg, g, store = _family_world(sf)
    _approve(reg, "ilo_like", runtime=True)
    recs, _ = INTL.ilostat_records([irow()], **{**ILO, "source_ref": "ilo_like", "source_edition": "E1"})
    with pytest.raises(CompensationSourceNotApproved, match="D-16"):
        store.import_records(recs, source_ref="ilo_like", source_edition="E1", mode="production")
    assert store.counts() == {"records": 0, "batches": 0}


def test_an_enabled_family_boundary_is_the_only_way_to_a_production_import_and_operational_use(sf, tmp_path):
    raw = json.loads(POLICY_PATH.read_text())
    raw["international_families"]["ilostat"]["enabled"] = True
    f = tmp_path / "enabled.json"
    f.write_text(json.dumps(raw))
    reg, g, store = _family_world(sf, PrecedencePolicy.load(f))
    _approve(reg, "ilo_like", runtime=True)
    recs, _ = INTL.ilostat_records([irow()], **{**ILO, "source_ref": "ilo_like", "source_edition": "E1"})
    assert store.import_records(recs, source_ref="ilo_like", source_edition="E1", mode="production").added == 1
    r = store.records_for([1], "CL")[0]
    assert evidence_status(r, reg, store.policy)["precedence_decided"] is True and evidence_status(r, reg, store.policy)["operational"] is False                # still needs qualification
    store.set_qualification(r["record_key"], "qualified", actor_user_id=1)
    r = store.records_for([1], "CL")[0]
    assert evidence_status(r, reg, store.policy)["operational"] is True
    assert evidence_status(r, reg, PrecedencePolicy.load())["precedence_decided"] is False and evidence_status(r, reg, PrecedencePolicy.load())["operational"] is False      # the default policy never allows it


def test_pending_international_evidence_is_flagged_internally_and_withheld_operationally(world):
    internal = resolve(world, title="syn sa intlonly", country="CL")
    assert internal.outcome is CompensationOutcome.EVIDENCE and internal.precedence_pending is True and internal.evidence_class == "C3" and internal.candidate_presentable is False
    assert any("PENDING owner decision D-16" in x for x in internal.coverage_limitations)
    op = resolve(world, title="syn sa intlonly", country="CL", op=True)
    assert op.outcome is CompensationOutcome.ABSTAIN and op.value is None and op.withheld.get("precedence_decision_pending") == 1 and op.abstention_reason == "evidence_withheld_precedence_decision_pending"


# ====================================================================================================================================== confidence, freshness, fallback
def _resp(**kw):
    base = dict(outcome=CompensationOutcome.EVIDENCE, evidence_class="C1", occupation_specificity="exact", pay_basis="gross", earnings_concept="employment_income", population_scope="employees", evidence_method="survey",
                geography_level="national", precedence_category="national_official_occupation_statistics", candidates=[{"grade": "alias_exact"}], citation={"publisher": "P"}, freshness={"publication_date": "2023-05-01"},
                corroborating=[], precedence_pending=False)
    base.update(kw)
    return CompensationResponse(**base)


def test_evidence_states_are_categorical_explainable_and_never_numerical():
    assert EVIDENCE_STATES == ("SUFFICIENT_EVIDENCE", "LIMITED_EVIDENCE", "AMBIGUOUS", "CONFLICTING", "INSUFFICIENT_EVIDENCE")
    strong = assess_evidence_state(_resp(), record_level="detailed", latest_available=True)
    assert strong["state"] == "SUFFICIENT_EVIDENCE" and strong["weak_factors"] == [] and strong["factors"]["methodological_clarity"] == "clear" and strong["factors"]["classification_certainty"] == "alias_exact"
    assert not any(isinstance(v, (int, float)) for v in strong["factors"].values()) and "confidence" not in json.dumps(strong).lower()
    cases = {"evidence_class_c2": dict(evidence_class="C2"), "evidence_class_c3": dict(evidence_class="C3"), "occupation_not_exact": dict(occupation_specificity="broader_group"),
             "methodology_incompletely_recorded": dict(pay_basis="unknown"), "occupation_classification_not_exact": dict(candidates=[{"grade": "alias_folded"}]),
             "corroborating_source_diverges": dict(corroborating=[{"agrees": False}]), "precedence_decision_pending": dict(precedence_pending=True),
             "crosswalk_not_independently_reviewed": dict(fallback={"qualification": "source_linked"})}
    for weak, change in cases.items():
        a = assess_evidence_state(_resp(**change), record_level="detailed", latest_available=True)
        assert a["state"] == "LIMITED_EVIDENCE" and weak in a["weak_factors"], weak
    assert assess_evidence_state(_resp(), record_level="broad")["state"] == "LIMITED_EVIDENCE"


@pytest.mark.parametrize("outcome,state", [(CompensationOutcome.AMBIGUOUS, "AMBIGUOUS"), (CompensationOutcome.CONFLICT, "CONFLICTING"), (CompensationOutcome.ABSTAIN, "INSUFFICIENT_EVIDENCE"),
                                           (CompensationOutcome.NOT_FOUND, "INSUFFICIENT_EVIDENCE"), (CompensationOutcome.UNSUPPORTED, "INSUFFICIENT_EVIDENCE"), (CompensationOutcome.NOT_CONFIGURED, "INSUFFICIENT_EVIDENCE"),
                                           (CompensationOutcome.INSUFFICIENT_CONTEXT, "INSUFFICIENT_EVIDENCE")])
def test_non_evidence_outcomes_map_to_the_existing_terminology(outcome, state):
    assert assess_evidence_state(CompensationResponse(outcome=outcome))["state"] == state


def test_a_real_resolution_is_sufficient_only_when_every_factor_is_strong(world):
    strong = resolve(world, title="syn sa analyst", country="CL")
    assert strong.evidence_assessment["state"] == "SUFFICIENT_EVIDENCE" and strong.evidence_class == "C1"
    weak = resolve(world, title="syn sa analyst", country="AR")                                              # basis not recorded in that source
    assert weak.evidence_assessment["state"] == "LIMITED_EVIDENCE" and "methodology_incompletely_recorded" in weak.evidence_assessment["weak_factors"]
    assert resolve(world, title="syn sa engineer", country="CL").evidence_assessment["state"] == "AMBIGUOUS"
    assert resolve(world, title="syn sa concepts", country="CL").evidence_assessment["state"] == "CONFLICTING"
    assert resolve(world, title="syn sa nodata", country="CL").evidence_assessment["state"] == "INSUFFICIENT_EVIDENCE"


def test_freshness_is_reported_as_recorded_and_never_replaced_by_todays_date(world):
    r = resolve(world, title="syn sa stale", country="CL")
    f = r.freshness
    assert f["reference_year"] == 2023 and f["publication_date"] is None and f["source_retrieved_at"] is None and f["describes_current_market_pay"] is False and f["source_edition"] == "FX-SA-1B"
    assert r.evidence_assessment["factors"]["freshness"] == "reference_year_recorded_publication_date_unknown" and r.evidence_assessment["factors"]["reference_year_is_latest_available"] == "yes"
    old = resolve(world, title="syn sa stale", country="CL", reference_year=2019)
    assert old.freshness["reference_year"] == 2019 and old.evidence_assessment["factors"]["reference_year_is_latest_available"] == "no"


def test_the_fallback_trace_names_the_stage_and_never_uses_another_country(world):
    exact = resolve(world, title="syn sa analyst", country="CL").fallback_trace
    broader = resolve(world, title="syn sa child", country="CL")
    assert exact["selected_stage"] == "exact_occupation" and exact["other_country_evidence_used"] is False and exact["eligible_records_by_class_at_selected_stage"]["C1"] == 1
    assert broader.fallback_trace["selected_stage"] is None and broader.fallback_trace["broader_context_records"] == 1 and broader.value is None and broader.outcome.value == "abstain"
    assert broader.contextual_evidence[0]["evidence_class"] == "C2" and broader.contextual_evidence[0]["broader_occupation_code"]
    none = resolve(world, title="syn sa nodata", country="CL").fallback_trace
    assert none["selected_stage"] is None and none["eligible_records_by_class_at_selected_stage"] == {"C1": 0, "C2": 0, "C3": 0}
    c3 = resolve(world, title="syn sa intlonly", country="CL")
    assert c3.evidence_class == "C3" and c3.fallback_trace["eligible_records_by_class_at_selected_stage"]["C3"] == 1 and c3.occupation_specificity == "exact"      # a lower tier keeps its own class


def test_a_national_source_outranks_a_comparable_international_one_and_incompatible_ones_are_a_conflict(world):
    best = resolve(world, title="syn sa precedence", country="CL")
    assert best.evidence_class == "C1" and best.value == "900" and len(best.corroborating) == 1 and best.corroborating[0]["agrees"] is False and best.corroborating[0]["precedence_category"] == "eurostat_harmonised"
    assert resolve(world, title="syn sa incompatible", country="CL").outcome is CompensationOutcome.CONFLICT
    assert resolve(world, title="syn sa confsrc", country="CL").abstention_reason == "comparable_sources_of_equal_precedence_disagree"


# ====================================================================================================================================== comparison safety
def _ev(**kw):
    base = dict(outcome=CompensationOutcome.EVIDENCE, value="1500.00", currency="USD", pay_period="monthly", measure="median", percentile=0, pay_basis="gross", earnings_concept="employment_income",
                population_scope="employees", evidence_method="survey", reference_year=2023, evidence_class="C1", occupation_specificity="exact", occupation_level="detailed", geography_level="national",
                country="US", operational=False)
    base.update(kw)
    return CompensationResponse(**base)


def test_nominal_comparison_requires_everything_to_match_and_returns_an_exact_difference():
    c = compare_nominal(_ev(value="12000.50", country="EC"), _ev(value="11999.25"))
    assert c.status is ComparisonStatus.COMPARABLE_NOMINAL and c.difference == Decimal("-1.25") and isinstance(c.difference, Decimal) and c.operational is False
    assert any("different_countries" in x for x in c.caveats) and "non_operational_evidence" in c.caveats and c.to_public_dict()["difference"] == "-1.25"
    assert compare_nominal(_ev(operational=True), _ev(operational=True)).operational is True
    for change, reason in ((dict(currency="CLP"), "currency_differs"), (dict(pay_period="hourly"), "pay_period_differs"), (dict(measure="mean"), "statistic_differs"), (dict(pay_basis="net"), "pay_basis_differs"),
                           (dict(reference_year=2022), "reference_year_differs"), (dict(evidence_class="C3"), "evidence_class_differs"), (dict(occupation_level="broad"), "occupation_granularity_differs"),
                           (dict(occupation_specificity="broader_group"), "occupation_specificity_differs"), (dict(geography_level="regional"), "geography_level_differs"),
                           (dict(earnings_concept="wage_statistic"), "earnings_concept_differs"), (dict(population_scope="all_workers"), "population_scope_differs"), (dict(evidence_method="administrative_records"), "evidence_method_differs")):
        c = compare_nominal(_ev(), _ev(**change))
        assert c.status is ComparisonStatus.NOT_COMPARABLE and reason in c.reasons and c.difference is None, reason


def test_an_unknown_definition_is_never_comparable_and_a_missing_side_is_unavailable():
    for field_name, reason in (("pay_basis", "pay_basis_unknown"), ("earnings_concept", "earnings_concept_unknown"), ("population_scope", "population_scope_unknown"), ("evidence_method", "evidence_method_unknown")):
        c = compare_nominal(_ev(**{field_name: "unknown"}), _ev(**{field_name: "unknown"}))
        assert c.status is ComparisonStatus.NOT_COMPARABLE and reason in c.reasons                           # even identical unknowns are not comparable across markets
    for other in (CompensationOutcome.ABSTAIN, CompensationOutcome.CONFLICT, CompensationOutcome.AMBIGUOUS):
        c = compare_nominal(_ev(), CompensationResponse(outcome=other))
        assert c.status is ComparisonStatus.UNAVAILABLE and c.difference is None and f"second_has_no_evidence_{other.value}" in c.reasons


def test_different_currencies_are_never_converted_and_fx_and_ppp_are_not_configured():
    c = compare_nominal(_ev(currency="CLP"), _ev(currency="ARS"))
    assert c.status is ComparisonStatus.NOT_COMPARABLE and "currency_differs" in c.reasons and "fx_comparison_not_configured" in c.caveats and c.difference is None

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("a provider was used")
    for fn, mode in ((compare_fx, "fx_converted"), (compare_ppp, "ppp_adjusted")):
        out = fn(_ev(currency="CLP"), _ev(currency="USD"), provider=Boom(), as_of=2023)
        assert out.status is ComparisonStatus.NOT_CONFIGURED and out.difference is None and any(mode in r and "D-10" in r for r in out.reasons)
        assert fn(_ev(), _ev()).status is ComparisonStatus.NOT_CONFIGURED                                    # even a matching pair is never converted


# ====================================================================================================================================== corpus
def test_the_corpus_is_synthetic_only_and_flags_the_d16_stand_in(corpus):
    assert "SYNTHETIC" in corpus["note"] and "D-16" in corpus["note"] and all(s["publisher"].endswith("(fixture)") for s in corpus["sources"])
    assert {s["source_id"] for s in corpus["sources"] if s.get("provenance")} == {"fx_ilo"} and len(corpus["cases"]) >= 55 and len(corpus["comparisons"]) >= 8
    assert all(n["label"].endswith("[synthetic fixture]") for b in corpus["nodes"] for n in b["rows"])


def test_every_block_case_and_comparison_matches_and_no_value_is_invented(world, corpus):
    assert [b for b in evaluate_blocks(world, corpus) if not b["ok"]] == []
    results = evaluate_cases(world, corpus)
    assert [r for r in results if not r["ok"]] == []
    assert not any(r["invented_value"] for r in results) and not any(r["operational"] or r["presentable"] for r in results)
    assert [c for c in evaluate_comparisons(world, corpus) if not c["ok"]] == []
    cats = {r["category"] for r in results}
    for needed in ("south_america_national", "regional", "granularity", "concepts", "populations", "international", "conflict", "freshness", "taxonomy", "missing_mapping", "unsupported", "ambiguity",
                   "precedence", "c4", "comparison", "geography_independence", "approval", "currency"):
        assert needed in cats, needed
    for cc in ("AR", "BO", "CL", "CO", "EC", "GY", "PY", "PE", "SR", "UY", "VE"):
        assert next(r for r in results if r["id"] == f"sa-{cc.lower()}-national")["outcome"] == "evidence"


def test_the_default_withholds_everything_that_is_not_operational(world):
    for cc in ("CL", "AR", "EC"):
        r = resolve(world, title="syn sa analyst", country=cc, op=True)
        assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.evidence_class == "C4" and r.abstention_reason == "evidence_exists_but_is_not_operational"


def test_a_qualified_runtime_approved_source_is_presentable_through_the_same_resolver(sf):
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), None
    from src.knowledge_foundation.aliases import AliasStore
    a = AliasStore(sf)
    tax.seed()
    reg.register("real_sa", origin="official_local", publisher="Synthetic publisher", dataset_name="Synthetic dataset", dataset_version="E1", precedence_category="national_official_occupation_statistics", validation_status="unvalidated")
    _approve(reg, "real_sa", runtime=True)
    node = g.add_occupation("Synthetic", [("isco", "08", "9701")])["occupation_key"]
    a.add_alias(node, "mechanism title", language="en", language_basis="curated_manual", alias_type="recognized_title")
    store = CompensationStoreV2(sf, reg, g)
    recs, _ = CA.south_america_records("CL", [row()], source_ref="real_sa", source_edition="E1", taxonomy_edition="08", reference_year=2023, **SAM)
    assert store.import_records(recs, source_ref="real_sa", source_edition="E1", mode="production").added == 1
    res = CompensationResolver(store, OccupationResolver(g, a, registry=reg), g, reg)
    q = CompensationRequest(occupation=MultilingualRequest(title="mechanism title", title_language="en"), country="CL")
    assert res.resolve(q).abstention_reason == "evidence_exists_but_is_not_operational"
    store.set_qualification(store.records_for([1], "CL")[0]["record_key"], "qualified", actor_user_id=2)
    ok = res.resolve(q)
    assert ok.outcome is CompensationOutcome.EVIDENCE and ok.operational and ok.candidate_presentable and ok.evidence_assessment["state"] == "SUFFICIENT_EVIDENCE"


def test_concurrent_identical_south_america_imports_yield_one_set(world):
    recs, _ = sa("CL", [row(code="9702", value="123"), row(code="9702", value="124", region="RM")])
    recs = [r.model_copy(update={"source_ref": "fx_sa_stat", "source_edition": "FX-CONC"}) for r in recs]
    gate, out = threading.Barrier(5), []

    def go():
        gate.wait()
        try:
            out.append(world.store.import_records(recs, source_ref="fx_sa_stat", source_edition="FX-CONC", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sum(1 for r in out if not isinstance(r, str) and r.added == 2) == 1 and not [r for r in out if isinstance(r, str)]


# ====================================================================================================================================== reports and registers
def test_the_global_coverage_report_keeps_statuses_separate_and_claims_nothing():
    rep = GR.coverage_report(ROOT)
    assert rep == json.loads((ROOT / "docs/capstone/p10/p10c_e/GLOBAL_COVERAGE_REPORT.json").read_text()) and set(rep["markets"]) == set(GR.MARKETS) | {"INTL"} and len(rep["markets"]) == 17
    assert rep["operational_markets"] == [] and rep["qualified_markets"] == [] and "global coverage is not claimed" in rep["note"]
    for m, v in rep["markets"].items():
        assert v["adapter_is_operational_coverage"] is False and v["operational_today"] is False and not v["statuses"]["evidence_qualified"] and not v["statuses"]["runtime_use_approved"] and v["statuses"]["data_imported"] == 0
        assert {"taxonomy_acquired", "taxonomy_edition_known", "occupation_nodes_available", "crosswalk_available", "licence_verified", "approved_for_ingestion", "data_imported", "evidence_qualified", "runtime_use_approved"} <= set(v["statuses"])
    for cc in WIDER_SA_PROFILES:
        v = rep["markets"][cc]
        assert v["isco08_structure_held_locally"] is True and v["national_occupation_classification"].startswith("UNKNOWN") and v["adapter"].startswith("south_america_records") and v["coverage_levels"]["compensation_level"] in ("targeted", "source_identified")
    assert rep["markets"]["INTL"]["precedence_decision"] == "PENDING OWNER DECISION D-16" and rep["markets"]["US"]["local_v1_records"] == 1386 and rep["markets"]["GB"]["local_v1_records"] == 527


def test_the_source_approval_register_proposes_everything_and_approves_nothing():
    reg = GR.approval_register(ROOT)
    assert reg == json.loads((ROOT / "docs/capstone/p10/p10c_e/SOURCE_APPROVAL_REGISTER.json").read_text()) and reg["approved_entries"] == []
    ids = {e["register_id"] for e in reg["entries"]}
    assert len(ids) == len(reg["entries"]) >= 30 and {"reg:bls_oews", "reg:ons_ashe", "reg:eurostat_earnings", "cand:intl_ilostat", "cand:cl_esi", "cand:co_geih", "link:us_soc_structure", "link:uk_soc_2020_structure", "link:us_soc_crosswalk", "link:uk_soc_crosswalk"} <= ids
    for e in reg["entries"]:
        assert e["status"] == "PROPOSED" and e["decisions_required"] and e["commercial_use"] == "UNKNOWN"
        assert all(d["id"].startswith("D-") for d in e["decisions_required"]) and e["current_lifecycle_state"] in ("LICENSING_PENDING", "RESTRICTED", "SOURCE_IDENTIFIED")
    ilo = next(e for e in reg["entries"] if e["register_id"] == "cand:intl_ilostat")
    assert ilo["proposed_evidence_class"] == "C3" and "D-16" in ilo["proposed_precedence_category"] and any(d["id"] == "D-16" for d in ilo["decisions_required"]) and "never operational" in ilo["proposed_operational_use"]
    assert set(next(e for e in reg["entries"] if e["register_id"] == "link:us_soc_structure")["linked_blockers"]) >= {"US-T1", "US-G1", "US-D1"} and "GB-D1" in next(e for e in reg["entries"] if e["register_id"] == "link:uk_soc_2020_structure")["linked_blockers"]
    cands = json.loads((ROOT / "src/knowledge_foundation/data/global_source_candidates.json").read_text())
    assert "CANDIDATE" in cands["note"] and len(cands["candidates"]) == 12 and all("(candidate)" in c["publisher"] for c in cands["candidates"]) and not {"licence", "edition"} & set(cands["candidates"][0])


def test_the_coverage_matrix_levels_for_wider_south_america_are_unchanged_and_nothing_is_qualified():
    rows = {r["code"]: r for r in json.loads((ROOT / "src/knowledge_foundation/data/coverage_matrix.json").read_text())["geographies"]}
    for cc in WIDER_SA_PROFILES:
        r = rows[cc]
        assert r["taxonomy_level"] == "targeted" and r["crosswalk_level"] == "targeted" and r["compensation_level"] == ("source_identified" if cc in ("CL", "CO") else "targeted")
        assert "qualified" not in (r["taxonomy_level"], r["crosswalk_level"], r["compensation_level"], r["outlook_level"]) and r["source_languages"] == [] and r["source_ids"] == []
        assert "P10C-E" in r["limitations"] and "nothing is qualified" in r["limitations"]


# ====================================================================================================================================== isolation, gates, scripts
def test_nothing_new_is_imported_by_a_runtime_or_candidate_path_and_no_migration_exists():
    offenders = []
    for pkg in ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents", "src/billing"):
        for f in (ROOT / pkg).rglob("*.py"):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []
    versions = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    assert versions[-1].startswith("0038_") and len(versions) == 38                                              # P10C-E needs no schema change
    for rel in ("src/copilot/knowledge/compensation.py", "src/copilot/knowledge/retrieval.py", "src/copilot/knowledge/router.py"):
        assert "knowledge_foundation" not in (ROOT / rel).read_text(), rel


def test_no_new_module_downloads_converts_or_reads_a_protected_store():
    banned = {"requests", "httpx", "urllib", "stripe", "openai", "boto3", "aiohttp", "socket", "pandas"}
    for f in list((ROOT / "src/knowledge_foundation").glob("*.py")) + list((ROOT / "src/knowledge_foundation/compensation").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & banned, (f.name, mods & banned)
    for f in (ROOT / "src/knowledge_foundation/compensation").glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            assert not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and any(isinstance(x, ast.Constant) and x.value in (12, 52, 260, 2080, 40) for x in (n.left, n.right))), (f.name, n.lineno)
        assert "data/knowledge" not in f.read_text(encoding="utf-8"), f.name


def test_all_gates_stay_off():
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    assert not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED])
    for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, g) is False


def test_no_client_path_can_import_approve_or_compare_country_data():
    for f in (ROOT / "src/api").rglob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert not any(x in t for x in ("south_america_records", "ilostat_records", "compare_nominal", "approval_register", "CompensationStoreV2")), f


def _run(name, *args, cwd):
    import subprocess
    import sys
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True, cwd=cwd)


def test_the_new_scripts_validate_output_first_and_read_no_local_store(tmp_path):
    for target in ("data/x", "evaluations/y"):
        r = _run("p10ce_reports.py", "--out-dir", str(ROOT / target), cwd=tmp_path)
        assert r.returncode == 2 and "refusing" in r.stderr and not (ROOT / target).exists()
    r = _run("bench_global_fallback.py", "--out", str(ROOT / "data/bench.json"), cwd=tmp_path)
    assert r.returncode == 2 and "refusing" in r.stderr and not (ROOT / "data/bench.json").exists()
    out = tmp_path / "reports"
    r = _run("p10ce_reports.py", "--out-dir", str(out), cwd=tmp_path)
    assert r.returncode == 0 and json.loads((out / "SOURCE_APPROVAL_REGISTER.json").read_text())["approved_entries"] == [] and json.loads((out / "GLOBAL_COVERAGE_REPORT.json").read_text())["operational_markets"] == []


def test_a_larger_multi_market_dataset_resolves_quickly_with_bounded_queries(sf):
    import time
    from sqlalchemy import event
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation.country_import import import_taxonomy_nodes
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    reg.register("fx_t", origin="synthetic_fixture", publisher="P", dataset_name="D")
    reg.register("fx_n", origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_official_occupation_statistics")
    store = CompensationStoreV2(sf, reg, g)
    n = 150
    import_taxonomy_nodes(g, a, reg, [{"code": f"{1000 + i}", "label": f"Synthetic {i}"} for i in range(n)], scheme="isco", edition="08", source_ref="fx_t", mode="fixture")
    t0 = time.perf_counter()
    total = 0
    for cc, cur in (("AR", "ARS"), ("CL", "CLP"), ("CO", "COP"), ("EC", "USD"), ("UY", "UYU")):
        recs, _ = CA.south_america_records(cc, [row(code=f"{1000 + i}", value=str(500 + i), currency=cur) for i in range(n)], source_ref="fx_n", source_edition="E1", taxonomy_edition="08", reference_year=2023, **SAM)
        total += store.import_records(recs, source_ref="fx_n", source_edition="E1", mode="fixture").added
    assert total == n * 5 and time.perf_counter() - t0 < 60
    counter = {"n": 0}

    @event.listens_for(sf.kw["bind"], "before_cursor_execute")
    def _c(conn, cur, st, par, ctx, many):
        counter["n"] += 1
    res = CompensationResolver(store, OccupationResolver(g, a), g, reg)
    t1, peak = time.perf_counter(), 0
    for i in range(0, n, 5):
        for cc in ("AR", "EC"):
            before = counter["n"]
            r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="isco", taxonomy_code=f"{1000 + i}", taxonomy_edition="08"), country=cc, require_operational=False))
            peak = max(peak, counter["n"] - before)
            assert r.outcome is CompensationOutcome.EVIDENCE and r.value == str(500 + i)
    assert (time.perf_counter() - t1) * 1000 / 60 < 100 and peak < 40
