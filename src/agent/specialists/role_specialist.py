"""Role & Opportunity specialist — bounded structured role analysis (Capstone P5).

Turns a job description / prior job analysis / role name into a bounded, structured
:class:`RoleBrief` (key competencies, interview themes, priorities). It is a THIN
orchestration over the existing governed capabilities — it never opens a raw model
path of its own:
- when structured ``requirements`` already exist (Mo ran AnalyzeJobDescription), it
  synthesises the brief deterministically from them;
- else, when a job description is present and a career service is available, it reuses
  the existing GOVERNED, injection-guarded, usage-captured JD-analysis operation
  (``career_service.analyze_job_description``) — the same one Mo's tool uses;
- else it degrades to a role-name-only brief, or an explicit "insufficient" brief.

It has no side effects and produces no candidate-facing prose (Mo owns the voice); it
returns structured advice for Mo to synthesise.
"""

from __future__ import annotations

from src.agent.specialists.schemas import RoleAnalysisInput, RoleBrief

__all__ = ["run_role_specialist"]

_MAX_LIST = 12


def run_role_specialist(request: RoleAnalysisInput, *, career_service=None) -> RoleBrief:
    """Build a bounded RoleBrief. Never raises — any failure degrades to a safe brief."""
    requirements = request.requirements
    source = "requirements"

    if not requirements:
        jd = (request.job_description or "").strip()
        if jd and career_service is not None:
            requirements = _analyze_jd(career_service, jd)
            source = "job_analysis" if requirements else None
        if not requirements:
            role = (request.target_role or "").strip()
            if role:
                return RoleBrief(
                    role_title=role[:200], confidence="low", source="role_only",
                    notes=["Share a job description for a fuller, evidence-linked brief."],
                )
            return RoleBrief(
                confidence="low", source="insufficient",
                notes=["Provide a job description or a target role to analyse."],
            )

    return _brief_from_requirements(requirements, source or "requirements",
                                    fallback_role=request.target_role)


def _analyze_jd(career_service, jd: str) -> dict | None:
    """Reuse the governed JD-analysis operation. Returns RoleRequirements dump or None."""
    try:
        call = career_service.analyze_job_description(jd)
    except Exception:  # noqa: BLE001 - governed op unavailable → degrade, never crash
        return None
    if not getattr(call, "ok", False) or call.value is None:
        return None
    try:
        return call.value.model_dump()
    except Exception:  # noqa: BLE001
        return None


def _brief_from_requirements(req: dict, source: str, *, fallback_role: str | None) -> RoleBrief:
    role_title = (req.get("role_title") or (fallback_role or "")).strip()
    seniority = (req.get("seniority") or None)

    required = _clean(req.get("required_skills"))
    preferred = _clean(req.get("preferred_skills"))
    technologies = _clean(req.get("technologies"))
    responsibilities = _clean(req.get("key_responsibilities"))
    leadership = _clean(req.get("leadership_expectations"))
    stakeholder = _clean(req.get("stakeholder_expectations"))
    stated_themes = _clean(req.get("likely_interview_themes"))

    # Key competencies: required skills first, then a few technologies (deduped).
    key_competencies = _dedupe(required + technologies)[:_MAX_LIST]
    # Interview themes: the JD's stated themes, else derived from responsibilities +
    # leadership/stakeholder expectations. Never fabricated beyond what the JD stated.
    interview_themes = _dedupe(
        stated_themes + responsibilities + leadership + stakeholder
    )[:_MAX_LIST]
    # Priorities: required skills the candidate will most likely be probed on.
    priorities = _dedupe(required + responsibilities)[:_MAX_LIST]

    have = sum(bool(x) for x in (key_competencies, interview_themes, priorities))
    confidence = "high" if have >= 3 else ("medium" if have == 2 else "low")
    notes = []
    if preferred:
        notes.append("Preferred (nice-to-have) skills present: " + ", ".join(preferred[:5]))

    return RoleBrief(
        role_title=role_title[:200],
        seniority=(seniority[:80] if isinstance(seniority, str) else None),
        key_competencies=key_competencies,
        interview_themes=interview_themes,
        priorities=priorities,
        notes=notes[:10],
        confidence=confidence,
        source=source,
    )


def _clean(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if v and str(v).strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out
