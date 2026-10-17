#!/usr/bin/env python
"""P10C-C Compensation V2 evaluation. Deterministic and offline: runs the committed SYNTHETIC fixture corpus through the importer and the internal resolver on a throwaway database and
checks the safety invariants (no invented value, no unapproved ingestion, no cross-country fallback, no combination of incompatible measurements, C4 abstention, traceable citations,
nothing operational) and the isolation from every candidate-facing path. No store, cache, artifact or protected file is touched. The exit code is NOT a product-quality claim: the 412-case
product coverage (95% gate) is neither read nor changed here and remains BELOW GATE; no real source data has been ingested."""

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
    from src.knowledge_foundation.compensation.fixtures import evaluate_cases, load_corpus, load_world
    from src.knowledge_foundation.compensation.policy import PrecedencePolicy
    from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest
    from src.persistence import init_db, make_engine, make_session_factory

    res: dict[str, tuple[bool, str]] = {}

    def check(name, ok, detail=""):
        res[name] = (bool(ok), detail)

    d = Path(tempfile.mkdtemp())
    engine = make_engine(f"sqlite:///{d}/c.db")
    init_db(engine)
    sf = make_session_factory(engine)
    corpus = load_corpus()
    world = load_world(sf, corpus)
    results = evaluate_cases(world, corpus)
    ok_n = sum(1 for x in results if x["ok"])
    outcomes = collections.Counter(x["outcome"] for x in results)
    check("corpus_is_synthetic_only", "SYNTHETIC" in corpus["note"] and all(s["source_id"].startswith("fx_") for s in corpus["sources"]) and all(world.reg.get(s["source_id"])["origin"] == "synthetic_fixture" for s in corpus["sources"]),
          f"{len(corpus['scenarios'])} scenarios, {len(corpus['sources'])} synthetic sources")
    check("every_corpus_case_matches_its_expectation", ok_n == len(results), f"{ok_n}/{len(results)}")
    check("no_value_is_invented", not any(x["invented_value"] for x in results), "no value outside an EVIDENCE outcome")
    check("nothing_is_operational_or_presentable", not any(x["operational"] or x["presentable"] for x in results), "no runtime-approved qualified source exists")
    check("synthetic_sources_can_never_serve_as_evidence", not any(world.reg.can_serve_as_evidence(s["source_id"]) or world.reg.can_ingest(s["source_id"]) for s in corpus["sources"]), "registry gate")
    cats = {x["category"] for x in results}
    check("every_required_scenario_is_covered", {"us_code", "uk_code", "eu_isco", "conflict", "ambiguity", "missing_market", "unsupported", "c4", "stale", "measurement", "specificity", "crosswalk", "comparison",
                                                   "geography_independence", "citation", "approval", "precedence", "context"} <= cats, f"{len(cats)} categories")
    check("c4_abstains_for_missing_evidence", outcomes["abstain"] >= 8 and all(x["outcome"] != "evidence" for x in results if x["category"] in ("c4", "missing_market")), f"{outcomes['abstain']} abstentions")
    check("incompatible_measurements_are_preserved_not_combined", outcomes["conflict"] >= 5, f"{outcomes['conflict']} conflicts")
    check("ambiguity_never_yields_a_salary", all(x["outcome"] == "ambiguous" for x in results if x["category"] == "ambiguity" and x["id"].startswith("ambiguous")), "AMBIGUOUS carries no value")
    check("fx_and_ppp_are_not_configured", all(x["outcome"] in ("not_configured", "insufficient_context") for x in results if x["category"] == "comparison"), "no rate, no conversion")
    pol = PrecedencePolicy.load()
    check("policy_is_versioned_and_has_no_country_overrides", pol.version == "p10c-d/1" and pol.raw["country_overrides"].startswith("none") and [t["rank"] for t in pol.tiers] == [1, 2, 3, 4, 5, 6], pol.version)
    # unapproved ingestion is blocked
    blocked = 0
    for sid, mode in (("fx_us_stat", "production"), ("nope", "fixture")):
        try:
            world.store.import_records([], source_ref=sid, source_edition="x", mode=mode)
        except CompensationSourceNotApproved:
            blocked += 1
    check("unapproved_or_synthetic_ingestion_is_blocked", blocked == 2, "production import of a synthetic or unregistered source refused")
    default = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job us_c1", title_language="en"), country="US"))
    check("default_withholds_non_operational_evidence", default.outcome is CompensationOutcome.ABSTAIN and default.value is None and default.abstention_reason == "evidence_exists_but_is_not_operational", default.abstention_reason or "")
    offenders = []
    for pkg in RUNTIME_PACKAGES:
        for f in (ROOT / pkg).rglob("*.py"):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [x.name for x in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    check("compensation_v2_is_not_imported_by_any_runtime_path", not offenders, f"{len(offenders)} offenders")
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    check("all_rollout_and_billing_gates_stay_off", not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED,
                                                           PP.PREPARATION_PACK_GENERATION_ENABLED]) and not any(getattr(bp, x) for x in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED",
                                                           "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")), "12 gates False")
    v1 = (ROOT / "src/copilot/knowledge/compensation.py").read_text(encoding="utf-8")
    check("compensation_v1_untouched", "knowledge_foundation" not in v1 and "class CompensationRepository" in v1, "V1 module unchanged and not coupled to V2")
    inv = json.loads((ROOT / "docs/capstone/p10/p10c_c/COMPENSATION_INVENTORY.json").read_text(encoding="utf-8"))
    check("inventory_is_metadata_only_and_matches_baseline", inv["records"] == 1913 and inv["per_source"]["bls_oews"]["records"] == 1386 and inv["per_source"]["ons_ashe"]["records"] == 527 and "No titles" in inv["note"],
          f"{inv['records']} V1 records")
    meta = {"cases": len(results), "passed": ok_n, "outcomes": dict(sorted(outcomes.items())), "invented_values": sum(1 for x in results if x["invented_value"])}
    return res, meta


def main() -> int:
    print("ASK4MO - P10C-C COMPENSATION V2 FOUNDATION EVALUATION\n")
    results, meta = run()
    failed = False
    for name, (ok, detail) in results.items():
        print(f"  {name:62} {'PASS' if ok else 'FAIL'}  {detail}")
        failed |= not ok
    print(f"\nCorpus: {meta['cases']} synthetic cases, {meta['passed']} as expected; outcomes {meta['outcomes']}; invented values {meta['invented_values']}")
    print("Product coverage (412 cases, 95% gate) is NOT evaluated here and remains BELOW GATE; no real source data was ingested.")
    print("Paid LLM calls: 0   Live calls: 0   External downloads: 0\n")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
