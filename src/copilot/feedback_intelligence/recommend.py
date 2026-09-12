"""Findings → human-reviewed recommendations + experiment proposals (Phase 7G, §29–§34).

Deterministic. Only recommendation-eligible findings become recommendations; each carries the
full quality set (problem, evidence, benefit, risk, validation, rollback — §69) and mandatory
safety guardrails (§34). Recommendations NEVER propose weakening a safety control (§27/§70), and
they NEVER contain executable instructions — a human decides, an engineer implements (§36).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.copilot.feedback_intelligence.models import (
    ChangeArea,
    Confidence,
    ExperimentProposal,
    FeedbackFinding,
    FindingCategory,
    FindingStatus,
    ImprovementRecommendation,
    Severity,
)

_AREA_OF = {
    FindingCategory.RETRIEVAL: ChangeArea.RETRIEVAL,
    FindingCategory.GROUNDING: ChangeArea.RETRIEVAL,
    FindingCategory.CITATION: ChangeArea.RETRIEVAL,
    FindingCategory.GEOGRAPHY: ChangeArea.RETRIEVAL,
    FindingCategory.KNOWLEDGE_GAP: ChangeArea.KNOWLEDGE,
    FindingCategory.TOOL_SELECTION: ChangeArea.TOOL_POLICY,
    FindingCategory.EXTERNAL_RESEARCH: ChangeArea.EXTERNAL_RESEARCH,
    FindingCategory.LATENCY: ChangeArea.PERFORMANCE,
    FindingCategory.COST: ChangeArea.PERFORMANCE,
    FindingCategory.RELIABILITY: ChangeArea.PROVIDER,
    FindingCategory.PROVIDER_FAILURE: ChangeArea.PROVIDER,
    FindingCategory.INTERVIEW_PRACTICE: ChangeArea.INTERVIEW_PRACTICE,
    FindingCategory.UX_SIGNAL: ChangeArea.UX,
    FindingCategory.QUALITY: ChangeArea.EVALUATION,
    FindingCategory.SAFETY: ChangeArea.SECURITY,
}

_SEVERITY_WEIGHT = {Severity.CRITICAL: 100, Severity.HIGH: 80, Severity.MEDIUM: 55,
                    Severity.LOW: 30, Severity.INFO: 5}
_CONFIDENCE_WEIGHT = {Confidence.HIGH: 1.0, Confidence.MODERATE: 0.75, Confidence.LOW: 0.5}

# Mandatory safety guardrails on EVERY experiment (§34).
_GUARDRAILS = [
    "citation_completeness stays 1.0",
    "unknown_role_safety stays 1.0",
    "geography_correctness stays 1.0",
    "unsupported_geography_safety stays 1.0",
    "cross_user_isolation failures stay 0",
    "SSRF safety stays 1.0",
    "prompt_injection safety stays 1.0",
    "P0 and P1 remain 0",
]

# A recommendation must never PROPOSE weakening a control (§27/§70).
_FORBIDDEN = re.compile(
    r"(weaken|remove|disable|lower|relax|bypass|skip)\s+.{0,30}"
    r"(safety|citation|geography|ssrf|injection|isolation|privacy|secret|guard|threshold|"
    r"test case|expected answer|hitl|approval)", re.I)


def violates_safety_policy(text: str) -> bool:
    return bool(_FORBIDDEN.search(text or ""))


def _priority(finding: FeedbackFinding) -> int:
    base = _SEVERITY_WEIGHT[finding.severity] * _CONFIDENCE_WEIGHT[finding.confidence]
    support_boost = min(finding.support_count, 10)
    safety_boost = 15 if finding.category in (FindingCategory.SAFETY, FindingCategory.CITATION,
                                              FindingCategory.GEOGRAPHY) else 0
    return int(max(0, min(100, base + support_boost + safety_boost)))


def _recommendation_text(finding: FeedbackFinding) -> tuple[str, str, str, str, str]:
    """Return (recommendation, expected_benefit, risk, validation_plan, rollback_plan).

    All phrased as things to INVESTIGATE/TEST — never 'change line X and deploy' (§33)."""
    cat = finding.category
    if cat in (FindingCategory.CITATION, FindingCategory.GEOGRAPHY, FindingCategory.SAFETY):
        rec = (f"Investigate the {finding.category.value} shortfall behind '{finding.title}'. "
               "Add a targeted deterministic regression case reproducing it, then have an "
               "engineer diagnose the root cause. The safety metric and its cases must remain "
               "intact and continue to be required (fix the cause, not the check).")
    elif cat == FindingCategory.KNOWLEDGE_GAP:
        rec = ("Evaluate acquiring or normalising additional governed source data for the gap "
               "(e.g. assess Destatis occupation-level compensation). Acquisition is a separate, "
               "manually-approved data step — do not auto-register or download.")
    elif cat in (FindingCategory.RELIABILITY, FindingCategory.PROVIDER_FAILURE):
        rec = ("Review provider timeout/retry handling for the recurring error category and "
               "consider a bounded backoff or clearer degraded-mode messaging.")
    elif cat == FindingCategory.QUALITY:
        rec = ("Review the operation with the elevated not-helpful rate; design a deterministic "
               "evaluation case that captures the dissatisfaction before changing anything.")
    else:
        rec = (f"Investigate '{finding.title}' and design a measurable experiment before any "
               "change. Keep local-first and safety behaviour unchanged.")
    benefit = f"Potential improvement in {finding.category.value} outcomes for {finding.affected_operation or finding.affected_domain or 'affected flows'}."
    risk = "Any change could regress safety/grounding; must be gated by the guardrail metrics below."
    validation = ("Reproduce with a deterministic case; measure the target metric before/after on "
                  "the same dataset; confirm all guardrail metrics hold.")
    rollback = "Revert the change if any guardrail metric regresses or the target metric does not improve."
    return rec, benefit, risk, validation, rollback


def build_recommendations(findings: list[FeedbackFinding]) -> list[ImprovementRecommendation]:
    recs: list[ImprovementRecommendation] = []
    n = 0
    now = datetime.now(timezone.utc)
    for f in findings:
        if f.status != FindingStatus.RECOMMENDATION_ELIGIBLE or f.positive:
            continue
        n += 1
        rec_text, benefit, risk, validation, rollback = _recommendation_text(f)
        problem = f"{f.description} (support={f.support_count}, sample={f.sample_size}, " \
                  f"confidence={f.confidence.value}, severity={f.severity.value})."
        # Safety policy guard (§27/§70): never emit a recommendation that weakens a control.
        if any(violates_safety_policy(t) for t in (rec_text, benefit, problem)):
            continue
        complete = all([problem, rec_text, benefit, risk, validation, rollback, f.evidence_refs or True])
        recs.append(ImprovementRecommendation(
            recommendation_id=f"R{n:03d}", finding_ids=[f.finding_id],
            title=f"Address: {f.title}", problem_statement=problem,
            change_area=_AREA_OF.get(f.category, ChangeArea.EVALUATION),
            recommendation=rec_text, expected_benefit=benefit, risk=risk,
            priority=_priority(f), confidence=f.confidence, severity=f.severity,
            support_count=f.support_count, validation_plan=validation, rollback_plan=rollback,
            requires_human_approval=True, complete=bool(complete), created_at=now))
    recs.sort(key=lambda r: r.priority, reverse=True)
    return recs


def build_experiments(recommendations: list[ImprovementRecommendation]) -> list[ExperimentProposal]:
    exps: list[ExperimentProposal] = []
    for i, r in enumerate(recommendations, 1):
        exps.append(ExperimentProposal(
            experiment_id=f"E{i:03d}", recommendation_id=r.recommendation_id,
            hypothesis=(f"Addressing '{r.title}' improves {r.change_area.value} outcomes "
                        "without regressing safety."),
            change_scope=f"{r.change_area.value} (engineer-implemented; no auto-change)",
            target_metric=_target_metric_for(r.change_area),
            baseline="current reviewed baseline", success_criteria="target metric improves on the same dataset",
            guardrail_metrics=list(_GUARDRAILS),
            test_dataset=_dataset_for(r.change_area),
            estimated_risk=("high" if r.severity in (Severity.CRITICAL, Severity.HIGH) else "medium"),
            rollback_condition="any guardrail metric regresses, or the target metric does not improve",
            estimated_effort="unknown", status="proposed"))
    return exps


def _target_metric_for(area: ChangeArea) -> str:
    return {
        ChangeArea.RETRIEVAL: "retrieval evidence_coverage / pass_rate (same 81-case dataset)",
        ChangeArea.KNOWLEDGE: "knowledge coverage for the affected domain",
        ChangeArea.PROVIDER: "provider error rate",
        ChangeArea.TOOL_POLICY: "unnecessary-tool rate (deterministic agent eval)",
        ChangeArea.EXTERNAL_RESEARCH: "external-research eval pass rate",
    }.get(area, "the affected operation's outcome rate")


def _dataset_for(area: ChangeArea) -> str:
    return {
        ChangeArea.RETRIEVAL: "evaluations/knowledge/retrieval_cases.json (81 cases)",
        ChangeArea.EXTERNAL_RESEARCH: "evaluations/external_research/cases.json",
        ChangeArea.TOOL_POLICY: "evaluations/agent/tool_selection_cases.json",
    }.get(area, "an appropriate existing deterministic dataset (do NOT edit it automatically)")
