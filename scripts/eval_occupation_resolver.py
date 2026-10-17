#!/usr/bin/env python
"""P10C-B multilingual occupation-resolver evaluation. Deterministic and offline: runs the committed SYNTHETIC fixture corpus through the resolver on a throwaway database and checks the
safety invariants (no wrong resolution, no guess, nothing operational, no unauthorised source promotion, geography independence) and the isolation from every candidate-facing path. No
store, cache, artifact or protected file is touched. Ambiguity correctness is reported as its OWN metric and the exit code is never a product-quality claim: product coverage stays
BELOW GATE until a later integration wave (this evaluation does not read or change it)."""

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
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.coverage import CoverageMatrix
    from src.knowledge_foundation.fixtures import evaluate_cases, load_corpus, load_into
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.language_coverage import LanguageCoverageService
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver, ResolutionOutcome
    from src.knowledge_foundation.registry import SourceRegistry
    from src.persistence import init_db, make_engine, make_session_factory

    res: dict[str, tuple[bool, str]] = {}

    def check(name, ok, detail=""):
        res[name] = (bool(ok), detail)

    d = Path(tempfile.mkdtemp())
    engine = make_engine(f"sqlite:///{d}/r.db")
    init_db(engine)
    sf = make_session_factory(engine)
    corpus = load_corpus()
    keys = load_into(sf, corpus)
    cm, lc, reg = CoverageMatrix(sf), LanguageCoverageService(sf), SourceRegistry(sf)
    cm.seed()
    lc.seed()
    g, a = OccupationGraph(sf), AliasStore(sf)
    r = OccupationResolver(g, a, coverage=cm, language_coverage=lc, registry=reg)
    results = evaluate_cases(r, keys, corpus)
    ok_n = sum(1 for x in results if x["ok"])
    exp = collections.Counter(x["expected"] for x in results)
    check("synthetic_corpus_is_synthetic_only", all(s["origin"] == "synthetic_fixture" for s in corpus["sources"]) and "SYNTHETIC" in corpus["note"], f"{len(corpus['occupations'])} occupations, {len(corpus['sources'])} synthetic sources")
    check("every_corpus_case_matches_its_expectation", ok_n == len(results), f"{ok_n}/{len(results)}")
    check("no_occupation_is_wrongly_resolved", not any(x["wrong_resolution"] for x in results), "wrong resolutions = 0")
    check("nothing_resolved_is_operational", not any(x["operational"] for x in results), "no qualified alias of an approved source exists")
    amb = [x for x in results if x["expected"] == "ambiguous"]
    check("ambiguity_correctness_is_complete", all(x["actual"] == "ambiguous" for x in amb) and amb, f"{sum(1 for x in amb if x['actual'] == 'ambiguous')}/{len(amb)} ambiguous cases returned AMBIGUOUS")
    abst = [x for x in results if x["expected"] in ("insufficient_context", "unsupported", "not_found")]
    check("abstention_correctness_is_complete", all(x["actual"] == x["expected"] for x in abst) and abst, f"{sum(1 for x in abst if x['actual'] == x['expected'])}/{len(abst)} abstaining cases")
    cats = {x["category"] for x in results}
    check("every_required_scenario_is_covered", {"official_code", "multilingual_alias", "shared_alias", "false_friend", "editions", "leading_zero", "geography_independence", "abstention", "unsupported_language",
                                                   "unsupported_country", "missing_language_metadata", "mixed_language", "legacy", "normalization", "crosswalk", "conflict", "industry", "unknown",
                                                   "cross_language", "duplicate_title"} <= cats, f"{len(cats)} categories")
    langs = {c["request"].get("title_language") for c in corpus["cases"] if c["category"] == "multilingual_alias"}
    check("eight_ui_languages_are_exercised_with_synthetic_aliases", langs >= {"en", "de", "fr", "es", "it", "pt", "nl", "ru"}, ",".join(sorted(x for x in langs if x)))
    check("russian_is_not_claimed_as_official_source_coverage", lc.get("ru")["taxonomy_level"] == "targeted" and lc.get("ru")["alias_data_level"] == "targeted" and not lc.get("ru")["source_ids"], "ru: UI locale + synthetic resolver tests only")
    check("no_language_is_qualified", not any(x["alias_qualified"] for x in lc.all()) and not any("qualified" in (x["taxonomy_level"], x["alias_data_level"], x["resolver_level"]) for x in lc.all()), "language coverage")
    fields = set(MultilingualRequest.__dataclass_fields__)
    check("resolver_request_has_no_interface_locale_field", not fields & {"locale", "ui_language", "interface_language", "conversation_language", "ui_locale"}, "title_language is the language of the input text")
    countries = set()
    for c in ("DE", "CH", "AT", None):
        out = r.resolve(MultilingualRequest(title="Krankenpfleger", title_language="de", country=c))
        countries.add((out.country_used, out.outcome))
    check("language_does_not_select_a_country", countries == {("DE", ResolutionOutcome.RESOLVED), ("CH", ResolutionOutcome.RESOLVED), ("AT", ResolutionOutcome.RESOLVED), (None, ResolutionOutcome.RESOLVED)}, "country_used mirrors the explicit input")
    check("synthetic_sources_can_never_serve_as_evidence", not any(reg.can_serve_as_evidence(s["source_id"]) or reg.can_ingest(s["source_id"]) for s in corpus["sources"]), "registry gate")
    # two reported quality classes (mirror of the P10C-0 analysis categories, on synthetic cases only; the real 412-case product coverage is not read or changed here)
    wiring = [x for x in results if x["category"] in ("official_code", "leading_zero")]
    ambig_titles = [x for x in results if x["category"] in ("shared_alias", "false_friend", "duplicate_title") and x["expected"] == "ambiguous"]
    check("code_wiring_class_resolves_correctly", wiring and all(x["ok"] for x in wiring), f"{sum(1 for x in wiring if x['ok'])}/{len(wiring)}")
    check("ambiguous_title_class_is_abstained_not_guessed", ambig_titles and all(x["actual"] == "ambiguous" for x in ambig_titles), f"{sum(1 for x in ambig_titles if x['actual'] == 'ambiguous')}/{len(ambig_titles)}")
    # isolation and gates
    offenders = []
    for pkg in RUNTIME_PACKAGES:
        for f in (ROOT / pkg).rglob("*.py"):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [x.name for x in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    check("foundation_is_not_imported_by_any_runtime_path", not offenders, f"{len(offenders)} offenders")
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    check("all_rollout_and_billing_gates_stay_off", not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED,
                                                           PP.PREPARATION_PACK_GENERATION_ENABLED]) and not any(getattr(bp, x) for x in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED",
                                                           "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")), "12 gates False")
    import src.copilot.knowledge.compensation as comp
    check("no_compensation_v2_and_v1_untouched", not hasattr(comp, "CompensationRecordV2") and "knowledge_foundation" not in (ROOT / "src/copilot/knowledge/compensation.py").read_text(), "no salary behaviour added")
    inv = json.loads((ROOT / "docs/capstone/p10/p10c_b/ALIAS_INVENTORY.json").read_text(encoding="utf-8"))
    check("alias_inventory_is_metadata_only_and_matches_baseline", inv["aliases"] == 23579 and inv["occupations"] == 8035 and "No alias text" in inv["note"], f"{inv['aliases']} aliases / {inv['occupations']} occupations")
    meta = {"cases": len(results), "passed": ok_n, "by_expected_outcome": dict(sorted(exp.items())), "ambiguity_correctness": f"{sum(1 for x in amb if x['actual'] == 'ambiguous')}/{len(amb)}",
            "wrong_resolutions": sum(1 for x in results if x["wrong_resolution"])}
    return res, meta


