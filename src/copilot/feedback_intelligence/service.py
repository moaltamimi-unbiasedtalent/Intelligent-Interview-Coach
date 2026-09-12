"""Offline Feedback Intelligence orchestrator (Phase 7G, §46/§47/§53).

A bounded, deterministic pipeline (NOT the candidate LangGraph): collect safe signals → dedupe →
snapshot (with provenance) → detect findings → build recommendations + experiments → persist to
the analysis-output root → STOP for human review. No network, no paid call by default. Optional
LLM synthesis is injectable and can ONLY add narrative text — it can never alter a support count,
metric, severity, confidence, priority or guardrail (§47).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.copilot.feedback_intelligence.analysis import (
    AnalysisConfig, deduplicate, detect_findings)
from src.copilot.feedback_intelligence.guards import safe_output_path
from src.copilot.feedback_intelligence.models import (
    ANALYSIS_VERSION, FeedbackSnapshot)
from src.copilot.feedback_intelligence.recommend import build_experiments, build_recommendations
from src.copilot.feedback_intelligence.signals import FeedbackSignalAdapter

DEFAULT_OUTPUT_ROOT = "evaluations/feedback_intelligence/runs"


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL,  # noqa: S603,S607
                                       timeout=5).decode().strip()
    except Exception:  # noqa: BLE001
        return None


@dataclass
class FeedbackRunResult:
    snapshot: FeedbackSnapshot
    findings: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    experiments: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    review_status: str = "awaiting_review"
    output_directory: str | None = None
    synthesis_used: bool = False


def collect_signals(adapters: list[FeedbackSignalAdapter]):
    signals, warnings, sources, hashes = [], [], [], {}
    for a in adapters:
        try:
            sigs, warns = a.signals()
        except Exception as exc:  # noqa: BLE001 - an adapter never sinks the whole run (§56/§57)
            warnings.append(f"{getattr(a, 'name', 'adapter')}: failed ({type(exc).__name__})")
            continue
        warnings.extend(warns)
        if sigs:
            sources.append(a.name)
            signals.extend(sigs)
            blob = json.dumps([s.model_dump(mode="json") for s in sigs], sort_keys=True)
            hashes[a.name] = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return signals, warnings, sources, hashes


def run(adapters: list[FeedbackSignalAdapter], *, config: AnalysisConfig | None = None,
        baselines: dict | None = None, output_dir: str | None = None, persist: bool = True,
        synthesize_fn: Callable[[dict], str] | None = None) -> FeedbackRunResult:
    """Run the deterministic pipeline; optionally add narrative via an injected synthesise fn."""
    config = config or AnalysisConfig()
    raw, warnings, sources, hashes = collect_signals(adapters)
    signals = deduplicate(raw)
    now = datetime.now(timezone.utc)
    sha = _git("rev-parse", "HEAD")
    porcelain = _git("status", "--porcelain")
    snapshot = FeedbackSnapshot(
        snapshot_id=f"snap-{now.strftime('%Y%m%d_%H%M%S')}", created_at=now,
        signal_count=len(signals), signal_sources=sorted(set(sources)),
        git_sha=sha, git_dirty=(None if porcelain is None else porcelain != ""),
        input_hashes=hashes, analysis_version=ANALYSIS_VERSION,
        config={"min_support_observation": config.min_support_observation,
                "min_support_recommendation": config.min_support_recommendation})

    findings = detect_findings(signals, config, baselines=baselines)
    recommendations = build_recommendations(findings)
    experiments = build_experiments(recommendations)

    result = FeedbackRunResult(
        snapshot=snapshot, findings=findings, recommendations=recommendations,
        experiments=experiments, warnings=warnings, review_status="awaiting_review")

    # Optional LLM synthesis (§41/§47): narrative ONLY, from safe aggregates. It cannot change
    # any deterministic field — we snapshot the numbers before and re-assert them after.
    if synthesize_fn is not None:
        before = _numbers_fingerprint(result)
        try:
            payload = safe_synthesis_payload(result)
            narrative = synthesize_fn(payload)
            result.synthesis_used = True
            result.warnings.append("LLM synthesis added narrative only (metrics unchanged).")
            _narrative_holder[snapshot.snapshot_id] = str(narrative)[:4000]
        except Exception as exc:  # noqa: BLE001 - synthesis failure never breaks the run
            result.warnings.append(f"LLM synthesis skipped ({type(exc).__name__}).")
        assert _numbers_fingerprint(result) == before, "synthesis must not alter deterministic data"

    if persist:
        result.output_directory = _persist(result, output_dir)
    return result


_narrative_holder: dict[str, str] = {}


def _numbers_fingerprint(result: FeedbackRunResult) -> str:
    """A hash over the deterministic fields that LLM synthesis must never change (§47)."""
    core = {
        "findings": [(f.finding_id, f.support_count, f.sample_size, f.rate, f.severity.value,
                      f.confidence.value, f.status.value) for f in result.findings],
        "recommendations": [(r.recommendation_id, r.priority, r.severity.value, r.confidence.value,
                             r.support_count, sorted(r.finding_ids)) for r in result.recommendations],
        "experiments": [(e.experiment_id, e.target_metric, tuple(e.guardrail_metrics))
                        for e in result.experiments],
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


def safe_synthesis_payload(result: FeedbackRunResult) -> dict:
    """The ONLY data an LLM synthesiser may receive: safe IDs/counts/labels — never raw content."""
    return {
        "finding_summaries": [
            {"id": f.finding_id, "title": f.title, "category": f.category.value,
             "severity": f.severity.value, "confidence": f.confidence.value,
             "support_count": f.support_count, "sample_size": f.sample_size,
             "positive": f.positive} for f in result.findings],
        "recommendation_summaries": [
            {"id": r.recommendation_id, "title": r.title, "change_area": r.change_area.value,
             "priority": r.priority} for r in result.recommendations],
        "signal_count": result.snapshot.signal_count,
        "sources": result.snapshot.signal_sources,
    }


def _persist(result: FeedbackRunResult, output_dir: str | None) -> str:
    base = Path(output_dir) if output_dir else Path(DEFAULT_OUTPUT_ROOT) / result.snapshot.snapshot_id
    out = safe_output_path(base)  # enforce the write boundary (§38)
    out.mkdir(parents=True, exist_ok=True)
    (out / "snapshot.json").write_text(result.snapshot.model_dump_json(indent=2), encoding="utf-8")
    (out / "findings.json").write_text(
        json.dumps([f.model_dump(mode="json") for f in result.findings], indent=2), encoding="utf-8")
    (out / "recommendations.json").write_text(
        json.dumps([r.model_dump(mode="json") for r in result.recommendations], indent=2), encoding="utf-8")
    (out / "experiments.json").write_text(
        json.dumps([e.model_dump(mode="json") for e in result.experiments], indent=2), encoding="utf-8")
    (out / "run_metadata.json").write_text(json.dumps({
        "analysis_version": ANALYSIS_VERSION, "git_sha": result.snapshot.git_sha,
        "git_dirty": result.snapshot.git_dirty, "generated_at": result.snapshot.created_at.isoformat(),
        "signal_count": result.snapshot.signal_count, "sources": result.snapshot.signal_sources,
        "finding_count": len(result.findings), "recommendation_count": len(result.recommendations),
        "experiment_count": len(result.experiments), "review_status": result.review_status,
        "synthesis_used": result.synthesis_used, "warnings": result.warnings,
        "paid_calls": 0}, indent=2), encoding="utf-8")
    (out / "feedback_intelligence_report.md").write_text(_report_md(result), encoding="utf-8")
    return str(out)


def _report_md(result: FeedbackRunResult) -> str:
    """A human-readable per-run report (§52). Safe metadata only — no candidate content."""
    s = result.snapshot
    pos = [f for f in result.findings if f.positive]
    safety = [f for f in result.findings if f.category.value in ("safety", "citation", "geography")
              and not f.positive]
    pos_lines = [f"- {f.title}" for f in pos] or ["- (none)"]
    safety_lines = [f"- [{f.severity.value}] {f.title}" for f in safety] or ["- (none below target)"]
    lines = [
        "# Feedback Intelligence Report", "",
        f"- generated_at: {s.created_at.isoformat()}  ·  git_sha: {s.git_sha}  ·  "
        f"git_dirty: {s.git_dirty}  ·  analysis: {s.analysis_version}",
        f"- signals: {s.signal_count}  ·  sources: {', '.join(s.signal_sources) or 'none'}",
        f"- review status: **{result.review_status}** (nothing is changed automatically)", "",
        "## Positive signals", *pos_lines, "",
        "## Safety findings", *safety_lines, "",
        "## Top recommendations (human review required — approval does NOT execute)",
    ]
    for r in result.recommendations[:8]:
        lines.append(f"- **P{r.priority} [{r.change_area.value}]** {r.title} — "
                     f"support {r.support_count}, {r.severity.value}/{r.confidence.value}")
    lines += ["", "## Proposed experiments (with mandatory guardrails)"]
    for e in result.experiments[:8]:
        lines.append(f"- {e.experiment_id}: {e.hypothesis} (guardrails: {len(e.guardrail_metrics)})")
    lines += ["", "## Known limitations",
              "- Ratings/metrics are structured signals, not controlled experiments.",
              "- No candidate content is analysed; free-text feedback is excluded.",
              "- Recommendations are advisory; an engineer implements approved items separately."]
    if result.warnings:
        lines += ["", "## Warnings", *[f"- {w}" for w in result.warnings]]
    return "\n".join(lines) + "\n"
