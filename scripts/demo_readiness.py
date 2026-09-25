#!/usr/bin/env python
"""Demo / knowledge readiness check (Capstone P6, §29).

Answers, BEFORE a demo, whether the product can actually retrieve grounded knowledge:
- committed governance artifacts present (governed K1–K4 datasets, source manifest, fixtures)?
- generated runtime KB present & compatible (structured stores + vector index built)?
- sources healthy?
- a retrieval smoke test passes?
- required evaluation fixtures available?

Exits NON-ZERO when a CRITICAL prerequisite is absent, so a demo never discovers a missing
KB only after the user asks a question. Unlike ``eval_knowledge_governance.py`` (which
gates governance logic and REPORTS the runtime KB state), this FAILS on a missing runtime KB.

    python scripts/demo_readiness.py            # governance + runtime KB required
    python scripts/demo_readiness.py --governance-only   # skip the generated-KB requirement
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.knowledge import governance as gov  # noqa: E402
from src.copilot.knowledge import governed_datasets as gd  # noqa: E402

_FIXTURES = [
    Path("evaluations/knowledge/multilingual_cases.json"),
    Path("evaluations/knowledge/coverage_report.json"),
    Path("evaluations/knowledge/retrieval_cases.json"),
]


def _retrieval_smoke() -> tuple[bool, str]:
    """A governed-dataset smoke (always available) — deterministic, no big KB required."""
    r = gd.lookup_compensation("software_developer")
    if r.covered and r.median and r.source_authority:
        return True, f"governed K1 lookup OK (median={r.median} {r.currency})"
    return False, "governed K1 lookup failed"


def main() -> int:
    governance_only = "--governance-only" in sys.argv
    problems: list[str] = []
    lines: list[str] = []

    # Committed governance artifacts (always critical).
    for label, path in [
        ("governed K1", gd.K1_PATH), ("governed K2", gd.K2_PATH),
        ("governed K3", gd.K3_PATH), ("governed K4", gd.K4_PATH),
        ("source manifest", Path("data/source_manifest.json")),
        *[(f"fixture {p.name}", p) for p in _FIXTURES],
    ]:
        ok = Path(path).is_file()
        lines.append(f"  [{'ok' if ok else 'MISSING'}] {label}: {path}")
        if not ok:
            problems.append(f"missing committed artifact: {path}")

    # Retrieval smoke (governed).
    smoke_ok, smoke_detail = _retrieval_smoke()
    lines.append(f"  [{'ok' if smoke_ok else 'FAIL'}] retrieval smoke: {smoke_detail}")
    if not smoke_ok:
        problems.append("retrieval smoke failed")

    # Generated runtime KB (critical for a live demo unless --governance-only).
    readiness = gov.overall_readiness()
    runtime_components = [c for c in readiness["components"]
                         if c["component"].startswith(("structured_store", "vector_index", "build_metadata"))]
    for c in runtime_components:
        ready = c["state"] == "ready"
        lines.append(f"  [{'ok' if ready else c['state'].upper()}] {c['component']}: {c['detail']}")
        if not ready and not governance_only:
            problems.append(f"runtime KB not ready: {c['component']} = {c['state']}")

    print("ASK4MO DEMO / KNOWLEDGE READINESS")
    print("=" * 68)
    print("\n".join(lines))
    print("-" * 68)
    print(f"overall runtime readiness: {readiness['overall']} "
          f"({readiness['ready_components']}/{readiness['total_components']} components ready)")
    print("=" * 68)

    if problems:
        print("\nREADINESS: NOT READY")
        for p in problems:
            print(f"  - {p}")
        if not governance_only and any("runtime KB" in p for p in problems):
            print("\nHint: build the governed KB (normalize + build_runtime_knowledge) and the "
                  "vector index, or run with --governance-only to check committed artifacts only.")
        return 1
    print("\nREADINESS: READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
