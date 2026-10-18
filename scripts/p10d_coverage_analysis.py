#!/usr/bin/env python
"""P10D product-coverage root-cause analysis (read-only; reports, never changes a baseline, a case or the 95% threshold).

Runs the unchanged 412-case evaluator through the P10C-G guard's own runner, compares the result with the baseline of the detected environment profile, and attributes every
insufficient case to a root cause. It also reports the sufficient cases whose ONLY evidence comes from a synthetic-fixture source (the evaluator counts source families, not
data origin, and not the country of an evidence row). The profiles are never combined and nothing here is a pass against the gate.

    python scripts/p10d_coverage_analysis.py [--json PATH] [--md PATH]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("p10_guard", ROOT / "scripts/check_product_coverage_baseline.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
from src.copilot.knowledge.origins import is_fixture_only, load_origins  # noqa: E402


def cause(case: dict, row: dict, stores_present: bool) -> str:
    if not stores_present:
        return "generated knowledge stores absent (clean checkout): nothing to retrieve; the case is sufficient only when abstention is acceptable"
    fam, geo = case["question_family"], case["geography"]
    if fam == "compensation":
        return f"compensation ({geo}): no official record matches this occupation title in the runtime store; no mapping is forced (a P10C resolver and source-qualification dependency)"
    if fam in ("future_growth", "short_term_outlook", "annual_openings"):
        return "outlook: the occupation is not mapped to a BLS-projections occupation; no mapping is forced"
    if fam == "education":
        return "education: the resolved occupation has no education attribute (BLS OOH covers a subset of occupations)"
    return f"no evidence ({fam})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    a = ap.parse_args(argv)
    cases = {c["id"]: c for c in json.loads(G.CASES.read_text())["cases"]}
    stores = G.store_report()
    profile = G.detect_profile(stores)
    rows = G.run_evaluator()
    parsed = G.parse_results(rows, list(cases))
    by_id = {r["id"]: r for r in rows}
    base = json.loads(G.BASELINE.read_text())["profiles"].get(profile)
    fixture = {sid for sid, o in load_origins().items() if is_fixture_only(o)}
    insufficient = parsed["insufficient_case_ids"]
    causes = Counter(cause(cases[i], by_id[i], any(stores.values())) for i in insufficient)
    fx_dep = sorted(i for i, r in by_id.items() if r["insufficient_ok"] == "True" and r["evidence"] not in ("", "0")
                    and set(filter(None, r["sources"].split("|"))) and set(filter(None, r["sources"].split("|"))) <= fixture)
    out = {"profile": profile, "stores_present": stores, "total": parsed["cases"], "sufficient": parsed["sufficient"], "insufficient": parsed["insufficient"], "required_for_gate": 392,
           "gate": "BELOW_GATE" if parsed["sufficient"] < 392 else "AT_OR_ABOVE_GATE_REPORTED", "baseline_sufficient": base and base["sufficient"],
           "improved": sorted(set(base["insufficient_case_ids"]) - set(insufficient)) if base else None, "regressed": sorted(set(insufficient) - set(base["insufficient_case_ids"])) if base else None,
           "root_causes": dict(causes.most_common()), "sufficient_only_because_of_synthetic_fixture_evidence": fx_dep,
           "sufficient_excluding_synthetic_fixture_dependence": parsed["sufficient"] - len(fx_dep), "insufficient_case_ids": insufficient}
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    if a.md:
        Path(a.md).write_text("# P10D product-coverage root causes [" + profile + "]\n\n" + f"{out['sufficient']}/{out['total']} sufficient (gate needs 392): {out['gate']}.\n\n" + "\n".join(f"- {n} x {c}" for c, n in causes.most_common())
                              + f"\n\nSufficient only because of synthetic-fixture evidence: {fx_dep or 'none'}. Excluding them: {out['sufficient_excluding_synthetic_fixture_dependence']}/{out['total']}.\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "insufficient_case_ids"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
