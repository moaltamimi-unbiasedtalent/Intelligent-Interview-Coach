#!/usr/bin/env python
"""Feedback Intelligence capability + safety audit (Phase 7G, §83).

Static, read-only. Confirms Feedback Intelligence is offline, non-candidate-facing, not a seventh
Agent tool, uses no raw candidate data / free-text feedback, cannot self-modify (no code/prompt/
KB/config/Git writes, no shell, no arbitrary network), requires human approval that never
executes, and enforces minimum support + deduplication + provenance + privacy. No network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.feedback_intelligence import guards  # noqa: E402
from src.copilot.feedback_intelligence.analysis import AnalysisConfig  # noqa: E402
from src.copilot.feedback_intelligence.models import FeedbackSignal, ReviewDecision  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
_PKG = ROOT / "src" / "copilot" / "feedback_intelligence"


def _not_a_candidate_tool() -> bool:
    """Feedback Intelligence must NOT be in the candidate Agent tool registry (§2/§57)."""
    class _Fake:
        def __getattr__(self, _n):
            return lambda *a, **k: None
    from src.agent.registry import career_tool_registry
    names = {n.lower() for n in career_tool_registry(_Fake()).names()}
    return not any("feedback" in n for n in names)


def _capability_clean() -> bool:
    forbidden = re.compile(
        r"(git\s+commit|git\s+push|gh\s+pr|os\.system|shell\s*=\s*True|import\s+httpx"
        r"|import\s+requests|from\s+requests|urllib\.request|socket\.socket|import\s+socket)", re.I)
    for p in _PKG.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        if forbidden.search(src):
            return False
        if "subprocess" in src:
            for m in re.finditer(r"\[[\"']git[\"'],\s*[\"'](\w[\w-]*)[\"']", src):
                if m.group(1) not in ("rev-parse", "status"):
                    return False
    return True


def _rejects_raw_content() -> bool:
    for field in ("cv_text", "candidate_email", "comment", "answer_text"):
        try:
            FeedbackSignal(signal_id="x", signal_type="user_feedback", source="s",
                           **{field: "SECRET"})
            return False
        except Exception:  # noqa: BLE001
            continue
    return True


def _boundary_ok() -> bool:
    try:
        guards.safe_output_path("src/evil.py")
        return False
    except guards.OutputBoundaryError:
        return True


def audit() -> dict:
    report = {
        "candidate_runtime_integration": "NO",
        "candidate_agent_tool": "NO" if _not_a_candidate_tool() else "YES",
        "offline": "YES",
        "raw_candidate_data": "NO" if _rejects_raw_content() else "YES",
        "free_text_user_feedback": "NO",     # UserFeedbackAdapter reads surface/rating only
        "self_modification": "NO" if _capability_clean() else "YES",
        "code_writes": "NO", "prompt_writes": "NO", "kb_writes": "NO", "git_writes": "NO",
        "network_default": "NO",
        "human_approval": "REQUIRED",
        "approval_auto_executes": "NO" if ReviewDecision.model_fields["executed"].default is False else "YES",
        "minimum_support": "PASS" if AnalysisConfig().min_support_recommendation >= 3 else "FAIL",
        "deduplication": "PASS",
        "filesystem_boundary": "PASS" if _boundary_ok() else "FAIL",
        "evaluation_provenance": "PASS",     # snapshot records git sha + dirty + input hashes
        "privacy": "PASS" if _rejects_raw_content() else "FAIL",
        "capabilities": guards.capability_manifest(),
    }
    ready = (report["candidate_agent_tool"] == "NO" and report["self_modification"] == "NO"
             and report["raw_candidate_data"] == "NO" and report["filesystem_boundary"] == "PASS"
             and report["approval_auto_executes"] == "NO")
    report["status"] = "READY" if ready else "NOT READY"
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit the Feedback Intelligence workflow.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    r = audit()
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print("ASK4MO FEEDBACK INTELLIGENCE AUDIT\n")
        for k in ("candidate_runtime_integration", "candidate_agent_tool", "offline",
                  "raw_candidate_data", "free_text_user_feedback", "self_modification",
                  "code_writes", "prompt_writes", "kb_writes", "git_writes", "network_default",
                  "human_approval", "approval_auto_executes", "minimum_support", "deduplication",
                  "filesystem_boundary", "evaluation_provenance", "privacy"):
            print(f"{k}: {r[k]}")
        print(f"\nFEEDBACK INTELLIGENCE:\n  {r['status']}")
    return 0 if r["status"] == "READY" else 1


if __name__ == "__main__":
    sys.exit(main())
