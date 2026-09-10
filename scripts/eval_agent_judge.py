#!/usr/bin/env python
"""LLM-as-judge qualitative scoring over recorded live agent traces (MANUAL / PAID).

EVALUATION TOOLING ONLY — advisory evidence, never runtime authority. It scores recorded
live responses (from `eval_agent_live.py --record`) with a fixed rubric; it makes NO new
agent runs and NEVER runs in the candidate path or CI.

    python scripts/eval_agent_judge.py                 # safe: cost preview, no paid call
    python scripts/eval_agent_judge.py --allow-paid    # score recorded traces (paid judge)
    python scripts/eval_agent_judge.py --profile advanced --allow-paid

Nothing calls a provider unless you explicitly opt in with ``--allow-paid`` (or
``RUN_PAID_EVAL=1``). Without opt-in it prints a cost preview and stops. The rubric,
validation, thresholds and aggregation live in ``src/agent/judge.py`` and are unit-tested
offline with fixtures (no provider). Human calibration is required — see
``docs/llm_judge_evaluation.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.judge import aggregate_judge, judge_one  # noqa: E402
from src.agent.live_eval import load_live_cases, load_traces  # noqa: E402

SUMMARY_PATH = Path("evaluations/agent_live/judge_summary.json")

# Rough per-judge-call token estimate for the cost preview (material + rubric in; small
# structured JSON out). Deliberately conservative; not a billing figure.
_EST_INPUT_TOKENS = 1200
_EST_OUTPUT_TOKENS = 200


def _paid_opt_in(args) -> bool:
    return bool(args.allow_paid or os.environ.get("RUN_PAID_EVAL") == "1")


def _cost_preview(n_judgeable: int, n_cases: int, profile: str) -> None:
    print("COST PREVIEW")
    print("=" * 60)
    print(f"  judge model profile        {profile}")
    print(f"  recorded traces to judge   {n_judgeable}")
    print("  expected agent requests    0  (this script scores recorded traces only)")
    print(f"  expected judge requests    {n_judgeable}")
    print("  max run count              1")
    print(f"  rough token range          ~{n_judgeable * _EST_INPUT_TOKENS:,} in / "
          f"~{n_judgeable * _EST_OUTPUT_TOKENS:,} out")
    print("  estimated cost             depends on the configured judge model's pricing")
    if n_judgeable < n_cases:
        print("-" * 60)
        print("  FULL PIPELINE (all cases) requires recording live traces first:")
        print(f"    1) python scripts/eval_agent_live.py --allow-paid --record   "
              f"→ ~{n_cases} agent requests")
        print(f"    2) python scripts/eval_agent_judge.py --allow-paid           "
              f"→ ~{n_cases} judge requests")
    print("=" * 60)


def _parse_json(content) -> dict:
    text = content if isinstance(content, str) else str(content)
    text = text.strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` fence if the model wrapped its output.
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def _build_judge_fn(profile: str):
    """Real judge callable (paid). Deterministic temperature; JSON output parsed and
    validated by the rubric layer."""
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model
    from src.llm.models import ModelProfile, model_id

    slug = model_id(ModelProfile[profile.upper()])
    model = build_chat_model(load_config(), model=slug, temperature=0)

    def judge_fn(messages, schema):  # noqa: ARG001 - schema documents the contract
        resp = model.invoke(messages)
        return _parse_json(getattr(resp, "content", resp))

    return judge_fn


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="LLM-as-judge scoring of recorded live traces (manual/paid).")
    p.add_argument("--allow-paid", action="store_true", help="opt in to real judge provider calls (costs money)")
    p.add_argument("--profile", choices=["fast", "balanced", "advanced"], default="advanced",
                   help="judge model tier (Advanced recommended for judging)")
    args = p.parse_args(argv)

    cases = {c["id"]: c for c in load_live_cases()}
    traces = load_traces()
    judgeable = [t for t in traces if t.case_id in cases and getattr(t, "response_text", None)]

    print("LLM-AS-JUDGE — qualitative scoring (EVALUATION TOOLING ONLY)\n")
    print(f"Live cases: {len(cases)} · recorded traces: {len(traces)} · "
          f"judgeable (with response text): {len(judgeable)}\n")
    _cost_preview(len(judgeable), len(cases), args.profile)

    if not _paid_opt_in(args):
        print("\nDID NOT run the judge (no --allow-paid / RUN_PAID_EVAL=1).")
        print("PAID RUN READY — AWAITING USER AUTHORISATION")
        return 0

    if not judgeable:
        print("\nNo judgeable recorded traces. First record live traces with:")
        print("  python scripts/eval_agent_live.py --allow-paid --record")
        return 1

    judge_fn = _build_judge_fn(args.profile)
    results = [judge_one(cases[t.case_id], t, judge_fn) for t in judgeable]
    summary = aggregate_judge(results)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps({"summary": summary, "cases": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\nJUDGE SUMMARY (advisory — requires human calibration)")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
