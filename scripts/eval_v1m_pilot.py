"""Deterministic/offline-first V1M retrieval-need pilot evaluator.

Default mode runs every fixture against the local deterministic baseline and
prints a shadow comparison plan. --live makes at most one synthetic request
per fixture using V1M_PILOT_ENABLED=true and V1M_API_KEY.

No candidate data is sent. Live mode is opt-in and the result never changes
career routing or synthesis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.copilot.rag.v1m_pilot import classify_retrieval_need
from src.copilot.rag.translation import heuristic_translation

CASES_PATH = Path(__file__).resolve().parents[1] / "evaluations" / "v1m" / "pilot_cases.json"


def _baseline(state: str) -> str:
    translated = heuristic_translation(state)
    return "retrieval_needed" if translated.retrieval_required else "retrieval_not_needed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call V1M for synthetic fixtures only")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    matched = 0
    uncertain = 0
    provider_errors = 0

    for case in cases:
        baseline = _baseline(case["state"])
        pilot = classify_retrieval_need(
            case["state"],
            enabled=True,
            threshold=args.threshold,
        ) if args.live else None

        if pilot is None:
            label = "not_run_offline"
        else:
            label = pilot.label
            if pilot.status != "ok":
                provider_errors += 1
            elif pilot.label == "uncertain":
                uncertain += 1
        if pilot is not None and pilot.status == "ok" and label == case["expected"]:
            matched += 1
        agreement = pilot is not None and pilot.status == "ok" and pilot.label == baseline
        print(
            json.dumps({
                "id": case["id"],
                "baseline": baseline,
                "expected": case["expected"],
                "pilot": label,
                "probability": pilot.probability if pilot else None,
                "latency_ms": pilot.latency_ms if pilot else None,
                "agreement": agreement,
            }, sort_keys=True)
        )

    print(json.dumps({
        "mode": "live" if args.live else "offline",
        "cases": len(cases),
        "matched": matched if args.live else None,
        "uncertain": uncertain if args.live else None,
        "provider_errors": provider_errors if args.live else None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
