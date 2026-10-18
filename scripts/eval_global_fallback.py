#!/usr/bin/env python
"""P10C-E wider South America, international fallback and comparison evaluation. Deterministic and offline: runs the committed SYNTHETIC corpus through the registry-gated importers, the
internal resolver, the evidence-state framework and the comparison contract on a throwaway database, and checks the safety invariants (no invented value, no unapproved ingestion, no
cross-country substitution, nothing operational while the international precedence decision is pending, no conversion, nothing qualified). No store, cache, artifact or protected file is
touched. The exit code is NOT a coverage or product-quality claim: no market is qualified and the 412-case product coverage (95% gate) is neither read nor changed here and remains BELOW GATE."""

from __future__ import annotations

import ast
import collections
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RUNTIME_PACKAGES = ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents", "src/billing")


def run() -> tuple[dict[str, tuple[bool, str]], dict]:
    import tests.conftest  # noqa: F401  (test isolation: temp database only)
    from src.knowledge_foundation import global_reports
    from src.knowledge_foundation.compensation.country_fixtures import evaluate_blocks, evaluate_cases, evaluate_comparisons, load_corpus, load_world
    from src.knowledge_foundation.compensation.countries import WIDER_SA_PROFILES
    from src.knowledge_foundation.compensation.policy import PrecedencePolicy
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved
    from src.persistence import init_db, make_engine, make_session_factory

    res: dict[str, tuple[bool, str]] = {}

    def check(name, ok, detail=""):
        res[name] = (bool(ok), detail)

    path = ROOT / "src/knowledge_foundation/data/fallback_fixture_corpus.json"
    d = Path(tempfile.mkdtemp())
    engine = make_engine(f"sqlite:///{d}/c.db")
    init_db(engine)
    sf = make_session_factory(engine)
    corpus = load_corpus(path)
    world = load_world(sf, corpus)
    blocks, results, comps = evaluate_blocks(world, corpus), evaluate_cases(world, corpus), evaluate_comparisons(world, corpus)
    ok_n = sum(1 for x in results if x["ok"])
    outcomes = collections.Counter(x["outcome"] for x in results)
    check("corpus_is_synthetic_only", "SYNTHETIC" in corpus["note"] and all(world.reg.get(s["source_id"])["origin"] == "synthetic_fixture" for s in corpus["sources"]), f"{len(corpus['sources'])} synthetic sources")
    check("every_import_block_matches_its_expectation", all(b["ok"] for b in blocks), f"{sum(1 for b in blocks if b['ok'])}/{len(blocks)} blocks")
    check("every_corpus_case_matches_its_expectation", ok_n == len(results), f"{ok_n}/{len(results)}")
    check("every_comparison_matches_its_expectation", all(c["ok"] for c in comps), f"{sum(1 for c in comps if c['ok'])}/{len(comps)}")
    check("no_value_is_invented", not any(x["invented_value"] for x in results), "no value outside an EVIDENCE outcome")
    check("nothing_is_operational_or_presentable", not any(x["operational"] or x["presentable"] for x in results), "no runtime-approved qualified source exists")
    check("synthetic_sources_can_never_serve_as_evidence", not any(world.reg.can_serve_as_evidence(s["source_id"]) or world.reg.can_ingest(s["source_id"]) for s in corpus["sources"]), "registry gate")
    cats = {x["category"] for x in results}
    check("every_required_scenario_is_covered", {"south_america_national", "regional", "granularity", "concepts", "populations", "international", "conflict", "freshness", "taxonomy", "missing_mapping", "unsupported", "ambiguity",
                                                   "precedence", "c4", "comparison", "geography_independence", "approval", "currency"} <= cats, f"{len(cats)} categories")
    check("all_eleven_wider_markets_have_a_national_synthetic_case", all(x["ok"] and x["outcome"] == "evidence" for x in results if x["id"] in {f"sa-{c.lower()}-national" for c in WIDER_SA_PROFILES}), "AR BO CL CO EC GY PY PE SR UY VE")
    pol = PrecedencePolicy.load()
    check("international_precedence_is_a_pending_boundary", pol.version == "p10c-e/1" and not pol.family_enabled("ilostat") and "D-16" in pol.raw["international_families"]["ilostat"]["status"], pol.version)
    pending = [x for x in results if x["id"] in ("intl-c3-internal", "intl-c3-argentina")]
    check("pending_international_evidence_is_flagged_and_withheld_operationally", all(x["ok"] for x in pending) and next(x for x in results if x["id"] == "intl-operational-mode-withheld")["ok"], "flagged internally; never operational")
    try:
        world.store.import_records([], source_ref="fx_ilo", source_edition="E", mode="production")
        blocked = False
    except CompensationSourceNotApproved:
        blocked = True
    check("production_import_of_the_pending_family_is_refused", blocked, "owner decision D-16")
    check("incompatible_and_unrelated_statistics_never_become_salary", all(x["ok"] for x in results if x["id"] in ("sa-incompatible-statistics-conflict", "sa-indicators-not-salary", "sa-household-income-never-evidence")), "conflict preserved; indicators rejected")
    check("no_cross_country_substitution", all(x["ok"] for x in results if x["id"] in ("sa-english-text-peru-no-borrowing", "sa-no-data-country-abstains", "intl-no-substitution-for-other-country")), "explicit country only")
    check("fx_and_ppp_are_not_configured", all(x["outcome"] == "not_configured" for x in results if x["id"] in ("sa-fx-not-configured", "sa-ppp-not-configured")) and all(c["status"] == "not_configured" for c in comps if c["id"].endswith("never-configured")), "no rate, no factor")
    cov = global_reports.coverage_report(ROOT)
    check("no_market_is_operational_or_qualified", not cov["operational_markets"] and not cov["qualified_markets"] and len(cov["markets"]) == 17, f"{len(cov['markets'])} markets")
    reg = global_reports.approval_register(ROOT)
    check("approval_register_proposes_and_never_approves", not reg["approved_entries"] and all(e["status"] == "PROPOSED" and e["decisions_required"] for e in reg["entries"]), f"{len(reg['entries'])} proposed entries")
    offenders = []
    for pkg in RUNTIME_PACKAGES:
        for f in (ROOT / pkg).rglob("*.py"):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [x.name for x in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    check("nothing_is_imported_by_any_runtime_path", not offenders, f"{len(offenders)} offenders")
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    check("all_rollout_and_billing_gates_stay_off", not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED,
                                                           PP.PREPARATION_PACK_GENERATION_ENABLED]) and not any(getattr(bp, x) for x in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED",
                                                           "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")), "12 gates False")
    v1 = (ROOT / "src/copilot/knowledge/compensation.py").read_text(encoding="utf-8")
    check("compensation_v1_untouched", "knowledge_foundation" not in v1 and "class CompensationRepository" in v1, "V1 module unchanged and not coupled to V2")
    versions = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("no_schema_change", versions[-1].startswith("0038_") and len(versions) == 38, versions[-1])
    meta = {"cases": len(results), "passed": ok_n, "outcomes": dict(sorted(outcomes.items())), "invented_values": sum(1 for x in results if x["invented_value"]), "blocks": len(blocks), "comparisons": len(comps)}
    return res, meta


def main() -> int:
    print("ASK4MO - P10C-E WIDER SOUTH AMERICA, INTERNATIONAL FALLBACK AND COMPARISON EVALUATION\n")
    results, meta = run()
    failed = False
    for name, (ok, detail) in results.items():
        print(f"  {name:62} {'PASS' if ok else 'FAIL'}  {detail}")
        failed |= not ok
    print(f"\nCorpus: {meta['cases']} synthetic cases, {meta['passed']} as expected; outcomes {meta['outcomes']}; invented values {meta['invented_values']}; {meta['blocks']} import blocks; {meta['comparisons']} comparisons")
    print("No market is qualified. Product coverage (412 cases, 95% gate) is NOT evaluated here and remains BELOW GATE; no real source data was ingested.")
    print("Paid LLM calls: 0   Live calls: 0   External downloads: 0\n")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
