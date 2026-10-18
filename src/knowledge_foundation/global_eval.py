"""P10C-G global evaluation corpus and negative-regression runner. Offline, deterministic and independent of every developer-local store: each run builds throwaway SQLite databases in its own
temporary directory, loads the committed SYNTHETIC corpus through the EXISTING loader, resolvers, registry and policy, runs the governance and negative-regression checks and disposes of
what it created. It reuses the existing architecture (``compensation.fixtures``, ``CompensationResolver``, ``SourceRegistry``, ``OccupationGraph``, ``AliasStore``, ``ashe_suppression``); it
adds no evaluator engine, no lifecycle state and no runtime path. Nothing here qualifies a source, approves evidence, converts a currency or touches a protected store."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

CORPUS_PATH = Path(__file__).parent / "data" / "global_evaluation_corpus.json"
RESULT_SCHEMA = "p10c-g-results/1"

# The complete list of required evidence tags (sections 6 to 11 of the P10C-G specification). Every tag must be exercised by at least one corpus case or governance check.
REQUIRED_TAGS: dict[str, list[str]] = {
    "occupation_classification": ["occupation:exact_code", "occupation:official_title", "occupation:curated_alias_proposal", "occupation:unqualified_alias", "occupation:ambiguous_title",
                                  "occupation:unsupported_title", "occupation:wrong_taxonomy_edition", "occupation:wrong_country", "occupation:missing_classification", "occupation:broad_occupation",
                                  "occupation:detailed_occupation", "occupation:conflicting_candidates", "occupation:revoked_mapping", "occupation:missing_provenance"],
    "compensation_evidence": ["compensation:exact_measurement", "compensation:unsupported_measurement", "compensation:mean_vs_median", "compensation:percentile", "compensation:hourly_vs_annual",
                              "compensation:weekly_vs_annual", "compensation:full_time_vs_part_time", "compensation:national_vs_regional", "compensation:detailed_vs_broad",
                              "compensation:different_taxonomy_editions", "compensation:publication_periods", "compensation:source_revisions", "compensation:missing_measurements",
                              "compensation:suppressed_measurements", "compensation:expired_or_revoked_evidence", "compensation:conflicting_sources", "compensation:unqualified_source",
                              "compensation:unapproved_source", "compensation:incomplete_provenance", "compensation:no_hidden_period_conversion", "compensation:no_unauthorised_currency_conversion",
                              "compensation:unsupported_comparison_rejected", "compensation:no_silent_broader_substitution", "compensation:no_cross_country_substitution"],
    "fallback_and_abstention": ["fallback:country_native_detailed", "fallback:country_native_broad", "fallback:authorised_international", "fallback:unavailable_national_evidence",
                                "fallback:insufficient_occupation_specificity", "fallback:conflicting_national_and_international", "fallback:unapproved_harmonised_mapping",
                                "fallback:missing_currency_conversion", "fallback:missing_ppp_conversion", "fallback:unsupported_geography", "fallback:c3_not_promoted_to_c1", "fallback:c4_abstains"],
    "multilingual": ["multilingual:official_title", "multilingual:authorised_alias", "multilingual:ambiguous_translation", "multilingual:unsupported_translation", "multilingual:accent_normalisation",
                     "multilingual:cross_language_collision", "multilingual:incorrect_language_country_assumption", "multilingual:unqualified_mapping", "multilingual:no_lexical_equivalence"],
    "lifecycle_and_governance": ["lifecycle:source_identified", "lifecycle:licence_pending", "lifecycle:ingestion_approved", "lifecycle:engineering_checked", "lifecycle:human_qualified",
                                 "lifecycle:runtime_approved", "lifecycle:revoked", "source:unapproved_never_operational", "source:unqualified_never_operational", "source:incomplete_provenance"],
    "negative_regression": ["negative:fabricated_mapping", "negative:invented_compensation", "negative:unapproved_source_promotion", "negative:unqualified_evidence_operational",
                            "negative:cross_country_substitution", "negative:incorrect_currency_assumption", "negative:suppressed_reconstruction", "negative:revoked_evidence_reuse",
                            "negative:silent_broader_substitution", "negative:incomplete_provenance", "negative:wrong_taxonomy_edition", "negative:unsupported_statistical_comparison",
                            "negative:false_reviewer_approval", "negative:licensing_bypass"],
}
JURISDICTIONS = ("US", "GB", "DE", "FR", "CA", "MX", "BR", "CL")
PER_JURISDICTION_CASES = ("exact-code", "official-title", "wrong-edition", "broad-evidence", "child-abstains-with-context", "other-country-never-falls-back", "operational-withheld")


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_corpus(corpus: dict[str, Any]) -> list[str]:
    """Fixture integrity: versioned schema, stable unique ids, synthetic labelling, explicit source and qualification state on every case, scenario references that exist."""
    errs: list[str] = []
    if corpus.get("schema") != "p10c-g/1" or not corpus.get("corpus_version"):
        errs.append("schema or corpus_version missing")
    if "SYNTHETIC" not in corpus.get("note", ""):
        errs.append("the corpus note must state that it is synthetic")
    ids = [c["id"] for c in corpus["cases"]]
    if len(ids) != len(set(ids)):
        errs.append("duplicate case ids")
    scen = {s["id"] for s in corpus["scenarios"]}
    if len(scen) != len(corpus["scenarios"]):
        errs.append("duplicate scenario ids")
    for c in corpus["cases"]:
        for k in ("id", "category", "scenario", "request", "expect", "tags", "source_state", "evidence_origin", "qualification_state"):
            if k not in c:
                errs.append(f"{c.get('id')}: missing {k}")
        if c.get("evidence_origin") != "SYNTHETIC":
            errs.append(f"{c['id']}: not labelled synthetic")
        if c.get("scenario") not in scen:
            errs.append(f"{c['id']}: unknown scenario")
        if c.get("internal") is False and c.get("qualification_state") != "SOURCE_QUALIFICATION_PENDING":
            errs.append(f"{c['id']}: an operational-mode case must record SOURCE_QUALIFICATION_PENDING")
    for s in corpus["sources"]:
        if s["source_id"] not in corpus["source_editions"] and s["source_id"] != "fx_occ":
            errs.append(f"{s['source_id']}: no edition")
    for key in JURISDICTIONS:
        for suffix in PER_JURISDICTION_CASES:
            if f"{key.lower()}-{suffix}" not in set(ids):
                errs.append(f"jurisdiction {key}: missing case {suffix}")
    return errs


@contextmanager
def _temp_world():
    d = Path(tempfile.mkdtemp(prefix="p10cg_"))
    engines = []
    try:
        from src.persistence import init_db, make_engine, make_session_factory

        def make(name="g.db"):
            e = make_engine(f"sqlite:///{d / name}")
            init_db(e)
            engines.append(e)
            return make_session_factory(e)
        yield make
    finally:
        for e in engines:
            e.dispose()
        shutil.rmtree(d, ignore_errors=True)


def run_corpus(corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load the corpus into a throwaway world through the existing loader and evaluate every case. Also verifies that no scenario record was rejected at import."""
    from src.knowledge_foundation.compensation import fixtures as F

    corpus = corpus or load_corpus()
    with _temp_world() as make:
        sf = make()
        world = F.load_world(sf, corpus)
        import_rejections = {sid: r.rejections for sid, r in world.reports.items() if r.rejected}
        results = F.evaluate_cases(world, corpus)
        fixture_only = all(world.reg.get(s["source_id"])["origin"] == "synthetic_fixture" for s in corpus["sources"])
        none_serve = not any(world.reg.can_serve_as_evidence(s["source_id"]) or world.reg.can_ingest(s["source_id"]) for s in corpus["sources"])
    by_id = {c["id"]: c for c in corpus["cases"]}
    for r in results:
        r["tags"] = by_id[r["id"]]["tags"]
    return {"cases": results, "passed": sum(1 for r in results if r["ok"]), "total": len(results), "import_rejections": import_rejections, "fixture_sources_only": fixture_only,
            "no_source_can_serve_as_evidence": none_serve, "invented_values": sum(1 for r in results if r["invented_value"]), "presentable_or_operational": sum(1 for r in results if r["presentable"] or r["operational"]),
            "meta_check_rejects_a_wrong_expectation": _evaluator_can_fail(corpus)}


