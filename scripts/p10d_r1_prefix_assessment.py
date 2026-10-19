#!/usr/bin/env python
"""P10D-R1: assess what an EARLIER checkout of the candidate retrieval path returned for the 412 product-coverage cases, under the V2 source-backed rules (read-only analysis).

Run it from the root of the checkout to assess (it imports that checkout's ``src``; for a checkout that predates ``evidence_integrity.py`` copy that one module and ``countries.py``
into it first). It uses the structured coordinator exactly as the evaluator does, classifies every returned evidence item with the origin ledger of THIS machine (developer-local),
and reports the cases that the legacy rule counted as sufficient only because of ineligible (synthetic, unknown-origin or wrong-country) evidence. It changes nothing.

    python scripts/p10d_r1_prefix_assessment.py [--json PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401

from src.copilot.config import load_config  # noqa: E402
from src.copilot.knowledge.evidence_integrity import origin_class, source_backed_assessment  # noqa: E402
from src.copilot.knowledge.origins import load_origins  # noqa: E402
from src.copilot.knowledge.retrieval import build_default_coordinator  # noqa: E402
from src.copilot.knowledge.router import route_question  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    cases = json.loads((ROOT / "evaluations/product_coverage/cases.json").read_text())["cases"]
    coord = build_default_coordinator(load_config())
    origins = load_origins()
    origin_of = lambda sid: origin_class(origins.get((sid or "").split(":", 1)[0]))  # noqa: E731
    out, legacy, backed = [], 0, 0
    for c in cases:
        o = coord.retrieve(route_question(c["query"]), c["query"])
        ev = o.evidence
        clarified = bool(getattr(o, "clarify", False))
        handled = bool(ev) or c["insufficient_ok"] or clarified
        asm = source_backed_assessment(ev, c["geography"], origin_of, citation_required=bool(c["citation_required"]))
        sb = bool(asm["eligible"]) or (not ev and c["insufficient_ok"]) or clarified
        legacy += handled
        backed += sb
        if handled and not sb:
            out.append({"id": c["id"], "query": c["query"], "geography": c["geography"], "sources": sorted({e.source_id for e in ev}), "reasons": asm["reasons"], "synthetic_only": asm["synthetic_only"]})
    res = {"legacy_sufficient": legacy, "source_backed_sufficient": backed, "cases": len(cases), "sufficient_legacy_but_not_source_backed": out}
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "sufficient_legacy_but_not_source_backed"}), len(out), "case(s) counted by the legacy rule only because of ineligible evidence")
    for r in out:
        print(" ", r["id"], r["geography"], r["sources"], r["reasons"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
