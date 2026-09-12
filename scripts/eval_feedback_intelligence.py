#!/usr/bin/env python
"""Deterministic Feedback Intelligence evaluation (Phase 7G, §82).

Offline, synthetic, no LLM, no network. Verifies signal normalisation/dedup, pattern detection
with sample-size discipline, safety prioritisation, recommendation completeness + evidence,
experiment guardrails, human-approval enforcement (and no-execution), privacy (schema rejects raw
content), and self-modification prevention (write boundary + capability guards).

Exit 0 when every SAFETY category is 100% and overall pass rate meets --min-pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.feedback_intelligence import analysis, guards, review  # noqa: E402
from src.copilot.feedback_intelligence.models import FeedbackSignal, SignalType  # noqa: E402
from src.copilot.feedback_intelligence.recommend import (  # noqa: E402
    build_experiments, build_recommendations)

CASES = "evaluations/feedback_intelligence/cases.json"
SAFETY_KINDS = ("safety_metric", "privacy", "boundary", "capability")
_PKG = Path(__file__).resolve().parent.parent / "src" / "copilot" / "feedback_intelligence"


def _uf(op, rating, run):
    return FeedbackSignal(signal_id=f"uf:{op}:{run}", signal_type=SignalType.USER_FEEDBACK,
                          source="user_feedback", operation=op, rating=rating, run_id_hash=run)


def _findings_for(signals, baselines=None):
    return analysis.detect_findings(signals, analysis.AnalysisConfig(), baselines=baselines)


def _capability_clean() -> bool:
    """No git-write / shell / network capability in the package (read-only git provenance OK)."""
    forbidden = re.compile(
        r"(git\s+commit|git\s+push|gh\s+pr|os\.system|shell\s*=\s*True|check_output\([^)]*commit"
        r"|import\s+httpx|import\s+requests|from\s+requests|urllib\.request|socket\.socket"
        r"|import\s+socket)", re.I)
    for p in _PKG.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        if forbidden.search(src):
            return False
        # subprocess is permitted ONLY for read-only git rev-parse/status provenance.
        if "subprocess" in src:
            for m in re.finditer(r"\[[\"']git[\"'],\s*[\"'](\w[\w-]*)[\"']", src):
                if m.group(1) not in ("rev-parse", "status"):
                    return False
    return True


def evaluate(cases):
    results = []
    for c in cases:
        kind, ok, detail = c["kind"], True, ""
        try:
            if kind == "support_pattern":
                sigs = ([_uf(c["operation"], "not_helpful", f"r{i}") for i in range(c["not_helpful"])]
                        + [_uf(c["operation"], "helpful", f"h{i}") for i in range(c["helpful"])])
                fs = [f for f in _findings_for(sigs) if not f.positive
                      and f.affected_operation == c["operation"]]
                ok = bool(fs) and fs[0].status.value == c["expect_status"]
                detail = f"status={(fs[0].status.value if fs else None)}"

            elif kind == "positive":
                sigs = ([_uf(c["operation"], "helpful", f"h{i}") for i in range(c["helpful"])]
                        + [_uf(c["operation"], "not_helpful", f"n{i}") for i in range(c["not_helpful"])])
                fs = [f for f in _findings_for(sigs) if f.positive]
                ok = bool(fs)

            elif kind == "duplicate":
                s = _uf("agent_answer", "not_helpful", "r0")
                deduped = analysis.deduplicate([s, s, s])
                ok = len(deduped) == c["expect_unique"]

            elif kind == "safety_metric":
                sig = FeedbackSignal(signal_id="m", signal_type=SignalType.RETRIEVAL_EVALUATION,
                                     source="retrieval_evaluation", metric_name=c["metric"],
                                     metric_value=c["value"], metric_dataset_hash="d")
                fs = _findings_for([sig])
                if c.get("expect_positive"):
                    ok = any(f.positive for f in fs)
                else:
                    ok = any(f.severity.value == c["expect_severity"] and not f.positive for f in fs)

            elif kind == "metric_missing":
                # A None metric value must NOT create a zero-valued finding (§26).
                sig = FeedbackSignal(signal_id="m", signal_type=SignalType.RAGAS_EVALUATION,
                                     source="ragas_evaluation", metric_name="id_context_precision",
                                     metric_value=None)
                fs = _findings_for([sig])
                ok = all(f.rate != 0.0 for f in fs) and not any("id_context" in f.title for f in fs)

            elif kind == "drift_incompatible":
                sig = FeedbackSignal(signal_id="m", signal_type=SignalType.RETRIEVAL_EVALUATION,
                                     source="retrieval_evaluation", metric_name=c["metric"],
                                     metric_value=c["value"], metric_dataset_hash=c["cur_hash"])
                fs = _findings_for([sig], baselines={c["metric"]: {"value": c["baseline"],
                                                                   "dataset_hash": c["base_hash"]}})
                ok = not any("Regression" in f.title for f in fs)  # incompatible → no compare

            elif kind == "drift_compatible":
                sig = FeedbackSignal(signal_id="m", signal_type=SignalType.RETRIEVAL_EVALUATION,
                                     source="retrieval_evaluation", metric_name=c["metric"],
                                     metric_value=c["value"], metric_dataset_hash=c["dhash"])
                fs = _findings_for([sig], baselines={c["metric"]: {"value": c["baseline"],
                                                                   "dataset_hash": c["dhash"]}})
                ok = any("Regression" in f.title for f in fs)

            elif kind == "rec_quality":
                sigs = [_uf("agent_answer", "not_helpful", f"r{i}") for i in range(6)]
                findings = _findings_for(sigs)
                recs = build_recommendations(findings)
                exps = build_experiments(recs)
                if c["check"] == "finding_ids":
                    ok = all(r.finding_ids for r in recs)
                elif c["check"] == "complete":
                    ok = all(r.complete and r.validation_plan and r.rollback_plan for r in recs)
                elif c["check"] == "guardrails":
                    ok = all(e.guardrail_metrics for e in exps)
                elif c["check"] == "no_dataset_edit":
                    ok = all("do NOT edit" in (e.test_dataset or "") or "cases.json" in (e.test_dataset or "")
                             for e in exps) if exps else True

            elif kind == "review":
                if True:
                    run_dir = Path("evaluations/feedback_intelligence/runs") / f"evaltmp_{c['case_id']}"
                    if c["action"] == "required":
                        sigs = [_uf("agent_answer", "not_helpful", f"r{i}") for i in range(6)]
                        recs = build_recommendations(_findings_for(sigs))
                        ok = all(r.requires_human_approval for r in recs)
                    elif c["action"] == "approve_no_execute":
                        rec = review.record_decision(run_dir, "R001", "approve")
                        ok = rec.executed is False
                    elif c["action"] == "reject":
                        review.record_decision(run_dir, "R002", "reject")
                        decs = review.load_decisions(run_dir)
                        ok = any(x.proposal_id == "R002" and x.decision.value == "reject" for x in decs)
                    elif c["action"] == "defer":
                        review.record_decision(run_dir, "R003", "defer")
                        ok = any(x.decision.value == "defer" for x in review.load_decisions(run_dir))
                    elif c["action"] == "immutable":
                        review.record_decision(run_dir, "R004", "approve")
                        review.record_decision(run_dir, "R004", "reject")
                        decs = [x for x in review.load_decisions(run_dir) if x.proposal_id == "R004"]
                        ok = len(decs) == 2  # history appended, never overwritten
                    import shutil
                    shutil.rmtree(run_dir, ignore_errors=True)

            elif kind == "privacy":
                # The signal schema must REJECT any raw-content/candidate field (extra=forbid).
                try:
                    FeedbackSignal(signal_id="x", signal_type=SignalType.USER_FEEDBACK,
                                   source="user_feedback", **{c["field"]: "SECRET"})
                    ok = False  # it accepted a forbidden field → fail
                except Exception:  # noqa: BLE001
                    ok = True

            elif kind == "boundary":
                blocked = False
                try:
                    guards.safe_output_path(c["path"])
                except guards.OutputBoundaryError:
                    blocked = True
                ok = (blocked == c["expect_blocked"])

            elif kind == "capability":
                ok = _capability_clean()

            elif kind == "missing_source":
                from src.copilot.feedback_intelligence.signals import FixtureAdapter
                sigs, warns = FixtureAdapter("does/not/exist.json").signals()
                ok = sigs == [] and bool(warns)  # graceful: warning, no crash
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"EXC {type(exc).__name__}: {exc}"
        results.append({"case_id": c["case_id"], "kind": kind, "passed": ok, "detail": detail})

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    def _rate(kind):
        rel = [r for r in results if r["kind"] == kind]
        return (round(sum(1 for r in rel if r["passed"]) / len(rel), 4), len(rel)) if rel else (None, 0)

    kinds = sorted({r["kind"] for r in results})
    summary = {"cases": total, "passed": passed,
               "pass_rate": round(passed / total, 4) if total else 0.0,
               "by_kind": {k: _rate(k) for k in kinds}}
    safety_ok = all(_rate(k)[0] in (None, 1.0) for k in SAFETY_KINDS)
    return {"summary": summary, "results": results, "safety_ok": safety_ok}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic Feedback Intelligence evaluation.")
    ap.add_argument("--cases", default=CASES)
    ap.add_argument("--min-pass", type=float, default=0.95)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    report = evaluate(cases)
    s = report["summary"]
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print("FEEDBACK INTELLIGENCE EVALUATION")
        print(f"  cases: {s['cases']}  passed: {s['passed']}  pass_rate: {s['pass_rate']}")
        for k, (rate, n) in s["by_kind"].items():
            print(f"  {k}: {rate} ({n})")
        for r in [r for r in report["results"] if not r["passed"]][:20]:
            print(f"    FAIL [{r['kind']}] {r['case_id']}: {r['detail']}")
    ok = report["safety_ok"] and s["pass_rate"] >= args.min_pass
    print(f"\nGATE: {'PASS' if ok else 'FAIL'} (min_pass={args.min_pass}, safety must be 100%)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
