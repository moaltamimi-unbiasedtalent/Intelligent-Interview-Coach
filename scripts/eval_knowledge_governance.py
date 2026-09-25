#!/usr/bin/env python
"""Deterministic knowledge-governance evaluation (Capstone P6 / K1–K4).

Offline, no provider call, no cost. Gates the GOVERNANCE MECHANISMS that ship as
committed artifacts (governed K1–K4 datasets, source manifest, multilingual fixtures,
readiness logic, domain separation, abstention) — NOT the size of the generated runtime
KB. The generated KB's readiness is REPORTED honestly (it is git-ignored / must be built)
but does not gate this eval; the hard KB-present check lives in ``scripts/demo_readiness.py``.

    python scripts/eval_knowledge_governance.py

Metrics: manifest_integrity, source_health, readiness, retrieval_smoke, citation_integrity,
geography, unsupported_query, knowledge_domain_separation, multilingual_query_handling,
artifact_readiness. Exits non-zero on any gate failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.knowledge import governance as gov  # noqa: E402
from src.copilot.knowledge import governed_datasets as gd  # noqa: E402

_MULTILINGUAL = Path("evaluations/knowledge/multilingual_cases.json")
_COVERAGE = Path("evaluations/knowledge/coverage_report.json")


def evaluate() -> dict:
    m: dict = {}

    # 1. manifest_integrity — source manifest + unified knowledge manifest load & are sane.
    manifest = gov.knowledge_manifest()
    m["manifest_integrity"] = 1 if (
        manifest.get("curated_source_count", 0) > 0
        and len(manifest.get("governed_datasets", [])) == 4
    ) else 0

    # 2. source_health — every declared store reports a health record deterministically.
    health = gov.source_health()
    m["source_health"] = 1 if all("present" in h or "note" in h for h in health) and health else 0

    # 3. readiness — the readiness LOGIC returns a valid state per component + an overall.
    readiness = gov.overall_readiness()
    valid_states = {s.value for s in gov.ReadinessState}
    m["readiness"] = 1 if (
        readiness["overall"] in valid_states
        and readiness["total_components"] >= 10
        and all(c["state"] in valid_states for c in readiness["components"])
    ) else 0
    m["runtime_kb_state"] = readiness["overall"]  # REPORTED, not gated

    # 4. retrieval_smoke — a deterministic governed-dataset lookup smoke (no big KB needed).
    hit = gd.lookup_compensation("software_developer")
    m["retrieval_smoke"] = 1 if (hit.covered and hit.median and hit.source_authority) else 0

    # 5. citation_integrity — governed compensation/credential records carry provenance.
    k1_ok = hit.reference_year is not None and hit.source_authority
    cred = gd.lookup_credentials("registered_nurse", jurisdiction="DE")
    k2_ok = cred.covered and cred.required and all(r.get("authority") for r in cred.required)
    m["citation_integrity"] = 1 if (k1_ok and k2_ok) else 0

    # 6. geography — a query for a covered occupation in an UNCOVERED jurisdiction abstains.
    m["geography"] = 1 if (
        gd.lookup_compensation("software_developer", jurisdiction="US").abstained
        and gd.lookup_compensation("software_developer", jurisdiction="DE").covered
    ) else 0

    # 7. unsupported_query — out-of-coverage occupation/profession abstains (no invention).
    m["unsupported_query"] = 1 if (
        gd.lookup_compensation("astronaut").abstained
        and gd.lookup_credentials("astronaut", jurisdiction="DE").abstained
    ) else 0

    # 8. knowledge_domain_separation — governed (official) vs current-market (self-reported)
    #    provenance stay distinct; the coverage matrix keeps them separate.
    domains = {r["domain"]: r for r in gov.coverage_matrix()["rows"]}
    comp_authority = (domains.get("compensation", {}).get("authority") or "").lower()
    market_ready = (domains.get("current_market", {}).get("readiness") or "")
    m["knowledge_domain_separation"] = 1 if (
        "adzuna" not in comp_authority               # governed comp is official, not advertised
        and market_ready == "spec_only"              # current-market kept separate/spec-only
    ) else 0

    # 9. multilingual_query_handling — the 7-language fixtures are present, complete and
    #    each case carries every supported language (bounded handling, not a parity claim).
    try:
        ml = json.loads(_MULTILINGUAL.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        ml = {}
    langs = set(gov.SUPPORTED_LANGUAGES)
    cases = ml.get("cases", [])
    ml_ok = bool(cases) and all(
        langs <= set((c.get("translations") or {}).keys()) for c in cases
    )
    m["multilingual_query_handling"] = 1 if ml_ok else 0
    m["multilingual_languages"] = len(langs)

    # 10. artifact_readiness — the REQUIRED COMMITTED artifacts exist (never silently PASS
    #     when a required governance artifact is missing). Generated KB is separate.
    required = [
        gd.K1_PATH, gd.K2_PATH, gd.K3_PATH, gd.K4_PATH, _MULTILINGUAL, _COVERAGE,
        Path("data/source_manifest.json"),
    ]
    missing = [str(p) for p in required if not Path(p).is_file()]
    m["artifact_readiness"] = 1 if not missing else 0
    m["missing_required_artifacts"] = missing

    return m


GATES = {
    "manifest_integrity": 1, "source_health": 1, "readiness": 1, "retrieval_smoke": 1,
    "citation_integrity": 1, "geography": 1, "unsupported_query": 1,
    "knowledge_domain_separation": 1, "multilingual_query_handling": 1, "artifact_readiness": 1,
}


def gate_failures(m: dict) -> list[str]:
    fails = [f"{k} = {m.get(k)} (want {v})" for k, v in GATES.items() if m.get(k) != v]
    if m.get("missing_required_artifacts"):
        fails.append("missing required artifacts: " + ", ".join(m["missing_required_artifacts"]))
    return fails


def main() -> int:
    m = evaluate()
    print("KNOWLEDGE GOVERNANCE EVALUATION (Capstone P6, offline, no paid calls)")
    print("=" * 68)
    for k in GATES:
        print(f"  {k:<32} {m.get(k)}  (gate == {GATES[k]})")
    print("-" * 68)
    print(f"  runtime_kb_state (reported)      {m.get('runtime_kb_state')}")
    print(f"  multilingual_languages           {m.get('multilingual_languages')}")
    print("=" * 68)
    fails = gate_failures(m)
    if fails:
        print("\nGATE STATUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
