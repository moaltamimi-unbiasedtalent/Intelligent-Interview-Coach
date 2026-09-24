"""Bounded interview-report export (Capstone P4 / bounded A9, §23/§24).

Serialises an OWNED, already-stored interview report to Markdown or versioned JSON. It
NEVER re-runs the LLM, invents fields, or exposes internal state (system prompts,
chain-of-thought, checkpoint payloads, provider secrets). Ownership is enforced by the
caller (the repository read is user-scoped); a foreign/unknown id yields None.
"""

from __future__ import annotations

from typing import Any

__all__ = ["EXPORT_SCHEMA_VERSION", "build_json_export", "build_markdown_export"]

EXPORT_SCHEMA_VERSION = 1


def _report_body(detail: dict) -> dict[str, Any]:
    report = (detail.get("report") or {}).get("report") or {}
    return report if isinstance(report, dict) else {}


def build_json_export(detail: dict) -> dict:
    """A machine-readable, versioned projection of the stored report (no internal data)."""
    config = detail.get("configuration") or {}
    body = _report_body(detail)
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "report_id": detail.get("id"),
        "created_at": detail.get("created_at"),
        "ended_at": detail.get("ended_at"),
        "target_role": config.get("target_role"),
        "interview_type": config.get("interview_type") or detail.get("mode"),
        "overall_score": body.get("overall_score") or body.get("readiness_score"),
        "summary": body.get("summary"),
        "strengths": body.get("strengths") or [],
        "focus_areas": body.get("focus_areas") or body.get("priorities") or [],
        "questions": [
            {
                "position": q.get("position"),
                "question": q.get("canonical_question"),
                "question_type": q.get("question_type"),
                "evaluation_summary": (q.get("answer") or {}).get("evaluation", {}).get("summary")
                if isinstance((q.get("answer") or {}).get("evaluation"), dict) else None,
            }
            for q in (detail.get("questions") or [])
        ],
    }


def build_markdown_export(detail: dict) -> str:
    data = build_json_export(detail)
    lines: list[str] = []
    lines.append(f"# Interview report — {data.get('target_role') or 'Practice interview'}")
    lines.append("")
    if data.get("created_at"):
        lines.append(f"- **Date:** {data['created_at']}")
    if data.get("interview_type"):
        lines.append(f"- **Type:** {data['interview_type']}")
    if data.get("overall_score") is not None:
        lines.append(f"- **Overall score:** {data['overall_score']}")
    lines.append("")
    if data.get("summary"):
        lines.append("## Summary")
        lines.append(str(data["summary"]))
        lines.append("")
    if data.get("strengths"):
        lines.append("## Strengths")
        for s in data["strengths"]:
            lines.append(f"- {s}")
        lines.append("")
    if data.get("focus_areas"):
        lines.append("## Focus areas")
        for f in data["focus_areas"]:
            lines.append(f"- {f}")
        lines.append("")
    if data.get("questions"):
        lines.append("## Questions")
        for q in data["questions"]:
            lines.append(f"### {q.get('position', '')}. {q.get('question', '')}".rstrip())
            if q.get("evaluation_summary"):
                lines.append(str(q["evaluation_summary"]))
            lines.append("")
    return "\n".join(lines).strip() + "\n"
