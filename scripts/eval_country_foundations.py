#!/usr/bin/env python
"""P10C-D Canada, Mexico and Brazil foundations evaluation. Deterministic and offline: runs the committed SYNTHETIC corpus through the registry-gated importers and the internal resolver on a
throwaway database and checks the safety invariants (no invented value, no unapproved ingestion, no cross-country or cross-edition matching, definitions never combined, household income never
evidence, regional never national, nothing operational) and the isolation from every candidate-facing path. No store, cache, artifact or protected file is touched. The exit code is NOT a
country-coverage or product-quality claim: no country is qualified and the 412-case product coverage (95% gate) is neither read nor changed here and remains BELOW GATE."""

from __future__ import annotations

import ast
import collections
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RUNTIME_PACKAGES = ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents", "src/billing")


def run() -> tuple[dict[str, tuple[bool, str]], dict]:
    import tests.conftest  # noqa: F401  (test isolation: temp database only)
    from sqlalchemy import select
    from src.knowledge_foundation import readiness
    from src.knowledge_foundation.compensation.country_fixtures import evaluate_blocks, evaluate_cases, load_corpus, load_world
    from src.knowledge_foundation.compensation.country_import import CountryImportNotApproved, import_crosswalk, import_taxonomy_nodes
    from src.knowledge_foundation.compensation.countries import PROFILES
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved
    from src.persistence import CompensationRecordV2Row, init_db, make_engine, make_session_factory

    res: dict[str, tuple[bool, str]] = {}

    def check(name, ok, detail=""):
        res[name] = (bool(ok), detail)

    d = Path(tempfile.mkdtemp())
    engine = make_engine(f"sqlite:///{d}/c.db")
    init_db(engine)
    sf = make_session_factory(engine)
    corpus = load_corpus()
    world = load_world(sf, corpus)
    blocks = evaluate_blocks(world, corpus)
    results = evaluate_cases(world, corpus)
    ok_n = sum(1 for x in results if x["ok"])
    outcomes = collections.Counter(x["outcome"] for x in results)
    check("corpus_is_synthetic_only", "SYNTHETIC" in corpus["note"] and all(world.reg.get(s["source_id"])["origin"] == "synthetic_fixture" for s in corpus["sources"]) and {t["edition"] for t in corpus["taxonomies"]} == {"fx-ed1", "fx-ed2"},
          f"{len(corpus['sources'])} synthetic sources, editions fx-ed1 and fx-ed2")
    check("every_import_block_matches_its_expectation", all(b["ok"] for b in blocks), f"{sum(1 for b in blocks if b['ok'])}/{len(blocks)} node, crosswalk and compensation blocks")
    check("every_corpus_case_matches_its_expectation", ok_n == len(results), f"{ok_n}/{len(results)}")
    check("no_value_is_invented", not any(x["invented_value"] for x in results), "no value outside an EVIDENCE outcome")
    check("nothing_is_operational_or_presentable", not any(x["operational"] or x["presentable"] for x in results), "no runtime-approved qualified source exists")
    check("synthetic_sources_can_never_serve_as_evidence", not any(world.reg.can_serve_as_evidence(s["source_id"]) or world.reg.can_ingest(s["source_id"]) for s in corpus["sources"]), "registry gate")
    cats = {x["category"] for x in results}
    check("every_required_scenario_is_covered", {"canada_national", "canada_provincial", "canada_language", "noc_editions", "mexico", "mexico_regional", "mexico_concepts", "brazil", "brazil_regional", "crosswalk",
                                                   "conflict", "c4", "citation", "approval", "stale", "statistical", "geography_independence", "comparison", "unsupported", "unsupported_occupation", "precedence"} <= cats,
          f"{len(cats)} categories")
    blocked = 0
    for call in (lambda: import_taxonomy_nodes(world.g, world.a, world.reg, [], scheme="noc", edition="fx-ed1", source_ref="fx_ca_tax", mode="production"),
                 lambda: import_crosswalk(world.g, world.reg, [], source_ref="fx_xwalk", from_taxonomy=("noc", "fx-ed1"), to_taxonomy=("isco", "08"), mode="production"),
                 lambda: world.store.import_records([], source_ref="fx_ca_pes", source_edition="E", mode="production"),
                 lambda: import_taxonomy_nodes(world.g, world.a, world.reg, [], scheme="noc", edition="fx-ed1", source_ref="nope", mode="fixture")):
        try:
            call()
        except (CountryImportNotApproved, CompensationSourceNotApproved):
            blocked += 1
    check("unapproved_or_synthetic_ingestion_is_blocked", blocked == 4, "taxonomy, crosswalk and compensation production imports of a synthetic or unregistered source refused")
    with sf() as s:
        household = s.scalar(select(CompensationRecordV2Row.id).where(CompensationRecordV2Row.earnings_concept == "household_income"))
    check("household_income_is_never_stored", household is None and any(r.rejections.get("earnings_concept_not_occupation_compensation") for r in world.comp_reports), "rejected at import and by CHECK")
    check("regional_figures_never_become_national", all(x["ok"] for x in results if x["id"] in ("ca-province-only-no-national", "ca-provincial-requested", "mx-national-default", "br-regional-national-both")), "regional only on request")
    check("definitions_populations_and_methods_are_not_combined", all(x["ok"] and x["outcome"] == "conflict" for x in results if x["id"] in ("mx-concepts-conflict", "mx-populations-conflict", "br-admin-vs-survey-conflict")), "conflicts preserved")
    check("noc_editions_never_collide_or_match_unknown", all(x["ok"] for x in results if x["category"] == "noc_editions"), "fx-ed1, fx-ed2, unspecified, unknown")
    check("interface_language_never_selects_a_country", all(x["ok"] for x in results if x["category"] == "geography_independence"), "fr/de/pt/es/en text with explicit countries")
    check("fx_and_ppp_are_not_configured", all(x["outcome"] == "not_configured" for x in results if x["category"] == "comparison"), "no rate, no conversion")
    rd = readiness.assess(ROOT)
    check("readiness_reports_no_operational_country", all(not c["operational_today"] and c["compensation_v2_records_linkable_today"] == 0 for c in rd["countries"].values()), f"{len(rd['countries'])} countries")
    cov = {g["code"]: g for g in json.loads((ROOT / "src/knowledge_foundation/data/coverage_matrix.json").read_text())["geographies"]}
    check("no_country_is_qualified", all("qualified" not in (cov[c]["taxonomy_level"], cov[c]["crosswalk_level"], cov[c]["compensation_level"], cov[c]["outlook_level"]) for c in PROFILES), "CA, MX, BR coverage levels unchanged")
    offenders = []
    for pkg in RUNTIME_PACKAGES:
        for f in (ROOT / pkg).rglob("*.py"):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [x.name for x in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    check("country_foundations_are_not_imported_by_any_runtime_path", not offenders, f"{len(offenders)} offenders")
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    check("all_rollout_and_billing_gates_stay_off", not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED,
                                                           PP.PREPARATION_PACK_GENERATION_ENABLED]) and not any(getattr(bp, x) for x in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED",
                                                           "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")), "12 gates False")
    v1 = (ROOT / "src/copilot/knowledge/compensation.py").read_text(encoding="utf-8")
    check("compensation_v1_untouched", "knowledge_foundation" not in v1 and "class CompensationRepository" in v1, "V1 module unchanged and not coupled to V2")
    meta = {"cases": len(results), "passed": ok_n, "outcomes": dict(sorted(outcomes.items())), "invented_values": sum(1 for x in results if x["invented_value"]), "blocks": len(blocks)}
    return res, meta


def main() -> int:
    print("ASK4MO - P10C-D CANADA, MEXICO AND BRAZIL FOUNDATIONS EVALUATION\n")
    results, meta = run()
    failed = False
    for name, (ok, detail) in results.items():
        print(f"  {name:62} {'PASS' if ok else 'FAIL'}  {detail}")
        failed |= not ok
    print(f"\nCorpus: {meta['cases']} synthetic cases, {meta['passed']} as expected; outcomes {meta['outcomes']}; invented values {meta['invented_values']}; {meta['blocks']} import blocks")
    print("No country is qualified. Product coverage (412 cases, 95% gate) is NOT evaluated here and remains BELOW GATE; no real source data was ingested.")
    print("Paid LLM calls: 0   Live calls: 0   External downloads: 0\n")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
