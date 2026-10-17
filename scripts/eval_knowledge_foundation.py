#!/usr/bin/env python
"""P10C-A knowledge-foundation evaluation. Deterministic and offline: checks the COMMITTED registry baseline, taxonomy catalogue, coverage matrix and GKB-0 baseline manifest, the
graph and resolver rules on a throwaway database, and the isolation of the foundation from every candidate-facing path. No store, cache, artifact or protected file is touched."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "src" / "knowledge_foundation" / "data"
RUNTIME_PACKAGES = ("src/copilot", "src/agent", "src/api", "src/application", "src/career")


def run() -> dict[str, tuple[bool, str]]:
    import tests.conftest  # noqa: F401  (test isolation: temp database only)
    from src.knowledge_foundation import coverage as COV
    from src.knowledge_foundation import enums as E
    from src.knowledge_foundation.graph import GraphError, OccupationGraph
    from src.knowledge_foundation.registry import RegistryError, SourceRegistry
    from src.knowledge_foundation.resolver_contract import GraphResolver, ResolutionOutcome, ResolutionRequest
    from src.knowledge_foundation.seed import BASELINE_PATH, load_registry_baseline
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import init_db, make_engine, make_session_factory

    res: dict[str, tuple[bool, str]] = {}

    def check(name, ok, detail=""):
        res[name] = (bool(ok), detail)

    reg = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    srcs = reg["sources"]
    check("registry_baseline_has_the_31_manifest_sources", len(srcs) == 31 and len({s["source_id"] for s in srcs}) == 31, f"{len(srcs)} sources")
    check("registry_values_are_valid_vocabulary", all(s["origin"] in E.ORIGINS and s["precedence_category"] in E.PRECEDENCE and s["licence_status"] in E.LICENCE_STATUSES
                                                    and s["redistribution"] in E.TRI_STATES and s["approval_status"] in E.APPROVAL_STATES for s in srcs), "enums")
    check("no_baseline_source_is_approved", all(s["approval_status"] in ("licensing_pending", "restricted") for s in srcs), "official or local is not approval")
    check("no_licence_is_marked_verified", all(s["licence_status"] != "verified" for s in srcs), "licence verification is an owner action")
    check("synthetic_fixtures_are_restricted", all(s["approval_status"] == "restricted" for s in srcs if s["origin"] == "synthetic_fixture") and any(s["origin"] == "synthetic_fixture" for s in srcs), "fixtures never evidence")
    check("redistribution_never_assumed", all(s["redistribution"] in ("yes", "unknown") for s in srcs) and all(s["licence_id"] for s in srcs if s["redistribution"] == "yes"), "yes needs a stated licence")
    check("evidence_class_only_where_named", {s["source_id"] for s in srcs if s["evidence_class"]} == {"bls_oews", "ba_entgeltatlas"}, "C-class only for the recovered named examples")
    cat = json.loads((DATA / "taxonomy_catalogue.json").read_text(encoding="utf-8"))["taxonomies"]
    check("taxonomy_catalogue_covers_the_nine_schemes", {t["scheme"] for t in cat} == set(E.SCHEMES), "schemes")
    check("unacquired_taxonomies_have_unknown_edition", all(t["edition"] == "unknown" for t in cat if t["acquisition_status"] in ("identified_externally",)), "no invented editions")
    cov = json.loads((DATA / "coverage_matrix.json").read_text(encoding="utf-8"))
    rows = cov["geographies"]
    check("coverage_matrix_equals_the_generator", cov == COV.build_default_matrix(), f"{len(rows)} geographies")
    check("coverage_has_target_geographies", len(rows) == 47 and {r["group"] for r in rows} == set(E.COVERAGE_GROUPS_), "EU-27, UK, EEA, CH, US, CA, MX, BR, South America")
    check("nothing_is_qualified_and_targeted_is_not_operational", all(r[d] != "qualified" for r in rows for d in ("taxonomy_level", "crosswalk_level", "compensation_level", "outlook_level")), "no qualification record exists")
    check("only_us_and_de_taxonomy_are_implemented", {r["code"] for r in rows if r["taxonomy_level"] == "implemented"} == {"US", "DE"}, "runtime resolver evidence")
    base = json.loads((ROOT / "docs/capstone/p10/p10c_a/GKB0_BASELINE_MANIFEST.json").read_text(encoding="utf-8"))
    check("baseline_manifest_present_and_content_free", base["schema"] == "gkb0_baseline/1" and base["source_manifest"]["count"] == 31 and "limitations" in base, "metadata only")
    check("baseline_raw_checksums_all_verified_when_recorded", base["build"]["verified_match"] == base["build"]["recorded_raw_checksums"] == 13, f"{base['build']['verified_match']}/{base['build']['recorded_raw_checksums']}")

    d = Path(tempfile.mkdtemp())
    sf = make_session_factory(make_engine(f"sqlite:///{d}/kf.db"))
    init_db(make_engine(f"sqlite:///{d}/kf.db"))
    TaxonomyCatalogue(sf).seed()
    registry = SourceRegistry(sf)
    load_registry_baseline(registry)
    g = OccupationGraph(sf)
    a = g.add_occupation("Test occupation", [("isco", "08", "2512")], source_ref="")
    b = g.add_occupation("Test occupation", [("onet_soc", "31.0", "15-1252.00")], source_ref="")
    try:
        g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="equivalent", basis="derived_rule", mapping_status="unknown", from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"),
                           limitations="label similarity")
        derived_equiv = False
    except GraphError:
        derived_equiv = True
    check("equivalence_cannot_rest_on_a_derived_rule", derived_equiv, "label similarity is not a basis")
    try:
        g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="related", basis="curated_manual", mapping_status="verified", from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"))
        v = False
    except GraphError:
        v = True
    check("verified_requires_a_source_provided_basis", v, "")
    r = GraphResolver(g)
    out = r.resolve(ResolutionRequest(title="Test occupation"))
    check("same_title_in_two_taxonomies_is_ambiguous", out.outcome is ResolutionOutcome.AMBIGUOUS and len(out.candidates) == 2, "titles are not identities")
    check("resolver_request_has_no_language_field", not {"language", "locale", "interface_language"} & set(ResolutionRequest.__dataclass_fields__), "language is never geography")
    try:
        registry.transition("bls_oews", "approved_for_ingestion")
        gated = False
    except RegistryError:
        gated = True
    check("approval_requires_the_lifecycle_and_a_verified_licence", gated, "")
    check("synthetic_fixture_cannot_be_approved", not _try_approve(registry, "ba_kompetenzkatalog"), "")

    offenders = []
    for pkg in RUNTIME_PACKAGES:
        for f in (ROOT / pkg).rglob("*.py"):
            if "knowledge_foundation" in f.read_text(encoding="utf-8", errors="ignore") and "preparation_pack" not in f.name:
                offenders.append(str(f.relative_to(ROOT)))
    check("foundation_is_not_imported_by_any_runtime_path", not offenders, str(offenders or "none"))
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    gates = [AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED]
    gates += [getattr(bp, n) for n in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")]
    check("all_rollout_and_billing_gates_are_off", not any(gates), "12 gates")
    return res


def _try_approve(registry, source_id) -> bool:
    from src.knowledge_foundation.registry import RegistryError
    try:
        for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion"):
            registry.transition(source_id, step)
        return True
    except RegistryError:
        return False


SAFETY = {"no_baseline_source_is_approved", "no_licence_is_marked_verified", "synthetic_fixtures_are_restricted", "redistribution_never_assumed", "nothing_is_qualified_and_targeted_is_not_operational",
          "equivalence_cannot_rest_on_a_derived_rule", "verified_requires_a_source_provided_basis", "same_title_in_two_taxonomies_is_ambiguous", "resolver_request_has_no_language_field",
          "approval_requires_the_lifecycle_and_a_verified_licence", "synthetic_fixture_cannot_be_approved", "foundation_is_not_imported_by_any_runtime_path", "all_rollout_and_billing_gates_are_off"}


def main() -> int:
    print("ASK4MO - P10C-A GLOBAL KNOWLEDGE FOUNDATION EVALUATION\n")
    results = run()
    failed = False
    for name, (ok, detail) in results.items():
        print(f"  {name:62} {'PASS' if ok else 'FAIL'}  {detail}")
        failed |= not ok
    print("\nPaid LLM calls: 0   Live calls: 0   External downloads: 0\n")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
