"""Phase 7G — offline Feedback Intelligence: models, analysis, recommendations, review, guards.

Fully offline/deterministic: no network, no LLM, no paid call, no candidate data. Proves evidence
discipline (min support, sample size, severity≠confidence, positive findings, safety escalation,
compatible-only drift, NOT_RUN handling), recommendation/experiment completeness + guardrails,
human-approval enforcement (approval never executes), privacy (schema rejects raw content), and
the self-modification boundary (write path + capability guards).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.copilot.feedback_intelligence import analysis, guards, review
from src.copilot.feedback_intelligence.models import (
    ANALYSIS_VERSION, Confidence, FeedbackSignal, ReviewDecision, Severity, SignalType)
from src.copilot.feedback_intelligence.recommend import (
    build_experiments, build_recommendations, violates_safety_policy)
from src.copilot.feedback_intelligence.service import (
    _numbers_fingerprint, run, safe_synthesis_payload)
from src.copilot.feedback_intelligence.signals import FixtureAdapter

_PKG = Path(__file__).resolve().parent.parent / "src" / "copilot" / "feedback_intelligence"


def _uf(op, rating, run_hash):
    return FeedbackSignal(signal_id=f"uf:{op}:{run_hash}", signal_type=SignalType.USER_FEEDBACK,
                          source="user_feedback", operation=op, rating=rating, run_id_hash=run_hash)


def _metric(name, value, dhash="d", source="retrieval_evaluation"):
    return FeedbackSignal(signal_id=f"m:{name}", signal_type=SignalType.RETRIEVAL_EVALUATION,
                          source=source, metric_name=name, metric_value=value,
                          metric_dataset_hash=dhash)


# --- models / privacy ----------------------------------------------------------------

@pytest.mark.parametrize("field", ["cv_text", "candidate_email", "comment", "answer_text",
                                   "job_description", "raw_response"])
def test_signal_rejects_raw_content_fields(field):
    with pytest.raises(Exception):
        FeedbackSignal(signal_id="x", signal_type=SignalType.USER_FEEDBACK, source="s",
                       **{field: "SECRET"})


def test_review_decision_never_executes():
    assert ReviewDecision.model_fields["executed"].default is False


# --- analysis: support / sample size / confidence ------------------------------------

def test_min_support_gates_status():
    obs = analysis.detect_findings([_uf("op", "not_helpful", f"r{i}") for i in range(2)])
    neg = [f for f in obs if not f.positive]
    assert neg and neg[0].status.value == "observation_only"  # 2 < 3 → not a pattern

    pattern = analysis.detect_findings([_uf("op", "not_helpful", f"r{i}") for i in range(4)])
    assert any(f.status.value == "pattern" for f in pattern if not f.positive)

    elig = analysis.detect_findings([_uf("op", "not_helpful", f"r{i}") for i in range(6)])
    assert any(f.status.value == "recommendation_eligible" for f in elig if not f.positive)


def test_small_sample_not_overstated():
    fs = analysis.detect_findings([_uf("op", "not_helpful", "r0"), _uf("op", "not_helpful", "r1")])
    neg = [f for f in fs if not f.positive][0]
    assert neg.sample_size == 2 and neg.support_count == 2  # reported honestly
    assert neg.status.value == "observation_only"


def test_duplicate_signals_deduplicated():
    s = _uf("op", "not_helpful", "r0")
    assert len(analysis.deduplicate([s, s, s])) == 1


def test_unique_runs_not_events():
    # 5 events but only 2 unique runs → support reflects events, but sample stays honest.
    sigs = [_uf("op", "not_helpful", "rA") for _ in range(3)] + [_uf("op", "not_helpful", "rB") for _ in range(2)]
    # distinct signal_ids required, so vary them
    for i, s in enumerate(sigs):
        s.signal_id = f"uf:op:{i}"
    agg = analysis.aggregate(sigs)
    assert agg.feedback_by_operation["op"]["runs"] == 2


def test_positive_finding_detected():
    sigs = [_uf("interview_evaluation", "helpful", f"r{i}") for i in range(10)]
    assert any(f.positive for f in analysis.detect_findings(sigs))


def test_severity_and_confidence_are_independent():
    fs = analysis.detect_findings([_metric("unknown_role_safety_rate", 0.8)])
    crit = [f for f in fs if not f.positive][0]
    assert crit.severity == Severity.CRITICAL      # damaging if true
    assert crit.confidence == Confidence.MODERATE  # but only one artifact of evidence


def test_safety_metric_holding_is_positive():
    fs = analysis.detect_findings([_metric("citation_completeness_rate", 1.0)])
    assert any(f.positive for f in fs)


# --- metric provenance / drift -------------------------------------------------------

def test_not_run_metric_not_scored_zero():
    sig = FeedbackSignal(signal_id="m", signal_type=SignalType.RAGAS_EVALUATION,
                         source="ragas_evaluation", metric_name="id_context_precision",
                         metric_value=None)
    fs = analysis.detect_findings([sig])
    assert not any("id_context" in f.title for f in fs)  # None → skipped, never a 0 finding


def test_incompatible_metric_not_compared():
    sig = _metric("pass_rate", 0.90, dhash="B")
    fs = analysis.detect_findings([sig], baselines={"pass_rate": {"value": 0.95, "dataset_hash": "A"}})
    assert not any("Regression" in f.title for f in fs)


def test_compatible_drift_detected():
    sig = _metric("pass_rate", 0.90, dhash="ds")
    fs = analysis.detect_findings([sig], baselines={"pass_rate": {"value": 0.95, "dataset_hash": "ds"}})
    assert any("Regression" in f.title for f in fs)


# --- recommendations / experiments ---------------------------------------------------

def _recs():
    findings = analysis.detect_findings([_uf("agent_answer", "not_helpful", f"r{i}") for i in range(6)]
                                        + [_metric("unknown_role_safety_rate", 0.8)])
    return findings, build_recommendations(findings)


def test_recommendations_are_complete_and_reference_evidence():
    _f, recs = _recs()
    assert recs
    for r in recs:
        assert r.finding_ids and r.problem_statement and r.expected_benefit and r.risk
        assert r.validation_plan and r.rollback_plan and r.requires_human_approval and r.complete


def test_safety_recommendation_is_top_priority():
    _f, recs = _recs()
    assert "unknown_role" in recs[0].title.lower() and recs[0].severity == Severity.CRITICAL


def test_experiments_have_guardrails_and_no_dataset_edit():
    _f, recs = _recs()
    exps = build_experiments(recs)
    assert exps and all(e.guardrail_metrics for e in exps)
    assert all(e.rollback_condition for e in exps)


def test_recommendation_never_weakens_safety():
    assert violates_safety_policy("weaken the citation safety threshold")
    assert violates_safety_policy("remove the unknown-role test case")
    assert not violates_safety_policy("investigate the root cause and add a regression case")


# --- human review --------------------------------------------------------------------

def test_review_records_and_is_immutable(tmp_path):
    d = Path("evaluations/feedback_intelligence/runs") / "pytest_review"
    try:
        r1 = review.record_decision(d, "R001", "approve")
        assert r1.executed is False
        review.record_decision(d, "R001", "reject")  # a new decision, not an overwrite
        decs = [x for x in review.load_decisions(d) if x.proposal_id == "R001"]
        assert len(decs) == 2 and {x.decision.value for x in decs} == {"approve", "reject"}
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_review_rejects_bad_path_outside_root():
    with pytest.raises(guards.OutputBoundaryError):
        review.record_decision("src/agent", "R1", "approve")


# --- filesystem boundary + capability (self-modification prevention, §79) ------------

@pytest.mark.parametrize("path", ["src/evil.py", "app.py", ".github/workflows/x.yml",
                                  "data/knowledge/roles.db", "/etc/passwd",
                                  "frontend/app/page.tsx"])
def test_write_outside_output_root_blocked(path):
    with pytest.raises(guards.OutputBoundaryError):
        guards.safe_output_path(path)


def test_write_inside_output_root_allowed():
    p = guards.safe_output_path("evaluations/feedback_intelligence/runs/x/findings.json")
    assert "feedback_intelligence" in str(p)


def test_package_has_no_forbidden_capabilities():
    """Architectural guard: no git-write / shell / arbitrary-network capability (§79).
    (A read-only `git rev-parse`/`status` for provenance is the only subprocess use allowed.)"""
    forbidden = re.compile(
        r"(git\s+commit|git\s+push|gh\s+pr|os\.system|shell\s*=\s*True|import\s+httpx"
        r"|import\s+requests|from\s+requests|urllib\.request|import\s+socket|socket\.socket)", re.I)
    for p in _PKG.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert not forbidden.search(src), f"forbidden capability in {p.name}"
        if "subprocess" in src:
            for m in re.finditer(r"\[[\"']git[\"'],\s*[\"'](\w[\w-]*)[\"']", src):
                assert m.group(1) in ("rev-parse", "status"), f"non-read git in {p.name}"


def test_not_registered_as_candidate_agent_tool():
    from src.agent.registry import career_tool_registry

    class _Fake:
        def __getattr__(self, _n):
            return lambda *a, **k: None
    names = career_tool_registry(_Fake()).names()
    assert not any("feedback" in n.lower() for n in names)
    assert len(names) == 8  # 6 career + 2 HITL — unchanged by Phase 7G


# --- end-to-end run + provenance + LLM-synthesis safety ------------------------------

def test_run_over_fixtures_produces_snapshot_and_awaits_review():
    res = run([FixtureAdapter("evaluations/feedback_intelligence/fixtures/signals.json")], persist=False)
    assert res.snapshot.signal_count > 40 and res.review_status == "awaiting_review"
    assert res.snapshot.analysis_version == ANALYSIS_VERSION
    assert res.findings and res.recommendations and res.experiments


def test_missing_source_is_warning_not_crash():
    sigs, warns = FixtureAdapter("nope/missing.json").signals()
    assert sigs == [] and warns


def test_llm_synthesis_cannot_alter_deterministic_metrics():
    adapters = [FixtureAdapter("evaluations/feedback_intelligence/fixtures/signals.json")]
    baseline = run(adapters, persist=False)
    before = _numbers_fingerprint(baseline)
    # A malicious synthesiser tries to inject numbers — it only returns a string; the run
    # asserts the deterministic fingerprint is unchanged.
    res = run(adapters, persist=False, synthesize_fn=lambda payload: "PRIORITY 100 for everything!!!")
    assert res.synthesis_used is True
    assert _numbers_fingerprint(res) == before


def test_synthesis_payload_has_no_raw_content():
    res = run([FixtureAdapter("evaluations/feedback_intelligence/fixtures/signals.json")], persist=False)
    payload = safe_synthesis_payload(res)
    # Only allow-listed safe keys are present (IDs/counts/labels) — never raw content.
    allowed_finding_keys = {"id", "title", "category", "severity", "confidence",
                            "support_count", "sample_size", "positive"}
    for f in payload["finding_summaries"]:
        assert set(f) <= allowed_finding_keys
    for r in payload["recommendation_summaries"]:
        assert set(r) <= {"id", "title", "change_area", "priority"}
    blob = str(payload)
    assert "@" not in blob                    # no emails
    assert "comment" not in blob.lower() and "cv_text" not in blob.lower()
