"""P10E execution plan: per test area, the cases, provider, model profile and a LOW/HIGH estimate of calls, tokens and cost.

Pure and offline (no provider call). The call counts and token sizes are ENGINEERING ASSUMPTIONS stated beside each row, not measurements: the real numbers come from the
guarded live run. Cost is computed with the published price snapshot (``evaluations/p10e/pricing_snapshot.json``); where a price or workload is not known the cost is the string
"UNKNOWN", never zero, and that area is excluded from the totals and listed as an open decision.
"""

from __future__ import annotations

from decimal import Decimal

from src.p10e.guard import load_prices

PROFILE_SLUG = {"fast": "openai/gpt-5.6-luna", "balanced": "openai/gpt-5.6-terra", "advanced": "openai/gpt-5.6-sol"}


def _cost(prices: dict, profile: str, calls: int, tin: int, tout: int) -> Decimal:
    pi, po = prices[PROFILE_SLUG[profile]]
    return (pi * tin + po * tout) * calls


def _row(prices: dict, area: str, profile: str, cases: int | None, calls_lo: int, calls_hi: int, in_lo: int, in_hi: int, out_lo: int, out_hi: int, *, evidence: str, implemented: str, note: str) -> dict:
    lo = _cost(prices, profile, calls_lo, in_lo, out_lo)
    hi = _cost(prices, profile, calls_hi, in_hi, out_hi)
    return {"area": area, "provider": "OpenRouter", "profile": profile, "model": PROFILE_SLUG[profile], "cases": cases, "calls_low": calls_lo, "calls_high": calls_hi,
            "input_tokens_low": calls_lo * in_lo, "input_tokens_high": calls_hi * in_hi, "output_tokens_low": calls_lo * out_lo, "output_tokens_high": calls_hi * out_hi,
            "cost_usd_low": str(lo.quantize(Decimal("0.0001"))), "cost_usd_high": str(hi.quantize(Decimal("0.0001"))), "evidence": evidence, "implementation_status": implemented, "assumptions": note}


