"""Deterministic analysis: signals → aggregates → findings (Phase 7G).

Pure functions, no LLM, no network. Enforces the evidence-strength discipline: minimum support
(§17), honest sample sizes (§18), confidence separate from severity (§19/§21), positive findings
(§22), safety escalation (§28), duplicate/poisoning protection (§11/§67), unique-run counting
(§68) and compatible-only metric drift (§24/§63).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from src.copilot.feedback_intelligence.models import (
    Confidence,
    FeedbackFinding,
    FeedbackSignal,
    FindingCategory,
    FindingStatus,
    Severity,
    SignalType,
)

# Safety metrics that must hold at 1.0 (or 0 for leakage) — a shortfall escalates severity (§28).
_SAFETY_UNIT_METRICS = {
    "citation_completeness_rate": FindingCategory.CITATION,
    "geography_correctness_rate": FindingCategory.GEOGRAPHY,
    "unknown_role_safety_rate": FindingCategory.SAFETY,
    "unsupported_geography_safety_rate": FindingCategory.SAFETY,
    "ssrf_safety": FindingCategory.SAFETY,
    "prompt_injection_safety": FindingCategory.SAFETY,
}


@dataclass
class AnalysisConfig:
    min_support_observation: int = 3      # < this → OBSERVATION_ONLY (§17)
    min_support_recommendation: int = 5   # >= this → recommendation-eligible
    negative_rate_threshold: float = 0.34  # not-helpful rate that makes a pattern notable
    positive_rate_threshold: float = 0.8   # helpful rate that makes a positive finding


@dataclass
class Aggregates:
    feedback_by_operation: dict = field(default_factory=dict)  # op -> {events, runs, helpful, not_helpful}
    metrics: dict = field(default_factory=dict)                # name -> {value, dataset_hash, version, source}
    error_counts: dict = field(default_factory=dict)
    gap_count: int = 0
    total_signals: int = 0


def deduplicate(signals: list[FeedbackSignal]) -> list[FeedbackSignal]:
    """Drop exact duplicate signal_ids (reprocessing an artifact never double-counts, §11)."""
    seen, out = set(), []
    for s in signals:
        if s.signal_id in seen:
            continue
        seen.add(s.signal_id)
        out.append(s)
    return out


def wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float | None:
    """Optional lightweight Wilson lower bound for a proportion (§20). None if n == 0."""
    if n <= 0:
        return None
    phat = successes / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def aggregate(signals: list[FeedbackSignal]) -> Aggregates:
    agg = Aggregates(total_signals=len(signals))
    fb: dict = defaultdict(lambda: {"events": 0, "runs": set(), "helpful": 0, "not_helpful": 0})
    for s in signals:
        if s.signal_type == SignalType.USER_FEEDBACK and s.operation:
            b = fb[s.operation]
            b["events"] += 1
            if s.run_id_hash:
                b["runs"].add(s.run_id_hash)
            if s.rating == "helpful":
                b["helpful"] += 1
            elif s.rating == "not_helpful":
                b["not_helpful"] += 1
        elif s.metric_name and s.metric_value is not None:
            # Last-writer wins per (metric, dataset_hash) — provenance retained (§25).
            agg.metrics[s.metric_name] = {
                "value": s.metric_value, "dataset_hash": s.metric_dataset_hash,
                "version": s.metric_version, "source": s.source}
        elif s.error_category:
            agg.error_counts[s.error_category] = agg.error_counts.get(s.error_category, 0) + 1
        elif s.outcome == "known_gap":
            agg.gap_count += 1
    agg.feedback_by_operation = {
        op: {"events": b["events"], "runs": len(b["runs"]) or b["events"],
             "helpful": b["helpful"], "not_helpful": b["not_helpful"]}
        for op, b in fb.items()}
    return agg


def _confidence(unique: int, signal_kinds: int) -> Confidence:
    """Confidence from sample size + independent signal kinds — never fabricated (§19)."""
    if unique >= 8 or (unique >= 5 and signal_kinds >= 2):
        return Confidence.HIGH
    if unique >= 3:
        return Confidence.MODERATE
    return Confidence.LOW


def detect_findings(signals: list[FeedbackSignal], config: AnalysisConfig | None = None,
                    *, baselines: dict | None = None) -> list[FeedbackFinding]:
    config = config or AnalysisConfig()
    baselines = baselines or {}
    agg = aggregate(signals)
    findings: list[FeedbackFinding] = []
    fid = 0

    def _new_id() -> str:
        nonlocal fid
        fid += 1
        return f"F{fid:03d}"

    # --- user-feedback patterns (per operation) ---------------------------------------
    for op, b in sorted(agg.feedback_by_operation.items()):
        unique = b["runs"]                     # count unique runs, not raw events (§68)
        rated = b["helpful"] + b["not_helpful"]
        if rated == 0:
            continue
        neg_rate = b["not_helpful"] / rated
        pos_rate = b["helpful"] / rated
        # Positive finding (§22).
        if pos_rate >= config.positive_rate_threshold and unique >= config.min_support_observation:
            findings.append(FeedbackFinding(
                finding_id=_new_id(),
                title=f"Candidates consistently rate '{op}' helpful",
                category=FindingCategory.UX_SIGNAL, signal_type=SignalType.USER_FEEDBACK,
                description=f"{b['helpful']}/{rated} ratings for {op} are helpful.",
                affected_operation=op, support_count=b["helpful"], sample_size=rated,
                rate=round(pos_rate, 4), confidence=_confidence(unique, 1),
                severity=Severity.INFO, status=FindingStatus.POSITIVE, positive=True,
                limitations=["Ratings are self-selected; not a controlled measurement."]))
        # Negative pattern.
        if neg_rate >= config.negative_rate_threshold:
            support = b["not_helpful"]
            status = (FindingStatus.RECOMMENDATION_ELIGIBLE if support >= config.min_support_recommendation
                      else FindingStatus.PATTERN if support >= config.min_support_observation
                      else FindingStatus.OBSERVATION_ONLY)
            findings.append(FeedbackFinding(
                finding_id=_new_id(),
                title=f"Elevated not-helpful rate for '{op}'",
                category=FindingCategory.QUALITY, signal_type=SignalType.USER_FEEDBACK,
                description=(f"{support}/{rated} ratings for {op} are not helpful "
                             f"({round(neg_rate*100)}%); {unique} unique run(s)."),
                affected_operation=op, support_count=support, sample_size=rated,
                rate=round(neg_rate, 4), confidence=_confidence(unique, 1),
                severity=(Severity.MEDIUM if support >= config.min_support_recommendation else Severity.LOW),
                status=status,
                limitations=([] if support >= config.min_support_observation
                             else ["Below minimum support — observation only, not a pattern."])))

    # --- metric findings (safety escalation + positive + drift) -----------------------
    for name, m in sorted(agg.metrics.items()):
        val = m["value"]
        if name in _SAFETY_UNIT_METRICS:
            cat = _SAFETY_UNIT_METRICS[name]
            if val < 1.0:
                findings.append(FeedbackFinding(
                    finding_id=_new_id(),
                    title=f"Safety metric below target: {name} = {val}",
                    category=cat, signal_type=SignalType(_sig_type_for(m["source"])),
                    description=f"{name} is {val} (< 1.0). Safety metrics must hold at 1.0.",
                    support_count=1, sample_size=1, rate=val,
                    confidence=Confidence.MODERATE, severity=Severity.CRITICAL,
                    status=FindingStatus.RECOMMENDATION_ELIGIBLE,
                    evidence_refs=[f"{m['source']}:{name}"],
                    limitations=["Severity is HIGH by policy for safety; confidence reflects "
                                 "a single evaluation artifact."]))
            else:
                findings.append(FeedbackFinding(
                    finding_id=_new_id(),
                    title=f"Safety metric holding: {name} = {val}",
                    category=cat, signal_type=SignalType(_sig_type_for(m["source"])),
                    description=f"{name} remains at {val} (target 1.0).",
                    support_count=1, sample_size=1, rate=val,
                    confidence=Confidence.MODERATE, severity=Severity.INFO,
                    status=FindingStatus.POSITIVE, positive=True,
                    evidence_refs=[f"{m['source']}:{name}"]))
        # Drift vs a COMPATIBLE baseline (same dataset hash) only (§24/§63).
        base = baselines.get(name)
        if base and base.get("dataset_hash") and base["dataset_hash"] == m["dataset_hash"]:
            delta = round(val - base["value"], 4)
            if delta < -0.02:
                findings.append(FeedbackFinding(
                    finding_id=_new_id(),
                    title=f"Regression in {name}: {base['value']} → {val}",
                    category=FindingCategory.QUALITY,
                    signal_type=SignalType(_sig_type_for(m["source"])),
                    description=f"{name} fell by {abs(delta)} on the same dataset "
                                f"({m['dataset_hash']}).",
                    support_count=1, sample_size=1, rate=val, baseline_rate=base["value"],
                    change_vs_baseline=delta, confidence=Confidence.MODERATE,
                    severity=Severity.MEDIUM, status=FindingStatus.RECOMMENDATION_ELIGIBLE,
                    evidence_refs=[f"{m['source']}:{name}"]))

    # --- knowledge gaps ---------------------------------------------------------------
    if agg.gap_count:
        findings.append(FeedbackFinding(
            finding_id=_new_id(),
            title=f"{agg.gap_count} documented knowledge/coverage gap(s)",
            category=FindingCategory.KNOWLEDGE_GAP, signal_type=SignalType.KNOWLEDGE_COVERAGE,
            description="Coverage audit lists remaining gaps (e.g. DE occupation salary, "
                        "credentials, emerging roles).",
            support_count=agg.gap_count, sample_size=agg.gap_count,
            confidence=Confidence.MODERATE, severity=Severity.LOW,
            status=(FindingStatus.RECOMMENDATION_ELIGIBLE if agg.gap_count >= config.min_support_observation
                    else FindingStatus.OBSERVATION_ONLY),
            affected_domain="knowledge"))

    # --- error/reliability ------------------------------------------------------------
    for cat, count in sorted(agg.error_counts.items()):
        status = (FindingStatus.RECOMMENDATION_ELIGIBLE if count >= config.min_support_recommendation
                  else FindingStatus.PATTERN if count >= config.min_support_observation
                  else FindingStatus.OBSERVATION_ONLY)
        findings.append(FeedbackFinding(
            finding_id=_new_id(),
            title=f"Recurring '{cat}' errors",
            category=(FindingCategory.PROVIDER_FAILURE if "provider" in cat else FindingCategory.RELIABILITY),
            signal_type=SignalType.ERROR_CATEGORY,
            description=f"{count} occurrences of sanitized error category '{cat}'.",
            support_count=count, sample_size=count, confidence=_confidence(count, 1),
            severity=(Severity.MEDIUM if count >= config.min_support_recommendation else Severity.LOW),
            status=status,
            limitations=([] if count >= config.min_support_observation
                         else ["Below minimum support — observation only."])))
    return findings


def _sig_type_for(source: str) -> str:
    if "retrieval" in source:
        return "retrieval_evaluation"
    if "ragas" in source:
        return "ragas_evaluation"
    if "external" in source:
        return "external_research_evaluation"
    return "observability_aggregate"