def _evaluator_can_fail(corpus: dict[str, Any]) -> bool:
    """The evaluator itself must be able to fail: a deliberately wrong expectation must be reported as a failure."""
    from src.knowledge_foundation.compensation import fixtures as F

    bad = {**corpus, "cases": [{**corpus["cases"][0], "expect": {**corpus["cases"][0]["expect"], "outcome": "unsupported"}}]}
    with _temp_world() as make:
        world = F.load_world(make(), corpus)
        return F.evaluate_cases(world, bad)[0]["ok"] is False


# ------------------------------------------------------------------------------------------------------------------------------------------------ governance
def _world(make):
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation.resolver import CompensationResolver
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.occupation_resolver import OccupationResolver
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue

    sf = make()
    tax, reg, g, al = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    tax.ensure("soc", "2018", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{2}-[0-9]{4}")
    tax.ensure("uk_soc", "2020", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{1,4}")
    store = CompensationStoreV2(sf, reg, g)
    return type("W", (), dict(sf=sf, reg=reg, g=g, al=al, store=store, tax=tax, res=CompensationResolver(store, OccupationResolver(g, al, registry=reg), g, reg)))


def _official_source(w, sid="gov_src", **kw):
    w.reg.register(sid, origin="official_local", publisher="Synthetic official publisher", dataset_name="Synthetic official dataset", dataset_version="E1", source_url="https://example.invalid/g",
                   precedence_category="national_official_occupation_statistics", validation_status="unvalidated", **kw)


def _record(source="gov_src", code="99-0001", **kw):
    from src.knowledge_foundation.compensation.record import CompensationRecordV2

    base = dict(taxonomy_scheme="soc", taxonomy_edition="2018", native_code=code, occupation_level="detailed", country="US", geography_level="national", currency="USD", pay_period="annual",
                pay_basis="gross", measure="median", earnings_concept="wage_statistic", population_scope="employees", evidence_method="survey", value=Decimal("60000"), source_ref=source,
                source_edition="E1", reference_year=2025)
    base.update(kw)
    return CompensationRecordV2(**base)


def _ask(w, title=None, code=None, country="US", operational=False, **kw):
    from src.knowledge_foundation.compensation.resolver import CompensationRequest
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest

    occ = MultilingualRequest(title=title, title_language="en" if title else None, taxonomy_scheme="soc" if code else None, taxonomy_code=code, taxonomy_edition="2018" if code else None)
    return w.res.resolve(CompensationRequest(occupation=occ, country=country, require_operational=operational, pay_period="annual", measure="median", **kw))


def _approve(w, sid, runtime=False):
    w.reg.transition(sid, "licensing_pending")
    w.reg.set_licence(sid, licence_id="synthetic", licence_status="verified")
    w.reg.transition(sid, "licensing_verified")
    w.reg.transition(sid, "approved_for_ingestion")
    if runtime:
        w.reg.transition(sid, "approved_for_runtime_use")


def chk_lifecycle_ladder(make):
    w = _world(make)
    _official_source(w)
    steps = []

    def snap(label):
        r = w.reg.get("gov_src")
        steps.append((label, r["approval_status"], w.reg.can_ingest("gov_src"), w.reg.can_serve_as_evidence("gov_src")))
    snap("source_identified")
    w.reg.transition("gov_src", "licensing_pending")
    snap("licence_pending")
    w.reg.set_licence("gov_src", licence_id="synthetic", licence_status="verified")
    w.reg.transition("gov_src", "licensing_verified")
    snap("licensing_verified")
    w.reg.transition("gov_src", "approved_for_ingestion")
    snap("ingestion_approved")
    w.reg.transition("gov_src", "approved_for_runtime_use")
    snap("runtime_approved")
    w.reg.transition("gov_src", "restricted", reason="synthetic revocation")
    snap("revoked")
    exp = [("source_identified", "discovered", False, False), ("licence_pending", "licensing_pending", False, False), ("licensing_verified", "licensing_verified", False, False),
           ("ingestion_approved", "approved_for_ingestion", True, False), ("runtime_approved", "approved_for_runtime_use", True, True), ("revoked", "restricted", False, False)]
    return steps == exp, "; ".join(f"{a}={b}" for a, b, *_ in steps)


def chk_unqualified_never_operational(make):
    w = _world(make)
    _official_source(w)
    _approve(w, "gov_src", runtime=True)
    node = w.g.add_occupation("synthetic occupation", [("soc", "2018", "99-0001")])
    w.al.add_alias(node["occupation_key"], "synthetic occupation", language="en", language_basis="curated_manual", alias_type="recognized_title")
    w.store.import_records([_record()], source_ref="gov_src", source_edition="E1", mode="production")
    key = w.store.records_for([1], "US")[0]["record_key"]
    states = []
    states.append(_ask(w, "synthetic occupation", operational=True).abstention_reason)                         # unqualified: exists in the graph and the database, still withheld
    w.store.set_qualification(key, "engineering_checked", actor_user_id=None)
    states.append(_ask(w, "synthetic occupation", operational=True).abstention_reason)                         # engineering-checked is not qualified
    w.store.set_qualification(key, "qualified", actor_user_id=7)                                                # synthetic test actor: a mechanism check, not a real approval
    open_ = _ask(w, "synthetic occupation", operational=True)
    w.reg.transition("gov_src", "restricted", reason="synthetic revocation")
    revoked = _ask(w, "synthetic occupation", operational=True)
    ok = (states == ["evidence_exists_but_is_not_operational"] * 2 and open_.candidate_presentable and open_.value == "60000" and revoked.value is None and not revoked.candidate_presentable)
    return ok, f"unqualified={states[0]}; engineering_checked={states[1]}; all gates open presentable={open_.candidate_presentable}; after revocation value={revoked.value}"


def chk_unapproved_promotion_and_licensing_bypass(make):
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved
    from src.knowledge_foundation.registry import RegistryError

    w = _world(make)
    w.reg.register("fx", origin="synthetic_fixture", publisher="Synthetic", dataset_name="Synthetic", precedence_category="national_official_occupation_statistics")
    _official_source(w)
    out = []
    for name, fn in (("fixture_cannot_be_approved", lambda: w.reg.transition("fx", "approved_for_ingestion")),
                     ("pending_source_cannot_import", lambda: w.store.import_records([_record()], source_ref="gov_src", source_edition="E1", mode="production")),
                     ("cannot_skip_the_lifecycle", lambda: w.reg.transition("gov_src", "approved_for_ingestion")),
                     ("no_approval_without_verified_licence", lambda: (w.reg.transition("gov_src", "licensing_pending"), w.reg.transition("gov_src", "licensing_verified"), w.reg.transition("gov_src", "approved_for_ingestion"))),
                     ("verified_licence_cannot_be_downgraded_while_approved", lambda: (w.reg.set_licence("gov_src", licence_id="synthetic", licence_status="verified"), w.reg.transition("gov_src", "approved_for_ingestion"), w.reg.set_licence("gov_src", licence_id=None, licence_status="unknown")))):
        try:
            fn()
            out.append((name, "NOT REFUSED"))
        except (RegistryError, CompensationSourceNotApproved):
            out.append((name, "refused"))
    return all(v == "refused" for _, v in out), ", ".join(f"{n}={v}" for n, v in out)


def chk_false_reviewer_approval(make):
    from src.knowledge_foundation.aliases import AliasError, AliasStore
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.knowledge_foundation.qualification_review import ReviewAuthorityError, reviewer_authority, reviewer_check_for

    w = _world(make)
    _official_source(w)
    _approve(w, "gov_src")
    node = w.g.add_occupation("synthetic occupation", [("soc", "2018", "99-0001")])
    w.store.import_records([_record()], source_ref="gov_src", source_edition="E1", mode="production")
    key = w.store.records_for([1], "US")[0]["record_key"]
    a = w.al.add_alias(node["occupation_key"], "synthetic title", language="en", language_basis="curated_manual", alias_type="recognized_title", source_ref="gov_src")
    refused = []
    for name, fn in (("record_without_reviewer", lambda: w.store.set_qualification(key, "qualified", actor_user_id=None)),
                     ("alias_without_reviewer", lambda: w.al.set_qualification(a["id"], "qualified", actor_user_id=None)),
                     ("record_with_invented_reviewer_id_when_authority_is_wired", lambda: CompensationStoreV2(w.sf, w.reg, w.g, reviewer_check=reviewer_check_for(w.sf, "measurement_reviewer")).set_qualification(key, "qualified", actor_user_id=424242)),
                     ("alias_with_invented_reviewer_id_when_authority_is_wired", lambda: AliasStore(w.sf, reviewer_check=reviewer_check_for(w.sf, "alias_reviewer")).set_qualification(a["id"], "qualified", actor_user_id=424242)),
                     ("authority_check_unknown_account", lambda: reviewer_authority(w.sf(), 424242, "measurement_reviewer"))):
        try:
            fn()
            refused.append((name, "NOT REFUSED"))
        except (ValueError, AliasError, ReviewAuthorityError):
            refused.append((name, "refused"))
    new_alias_state = w.al.aliases_for(node["occupation_key"])[0]["qualification_status"]
    return all(v == "refused" for _, v in refused) and new_alias_state == "unqualified", ", ".join(f"{n}={v}" for n, v in refused) + f"; a new alias is {new_alias_state}"


def chk_fabricated_mapping(make):
    from src.knowledge_foundation.graph import GraphError

    w = _world(make)
    _official_source(w)
    a = w.g.add_occupation("synthetic A", [("soc", "2018", "99-0001")])["occupation_key"]
    b = w.g.add_occupation("synthetic B", [("soc", "2018", "99-0002")])["occupation_key"]
    out = []
    for name, kw in (("equivalent_from_a_derived_rule", dict(relationship_type="equivalent", basis="derived_rule", mapping_status="partial", limitations="x")),
                     ("verified_without_a_source_provided_basis", dict(relationship_type="broader", basis="curated_manual", mapping_status="verified", source_ref="gov_src")),
                     ("verified_with_no_source", dict(relationship_type="broader", basis="source_provided", mapping_status="verified", source_ref="")),
                     ("derived_rule_without_a_stated_limitation", dict(relationship_type="related", basis="derived_rule", mapping_status="partial")),
                     ("unregistered_source", dict(relationship_type="broader", basis="source_provided", mapping_status="verified", source_ref="not_registered"))):
        try:
            w.g.add_relationship(a, b, from_taxonomy=("soc", "2018"), to_taxonomy=("soc", "2018"), **kw)
            out.append((name, "NOT REFUSED"))
        except GraphError:
            out.append((name, "refused"))
    try:
        w.g.add_relationship(a, a, relationship_type="related", basis="curated_manual", mapping_status="partial", from_taxonomy=("soc", "2018"), to_taxonomy=("soc", "2018"))
        out.append(("self_relationship", "NOT REFUSED"))
    except GraphError:
        out.append(("self_relationship", "refused"))
    return all(v == "refused" for _, v in out) and w.g.counts()["relationships"] == 0, ", ".join(f"{n}={v}" for n, v in out)


def chk_invented_compensation(make):
    from pydantic import ValidationError

    bad = [("zero_value", dict(value=Decimal("0"))), ("negative_value", dict(value=Decimal("-5"))), ("reported_without_value", dict(value=None)),
           ("suppressed_with_an_amount", dict(value_status="suppressed")), ("currency_not_iso", dict(currency="US$")), ("percentile_without_the_percentile_measure", dict(percentile=25)),
           ("bounds_inverted", dict(lower_value=Decimal("90"), upper_value=Decimal("10"))), ("reference_year_absurd", dict(reference_year=1066))]
    out = []
    for name, kw in bad:
        try:
            _record(**kw)
            out.append((name, "NOT REFUSED"))
        except (ValidationError, ValueError):
            out.append((name, "refused"))
    return all(v == "refused" for _, v in out), ", ".join(f"{n}={v}" for n, v in out)


def chk_incorrect_currency_assumption(make):
    from src.knowledge_foundation.compensation import country_adapters as CA

    maps = dict(statistic_map={"MED": ("median", 0)}, period_map={"YR": "annual"})
    kw = dict(source_ref="s", source_edition="E", taxonomy_edition="fx", reference_year=2025, level_by_code_length={5: "detailed"}, **maps)
    wrong = CA.canada_records([{"code": "90001", "statistic": "MED", "period": "YR", "value": "50000", "currency": "USD"}], **kw)
    right = CA.canada_records([{"code": "90001", "statistic": "MED", "period": "YR", "value": "50000"}], **kw)
    sa = CA.south_america_records("CL", [{"code": "9701", "statistic": "MED", "period": "YR", "value": "5000", "concept": "wage", "population": "emp", "method": "survey"}], source_ref="s", source_edition="E",
                                  taxonomy_edition="08", reference_year=2025, statistic_map={"MED": ("median", 0)}, period_map={"YR": "annual"}, concept_map={"wage": "wage_statistic"},
                                  population_map={"emp": "employees"}, method_map={"survey": "survey"})
    ok = wrong[0] == [] and wrong[1].get("currency_mismatch") == 1 and len(right[0]) == 1 and right[0][0].currency == "CAD" and sa[0] == [] and sa[1].get("currency_missing") == 1
    return ok, f"CAD row stating USD rejected={dict(wrong[1])}; unstated CAD kept as CAD; South America row without a stated currency rejected={dict(sa[1])}"


def chk_suppressed_reconstruction(make):
    from src.knowledge_foundation.compensation.record import CompensationRecordV2

    w = _world(make)
    w.reg.register("ons_ashe", origin="authorised_manual", publisher="Synthetic official publisher", dataset_name="Synthetic ASHE-like dataset", dataset_version="E1",
                   precedence_category="national_official_occupation_statistics", validation_status="unvalidated")
    _approve(w, "ons_ashe")
    for code in ("3312", "3311"):
        w.g.add_occupation(f"synthetic uk {code}", [("uk_soc", "2020", code)])

    def rec(code, period):
        return CompensationRecordV2(taxonomy_scheme="uk_soc", taxonomy_edition="2020", native_code=code, occupation_level="detailed", country="GB", geography_level="national", currency="GBP",
                                    pay_period=period, pay_basis="gross", measure="median", value=Decimal("40000"), source_ref="ons_ashe", source_edition="E1", reference_year=2025)
    rep = w.store.import_records([rec("3312", "annual"), rec("3312", "weekly"), rec("3311", "annual")], source_ref="ons_ashe", source_edition="E1", mode="production")
    kept = {(r["native_code"], r["pay_period"]) for r in w.store.records_for([1, 2], "GB")}
    return rep.rejections == {"publisher_suppressed_measurement_must_stay_missing": 1} and kept == {("3312", "weekly"), ("3311", "annual")}, f"rejected={rep.rejections}; stored={sorted(kept)}"


def chk_revoked_mapping(make):
    w = _world(make)
    _official_source(w)
    _approve(w, "gov_src")
    parent = w.g.add_occupation("synthetic broad", [("soc", "2018", "99-0010")])["occupation_key"]
    child = w.g.add_occupation("synthetic child", [("soc", "2018", "99-0011")])["occupation_key"]
    w.al.add_alias(child, "synthetic child", language="en", language_basis="curated_manual", alias_type="recognized_title")
    w.store.import_records([_record(code="99-0010", occupation_level="broad")], source_ref="gov_src", source_edition="E1", mode="production")
    w.g.add_relationship(child, parent, relationship_type="broader", basis="source_provided", mapping_status="verified", from_taxonomy=("soc", "2018"), to_taxonomy=("soc", "2018"), source_ref="gov_src")
    before = _ask(w, "synthetic child")
    w.g.supersede_relationship(child, parent)
    after = _ask(w, "synthetic child")
    ok = bool(before.contextual_evidence) and before.value is None and not after.contextual_evidence and after.value is None and after.outcome.value == "abstain"
    return ok, f"before revocation: context offered={len(before.contextual_evidence)}, own value={before.value}; after: context={len(after.contextual_evidence)}, own value={after.value}"


def chk_provenance_on_import(make):
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved, build_citation

    w = _world(make)
    _official_source(w)
    _approve(w, "gov_src")
    w.reg.register("gov_noattr", origin="official_local", publisher=None, dataset_name=None, dataset_version="E1", precedence_category="national_official_occupation_statistics", validation_status="unvalidated")
    _approve(w, "gov_noattr")
    w.g.add_occupation("synthetic occupation", [("soc", "2018", "99-0001")])
    w.store.import_records([_record()], source_ref="gov_src", source_edition="E1", mode="production")
    rec = w.store.records_for([1], "US")[0]
    cit = build_citation(rec, w.reg)
    try:
        w.store.import_records([_record(source="gov_noattr")], source_ref="gov_noattr", source_edition="E1", mode="production")
        refused = False
    except CompensationSourceNotApproved:
        refused = True
    return bool(cit and cit["publisher"] and cit["dataset"] and cit["edition"] and cit["native_code"] and rec["publisher"] and rec["dataset_name"]) and refused, f"citation fields present={bool(cit)}; source without attribution refused at import={refused}"


def chk_secondary_never_presents_as_c1_c3(make):
    w = _world(make)
    w.reg.register("sec_src", origin="official_local", publisher="Synthetic secondary provider", dataset_name="Synthetic secondary dataset", dataset_version="E1", precedence_category="authorized_secondary",
                   validation_status="unvalidated")
    _approve(w, "sec_src")
    w.g.add_occupation("synthetic occupation", [("soc", "2018", "99-0001")])
    rep = w.store.import_records([_record(source="sec_src")], source_ref="sec_src", source_edition="E1", mode="production")
    return rep.added == 0 and rep.rejections == {"evidence_class_undeterminable": 1} and w.store.counts()["records"] == 0, f"added={rep.added}; rejected={rep.rejections}: authorised secondary evidence has no C1 to C3 class, so it is never stored as evidence"


def chk_unsupported_statistical_comparison(make):
    a, b = _record(), _record(measure="mean")
    c, d = _record(pay_period="hourly", value=Decimal("29")), _record(currency="EUR")
    e = _record(population_scope="full_time_employees")
    keys = {a.comparability_key(), b.comparability_key(), c.comparability_key(), d.comparability_key(), e.comparability_key()}
    unknown = _record(measure="unknown").comparability_key()[6] is None and _record(pay_basis="unknown").comparability_key()[5] is None
    return len(keys) == 5 and unknown, f"{len(keys)} of 5 differing measurements have distinct comparability keys; unknown measure or basis is comparable with nothing={unknown}"


GOVERNANCE: list[tuple[str, list[str], Callable]] = [
    ("g-lifecycle-ladder", ["lifecycle:source_identified", "lifecycle:licence_pending", "lifecycle:ingestion_approved", "lifecycle:runtime_approved", "lifecycle:revoked", "compensation:unapproved_source"], chk_lifecycle_ladder),
    ("g-unqualified-never-operational", ["lifecycle:engineering_checked", "lifecycle:human_qualified", "compensation:unqualified_source", "compensation:expired_or_revoked_evidence", "negative:unqualified_evidence_operational",
                                         "negative:revoked_evidence_reuse"], chk_unqualified_never_operational),
    ("g-unapproved-promotion-and-licensing-bypass", ["negative:unapproved_source_promotion", "negative:licensing_bypass"], chk_unapproved_promotion_and_licensing_bypass),
    ("g-false-reviewer-approval", ["negative:false_reviewer_approval"], chk_false_reviewer_approval),
    ("g-fabricated-mapping", ["negative:fabricated_mapping"], chk_fabricated_mapping),
    ("g-invented-compensation", ["negative:invented_compensation"], chk_invented_compensation),
    ("g-incorrect-currency-assumption", ["negative:incorrect_currency_assumption", "compensation:no_unauthorised_currency_conversion"], chk_incorrect_currency_assumption),
    ("g-suppressed-reconstruction", ["negative:suppressed_reconstruction", "compensation:suppressed_measurements"], chk_suppressed_reconstruction),
    ("g-revoked-mapping", ["occupation:revoked_mapping", "negative:silent_broader_substitution", "compensation:no_silent_broader_substitution"], chk_revoked_mapping),
    ("g-provenance-on-import", ["occupation:missing_provenance", "negative:incomplete_provenance", "compensation:incomplete_provenance"], chk_provenance_on_import),
    ("g-secondary-never-presents-as-c1-c3", ["fallback:secondary_is_not_c1_c3", "fallback:c4_abstains"], chk_secondary_never_presents_as_c1_c3),
    ("g-unsupported-statistical-comparison", ["negative:unsupported_statistical_comparison", "compensation:unsupported_comparison_rejected"], chk_unsupported_statistical_comparison),
]


def run_governance() -> list[dict[str, Any]]:
    out = []
    for cid, tags, fn in GOVERNANCE:
        t0 = time.perf_counter()
        try:
            with _temp_world() as make:
                ok, detail = fn(make)
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failing check, reported with its type only
            ok, detail = False, f"check raised {type(exc).__name__}"
        out.append({"id": cid, "ok": bool(ok), "detail": detail, "tags": tags, "seconds": round(time.perf_counter() - t0, 3)})
    return out


# ----------------------------------------------------------------------------------------------------------------------------------- matrix and aggregation
def coverage_matrix(corpus: dict[str, Any], corpus_results: dict[str, Any], governance: list[dict[str, Any]]) -> dict[str, Any]:
    exercised: dict[str, int] = Counter()
    passing: dict[str, int] = Counter()
    for r in corpus_results["cases"]:
        for t in r["tags"]:
            exercised[t] += 1
            passing[t] += int(r["ok"])
    for g in governance:
        for t in g["tags"]:
            exercised[t] += 1
            passing[t] += int(g["ok"])
    # corpus tags also stand for the negative-regression names where the corpus case is the negative test
    alias = {"negative:cross_country_substitution": "compensation:no_cross_country_substitution", "negative:wrong_taxonomy_edition": "occupation:wrong_taxonomy_edition",
             "negative:silent_broader_substitution": "compensation:no_silent_broader_substitution", "negative:incomplete_provenance": "source:incomplete_provenance",
             "compensation:unapproved_source": "source:unapproved_never_operational", "compensation:unqualified_source": "source:unqualified_never_operational",
             "compensation:incomplete_provenance": "source:incomplete_provenance", "occupation:missing_provenance": "source:incomplete_provenance",
             "compensation:no_hidden_period_conversion": "compensation:weekly_vs_annual"}
    for k, v in alias.items():
        if exercised[k] == 0 and exercised[v] > 0:
            exercised[k], passing[k] = exercised[v], passing[v]
    required = {t for tags in REQUIRED_TAGS.values() for t in tags}
    missing = sorted(t for t in required if exercised[t] == 0)
    failing = sorted(t for t in required if exercised[t] and passing[t] < exercised[t])
    jur = {}
    for key in JURISDICTIONS:
        row = {s: next((r["ok"] for r in corpus_results["cases"] if r["id"] == f"{key.lower()}-{s}"), None) for s in PER_JURISDICTION_CASES}
        jur[key] = row
    return {"required_tags": len(required), "exercised": sum(1 for t in required if exercised[t]), "missing_tags": missing, "failing_tags": failing,
            "by_group": {grp: {"required": len(tags), "exercised": sum(1 for t in tags if exercised[t])} for grp, tags in REQUIRED_TAGS.items()}, "jurisdictions": jur,
            "tag_counts": {t: exercised[t] for t in sorted(exercised)}}


def run_all(corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    corpus = corpus or load_corpus()
    integrity = validate_corpus(corpus)
    t1 = time.perf_counter()
    cres = run_corpus(corpus)
    t2 = time.perf_counter()
    gov = run_governance()
    t3 = time.perf_counter()
    matrix = coverage_matrix(corpus, cres, gov)
    det = hashlib.sha256(json.dumps({"cases": [(r["id"], r["ok"], r["outcome"]) for r in cres["cases"]], "governance": [(g["id"], g["ok"]) for g in gov]}, sort_keys=True).encode()).hexdigest()
    ok = (not integrity and cres["passed"] == cres["total"] and not cres["import_rejections"] and cres["fixture_sources_only"] and cres["no_source_can_serve_as_evidence"] and cres["invented_values"] == 0
          and cres["presentable_or_operational"] == 0 and cres["meta_check_rejects_a_wrong_expectation"] and all(g["ok"] for g in gov) and not matrix["missing_tags"] and not matrix["failing_tags"])
    return {"schema": RESULT_SCHEMA, "corpus_version": corpus["corpus_version"], "ok": ok, "fixture_integrity_errors": integrity,
            "corpus": {k: v for k, v in cres.items() if k != "cases"} | {"cases": [{k: r[k] for k in ("id", "category", "ok", "outcome", "problems")} for r in cres["cases"]]},
            "governance": gov, "matrix": matrix, "determinism_hash": det,
            "timing_seconds": {"fixture_integrity": round(t1 - t0, 3), "corpus_rebuild_and_evaluation": round(t2 - t1, 3), "governance_and_negative_regression": round(t3 - t2, 3), "total": round(t3 - t0, 3)}}
