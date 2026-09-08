#!/usr/bin/env python
"""Deterministic agent-orchestration evaluation (Sprint 4 Phase 11).

Runs the held-out orchestration dataset through the scripted-model harness — NO
provider calls, NO cost — and prints the DETERMINISTIC ORCHESTRATION REGRESSION
METRICS, a HITL/isolation probe, and the release gate status. Exits non-zero when any
required gate fails, so it can run in CI.

    python scripts/eval_agent.py

This is NOT a live-model benchmark or an LLM-accuracy score; it measures tool
routing, agentic-RAG decisions, citation validity, completion and safety invariants.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make the repo root importable when run directly from a clean checkout / CI
# (`python scripts/eval_agent.py`), matching the other scripts/eval_*.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.eval import (  # noqa: E402
    GATES,
    build_eval_career,
    evaluate,
    gate_failures,
    hitl_and_isolation_probe,
    load_cases,
)


def main() -> int:
    t0 = time.perf_counter()
    cases = load_cases()
    metrics = evaluate(cases, build_eval_career())
    probe = hitl_and_isolation_probe()
    runtime = time.perf_counter() - t0

    results = metrics.pop("results", [])
    failed_cases = [
        r for r in results
        if not set(r["expected_tools"]).issubset(set(r["tools_used"]))
        or any(t not in set(r["expected_tools"]) for t in r["tools_used"])
    ]

    print("DETERMINISTIC ORCHESTRATION REGRESSION METRICS (no provider calls)")
    print("=" * 64)
    print(f"cases: {metrics['cases']}   runtime: {runtime:.2f}s")
    print("-" * 64)
    order = [
        "required_tool_recall", "unnecessary_tool_rate", "required_retrieval_recall",
        "unnecessary_retrieval_rate", "citation_validity", "retrieval_sequence_validity",
        "completion_rate", "unregistered_tool_attempts",
    ]
    for key in order:
        gate = GATES.get(key)
        gate_str = f"  (gate {gate[0]} {gate[1]})" if gate else ""
        print(f"  {key:<30} {metrics[key]}{gate_str}")
    print("-" * 64)
    print("HITL / ISOLATION PROBE")
    print(f"  hitl_trigger_recall            {probe['hitl_trigger_recall']}  "
          f"(pending_action={probe.get('_pending_action_type')})")
    print(f"  cross_user_access_failures     {probe['cross_user_access_failures']}  (MUST be 0)")
    print("=" * 64)

    failures = gate_failures(metrics)
    if probe["cross_user_access_failures"] != 0:
        failures.append(f"cross_user_access_failures={probe['cross_user_access_failures']} (must be 0)")
    if probe["hitl_trigger_recall"] < 1.0:
        failures.append("hitl_trigger_recall < 1.0 (ambiguous role did not pause for a human)")

    if failed_cases:
        print(f"\nFAILED CASES ({len(failed_cases)}):")
        for r in failed_cases:
            print(f"  case: {r['id']}\n    expected: {r['expected_tools']}\n    actual:   {r['tools_used']}")

    if failures:
        print("\nGATE STATUS: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
