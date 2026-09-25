#!/usr/bin/env python
"""Deterministic multi-agent + per-operation model-policy evaluation (Capstone P5/E4).

Runs the bounded-specialist and E4 model-policy invariants through a scripted, offline
harness — NO provider calls, NO cost — and prints the metrics plus the release gate
status. Exits non-zero when any required gate fails, so it runs in CI alongside
``scripts/eval_agent.py``.

    python scripts/eval_multi_agent.py

This is NOT a live-model or answer-quality benchmark. It measures: model-policy
resolution (capability floors, deterministic ops, bounded fallback, raw-slug rejection),
specialist routing validity, owner-scoped evidence isolation, the coach's
no-fabrication contract, 7-language prompt-injection inertness, and specialist
orchestration + cross-user denial through the agent service.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.multi_agent_eval import GATES, ZERO_INVARIANTS, evaluate, gate_failures  # noqa: E402


def main() -> int:
    t0 = time.perf_counter()
    metrics = evaluate()
    runtime = time.perf_counter() - t0

    policy_failures = metrics.pop("policy_failures", [])

    print("DETERMINISTIC MULTI-AGENT + MODEL-POLICY METRICS (no provider calls)")
    print("=" * 68)
    print(f"runtime: {runtime:.2f}s   injection languages: {metrics.get('injection_languages')}")
    print("-" * 68)
    order = [
        "policy_pass_rate", "router_valid_rate", "router_bounded_rate",
        "router_deterministic_rate", "injection_inert_rate",
        "uncovered_yield_clarifications", "recommendation_ids_valid",
        "reasoner_bogus_ids_sanitised", "no_owner_returns_empty",
        "specialists_completed", "specialist_packet_present", "specialists_used_count",
        "coaching_present", "evidence_present", "unknown_specialist_rejected",
    ]
    for key in order:
        gate = GATES.get(key)
        gate_str = f"  (gate {gate[0]} {gate[1]})" if gate else ""
        print(f"  {key:<32} {metrics.get(key)}{gate_str}")
    print("-" * 68)
    print("HARD SECURITY INVARIANTS (must be 0)")
    for key in ZERO_INVARIANTS:
        print(f"  {key:<32} {metrics.get(key)}")
    print("=" * 68)

    if policy_failures:
        print(f"\nPOLICY FAILURES ({len(policy_failures)}):")
        for f in policy_failures[:10]:
            print(f"  - {f}")

    failures = gate_failures({**metrics, "policy_failures": policy_failures})
    if failures:
        print("\nGATE STATUS: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