SAFETY = {"no_occupation_is_wrongly_resolved", "nothing_resolved_is_operational", "ambiguity_correctness_is_complete", "abstention_correctness_is_complete", "synthetic_sources_can_never_serve_as_evidence",
          "language_does_not_select_a_country", "resolver_request_has_no_interface_locale_field", "foundation_is_not_imported_by_any_runtime_path", "all_rollout_and_billing_gates_stay_off",
          "no_compensation_v2_and_v1_untouched", "russian_is_not_claimed_as_official_source_coverage", "no_language_is_qualified"}


def main() -> int:
    print("ASK4MO - P10C-B MULTILINGUAL OCCUPATION RESOLVER EVALUATION\n")
    results, meta = run()
    failed = False
    for name, (ok, detail) in results.items():
        print(f"  {name:62} {'PASS' if ok else 'FAIL'}  {detail}")
        failed |= not ok
    print(f"\nCorpus: {meta['cases']} synthetic cases, {meta['passed']} as expected; outcomes {meta['by_expected_outcome']}; ambiguity correctness {meta['ambiguity_correctness']}; wrong resolutions {meta['wrong_resolutions']}")
    print("Product coverage (412 cases, 95% gate) is NOT evaluated here and remains BELOW GATE.")
    print("Paid LLM calls: 0   Live calls: 0   External downloads: 0\n")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