def build_plan(prices: dict | None = None) -> dict:
    prices = prices or load_prices()
    A, B = "agent decision metrics (tool selection, retrieval decision, HITL, refusal) per profile", "answer_grounded, abstains_when_unsupported, no_cross_country_claim, injection_resistance (deterministic); human metrics PENDING_HUMAN_REVIEW"
    rows = [
        _row(prices, "smoke", "fast", 1, 1, 1, 300, 300, 100, 200, evidence="authentication, schema, usage and latency reporting", implemented="IMPLEMENTED (guarded); NOT RUN", note="one tiny request per profile"),
        _row(prices, "smoke", "balanced", 1, 1, 1, 300, 300, 100, 200, evidence="same", implemented="IMPLEMENTED (guarded); NOT RUN", note="one tiny request per profile"),
        _row(prices, "smoke", "advanced", 1, 1, 1, 300, 300, 100, 200, evidence="same", implemented="IMPLEMENTED (guarded); NOT RUN", note="one tiny request per profile"),
        _row(prices, "live_agent_22_cases", "balanced", 22, 22 * 3, 22 * 8, 3000, 8000, 300, 1500, evidence=A, implemented="EXISTING runner (scripts/eval_agent_live.py), wired to the guard; NOT RUN", note="3 to 8 nested model calls per agent run; reasoning tokens bill as output"),
        _row(prices, "live_agent_22_cases", "fast", 22, 22 * 3, 22 * 8, 3000, 8000, 300, 1500, evidence=A, implemented="same; optional comparison", note="same sizes as Balanced"),
        _row(prices, "live_agent_22_cases", "advanced", 22, 22 * 3, 22 * 8, 3000, 8000, 300, 1500, evidence=A, implemented="same; optional comparison", note="same sizes as Balanced"),
        _row(prices, "kb_model_quality_answer_cases", "balanced", 9, 9, 9, 450, 1500, 200, 1200, evidence=B, implemented="IMPLEMENTED for the 9 answer cases (guarded); NOT RUN", note="dry run measured 3,678 input tokens over the 9 answer cases (about 410 each); evidence cases need a synthesis harness that does not exist"),
        _row(prices, "kb_model_quality_answer_cases", "fast", 9, 9, 9, 450, 1500, 200, 1200, evidence=B, implemented="same; contract compares all three profiles", note="same sizes"),
        _row(prices, "kb_model_quality_answer_cases", "advanced", 9, 9, 9, 450, 1500, 200, 1200, evidence=B, implemented="same; contract compares all three profiles", note="same sizes"),
        _row(prices, "interview_quality_balanced_part", "balanced", 8, 8 * 3, 8 * 3, 3000, 6000, 500, 2000, evidence="question relevance, follow-ups, feedback usefulness: judged by named reviewers", implemented="NOT IMPLEMENTED (harness and synthetic persona set to be built)", note="8 role families x (generate, follow-up, second turn)"),
        _row(prices, "interview_quality_advanced_part", "advanced", 8, 8 * 2, 8 * 2, 3000, 6000, 500, 2000, evidence="answer evaluation and final report", implemented="NOT IMPLEMENTED (harness and synthetic persona set to be built)", note="8 role families x (evaluate, final report); matches the Advanced workload policy"),
        _row(prices, "failure_paths_live", "fast", 2, 2, 2, 100, 100, 10, 10, evidence="invalid model and rejected credential produce controlled errors", implemented="NOT IMPLEMENTED live (offline fakes cover every other failure mode)", note="error responses expected to be free; unknown until observed"),
    ]
    unknown = [
        {"area": "ragas_judge", "reason": "judge model price not in the snapshot and the RAGAS runner makes nested calls that the guard cannot yet intercept", "workload": "35 cases x about 4 judge calls = about 140 judge calls plus 35 answer generations (offline estimator)", "implementation_status": "EXISTING runner; guard integration NOT IMPLEMENTED; needs RAGAS_EVAL_API_KEY (not configured)"},
        {"area": "semantic_retrieval_calibration", "reason": "no embedding provider or model is selected or configured (COPILOT_EMBEDDING_API_KEY absent) and no price is known", "workload": "isolated temporary index over the P10D corpus plus its 33 retrieval cases; separate calibration and validation splits to be defined before any call", "implementation_status": "NOT IMPLEMENTED; needs an owner decision on the embedding provider and model"},
        {"area": "multilingual_live", "reason": "the 20 selected contract cases cover only en, de and fr; the other four knowledge-base languages need cases whose expectations are fixed BEFORE any model output exists", "workload": "to be authored", "implementation_status": "NOT IMPLEMENTED"},
    ]
    def total(key: str, profile: str | None = None, areas: set[str] | None = None) -> Decimal:
        return sum((Decimal(r[key]) for r in rows if (profile is None or r["profile"] == profile) and (areas is None or r["area"] in areas)), Decimal(0))
    core = {"smoke", "live_agent_22_cases", "kb_model_quality_answer_cases", "interview_quality_balanced_part", "interview_quality_advanced_part", "failure_paths_live"}
    core_rows = [r for r in rows if r["area"] in core and not (r["area"] in ("live_agent_22_cases", "kb_model_quality_answer_cases") and r["profile"] != "balanced")]
    def tot(rs: list, k: str):
        return sum((Decimal(r[k]) for r in rs), Decimal(0))
    envelope = {"scope": "smoke (3 profiles) + live agent (Balanced) + KB answer cases (Balanced) + interview quality sample + failure paths",
                "calls_low": int(tot(core_rows, "calls_low")), "calls_high": int(tot(core_rows, "calls_high")), "cost_usd_low": str(tot(core_rows, "cost_usd_low")), "cost_usd_high": str(tot(core_rows, "cost_usd_high")),
                "all_rows_cost_usd_low": str(total("cost_usd_low")), "all_rows_cost_usd_high": str(total("cost_usd_high")), "all_rows_calls_high": sum(r["calls_high"] for r in rows)}
    return {"schema": "p10e-execution-plan/1", "generated_on": "2026-10-19", "no_provider_call_made": True, "price_snapshot": "evaluations/p10e/pricing_snapshot.json",
            "rows": rows, "areas_with_unknown_cost": unknown, "estimated_envelope_for_the_core_scope": envelope,
            "caveat": "LOW and HIGH bound an assumption, not the truth: reasoning-model output can exceed the HIGH output figure and is capped only by the per-request output limit. The guard enforces a worst-case ceiling per call, so a run stops rather than overspends, and may stop early if the approved ceiling is tight."}
