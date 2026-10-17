"""Opportunity Preparation Pack: domain model, deterministic assembly and output validation (W12.4D-P5-A).

AI-assisted INTERVIEW PREPARATION for ONE opportunity. It is not a recruitment service, a hiring decision, a verified assessment, a salary service or human
coaching, and it never claims to be.

* **Default disabled.** ``PREPARATION_PACK_GENERATION_ENABLED = False`` is a code constant (like the billing and other rollout gates). While False nobody can
  start a generation and no provider is called. READING, downloading and deleting a stored Pack is never gated by plan or by this constant: a Pack is an
  independent candidate-owned artifact and stays accessible after a downgrade.
* **One entitlement authority.** With the gate on, generation needs an ACTIVE Premium-plan subscription through ``plan_state.resolve_plan_state`` over the
  existing ``EntitlementService``. ``premium_preview``, client labels, expired, unknown and unreadable state are ``not_entitled``.
* **Every item carries an evidence category** (candidate-provided, opportunity-provided, verified-external, knowledge-base, ai-guidance, unavailable). Only
  items with a resolvable, retained source reference may be ``verified_external``; AI guidance is never presented as a verified fact and carries no citation.
* **Mostly deterministic.** Requirements, company facts, alignment, gaps and examples are assembled by auditable rules from the candidate's OWN retained
  evidence (accepted document claims and Story Bank entries), the opportunity record, the candidate-supplied job description and the existing Company
  Intelligence report. Only the interview-question and roadmap wording (category ``ai_guidance``) uses a model, through the existing structured-output
  path, with schema validation and grounding checks. Invalid or ungrounded output fails the generation; nothing is repaired by invention.
* **No interview data.** A Pack never reads or embeds interviews, feedback, reports or analytics, so it cannot bypass a history entitlement.
* **No numbers about people or pay.** No matching score, no probability, no salary, percentile, currency or tax figure (the compensation engine is P10C and
  is not part of this wave).
"""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field

# A code constant: nothing but a reviewed, owner-approved release can enable Pack generation. Tests flip it on an isolated module attribute.
PREPARATION_PACK_GENERATION_ENABLED = False
SCHEMA_VERSION = "pack-1"
STALE_GENERATION_SECONDS = 15 * 60                  # a ``generating`` row older than this was interrupted and is marked failed
MAX_JD_CHARS = 8000                                 # context budgets: nothing unbounded ever reaches a model
MAX_REQUIREMENTS = 20
MAX_EVIDENCE_UNITS = 60
MAX_QUESTIONS = 12
MAX_ROADMAP_STEPS = 12
_TEST_ENVS = ("development", "dev", "local", "test", "testing")

__all__ = ["PREPARATION_PACK_GENERATION_ENABLED", "SCHEMA_VERSION", "Category", "SectionStatus", "PackAccessPolicy", "PackInputs", "PackGuidance", "GuidanceContext",
           "GuidanceGenerator", "PackGenerationError", "PackGenerationUnavailable", "assemble", "validate_guidance", "render_markdown", "extract_requirements", "SECTION_IDS"]


class Category(str, Enum):
    candidate_provided = "candidate_provided"       # A
    opportunity_provided = "opportunity_provided"   # B
    verified_external = "verified_external"         # C (a retained, resolvable source)
    knowledge_base = "knowledge_base"               # D
    ai_guidance = "ai_guidance"                     # E (method: deterministic or model; NEVER a verified fact)
    unavailable = "unavailable"                     # F


class SectionStatus(str, Enum):
    available = "available"
    partial = "partial"
    insufficient_evidence = "insufficient_evidence"
    not_applicable = "not_applicable"
    failed = "failed"


SECTION_IDS = ("overview", "company", "requirements", "alignment", "gaps", "questions", "examples", "roadmap", "sources")


class PackSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    url: str | None = None
    category: Category
    provider: str | None = None
    retrieved_at: str | None = None
    effective_date: str | None = None
    self_reported: bool = False


class PackItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    text: str
    category: Category
    source_ids: list[str] = Field(default_factory=list)
    ref_ids: list[str] = Field(default_factory=list)
    meta: dict[str, str] = Field(default_factory=dict)


class PackSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    status: SectionStatus
    items: list[PackItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PreparationPackContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION
    opportunity: dict[str, Any]
    inputs: dict[str, bool]
    sections: list[PackSection]
    sources: list[PackSource] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PackGenerationUnavailable(Exception):
    """Generation is not available for this request (the rollout gate is off or the caller is not entitled). Carries only a bounded reason."""

    def __init__(self, reason: str) -> None:
        super().__init__("preparation_pack_generation_unavailable")
        self.reason = reason


class PackGenerationError(Exception):
    """A bounded, content-free failure. ``category`` is a short code; nothing from the model output or the candidate's data is carried."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


# ------------------------------------------------------------------------------------------------------------------------ entitlement
class PackAccessPolicy:
    """Stateless per request. ``decide`` -> ``feature_disabled`` | ``not_entitled`` | ``allowed``. Applies to GENERATION only."""

    def __init__(self, entitlements, *, override: Callable[[int], str] | None = None) -> None:
        if override is not None and (os.environ.get("API_ENV") or "development").strip().lower() not in _TEST_ENVS:
            raise ValueError("A synthetic Pack entitlement decision cannot be used outside development and test.")
        self._entitlements, self._override = entitlements, override

    def decide(self, user_id: int) -> str:
        if not PREPARATION_PACK_GENERATION_ENABLED:
            return "feature_disabled"
        if self._override is not None:
            return "allowed" if self._override(int(user_id)) == "premium" else "not_entitled"
        from src.application.plan_state import PREMIUM, resolve_plan_state

        return "allowed" if resolve_plan_state(self._entitlements, user_id) == PREMIUM else "not_entitled"


# ------------------------------------------------------------------------------------------------------------------------ inputs
class PackInputs(BaseModel):
    """Everything the Pack may use. Every member is the CALLER's own, already owner-scoped data; interviews are deliberately absent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    opportunity: dict[str, Any]
    jd_text: str | None = None
    company: Any | None = None                       # CompanyIntelligenceReport (existing service) or None
    claims: list[dict[str, Any]] = Field(default_factory=list)    # accepted/edited document claims (non-rejected)
    stories: list[dict[str, Any]] = Field(default_factory=list)
    kb: list[dict[str, Any]] = Field(default_factory=list)        # optional governed knowledge evidence: {id, title, text, url?}


_STOP = frozenset("""about above across after again also among and any are around because been before being between both but can could did does doing done each
either else ever every for from had has have having her here him his how into its itself just may might more most much must not off once only other our out over own
same she should some such than that the their them then there these they this those through too under until upon very was were what when where which while who whom why
will with within without would you your able etc per via""".split())
_COMPETENCIES = {
    "leadership": ("lead", "leading", "leadership", "manage", "mentor", "coach", "supervise", "führung", "leiten"),
    "communication": ("communicat", "present", "stakeholder", "negotiat", "writing", "kommunikation"),
    "problem solving": ("problem", "analys", "solve", "troubleshoot", "diagnos", "lösung"),
    "teamwork": ("team", "collaborat", "cross-functional", "partner", "zusammenarbeit"),
    "project management": ("project", "deliver", "plan", "schedule", "roadmap", "projekt"),
    "customer focus": ("customer", "client", "patient", "service", "kunde"),
    "technical skills": ("technical", "software", "system", "engineer", "code", "data", "technolog"),
    "data analysis": ("data", "metric", "kpi", "report", "forecast", "daten"),
    "regulation and compliance": ("regulat", "complian", "audit", "safety", "standard", "policy", "vorschrift"),
}
_REQ_CUE = re.compile(r"\b(must|required|requirement|experience|proficien|knowledge|ability|able to|skills?|responsib|degree|years?|fluent|certif|qualif|familiar)\b", re.I)
_BULLET = re.compile(r"^\s*(?:[-*•–·]|\d{1,2}[.)])\s+")
_SENIORITY = re.compile(r"\b(intern|graduate|junior|entry[- ]level|mid[- ]level|senior|lead|principal|staff|head of|director|vp|executive)\b", re.I)
_WORK_MODEL = re.compile(r"\b(remote|hybrid|on[- ]?site|in[- ]office)\b", re.I)
_URL = re.compile(r"https?://|www\.", re.I)
_MONEY = re.compile(r"(?:[€$£¥]\s?\d|\d\s?(?:[kK]\b|eur\b|usd\b|gbp\b|chf\b|€|\$|£)|\b(?:salary|salaries|compensation|gehalt|salaire|salario|stipendio|salário|salaris|зарплат|bonus|equity|percentile|median pay)\b)", re.I)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿа-я0-9+#.]{4,}", (text or "").lower()) if w not in _STOP}


def _tags(text: str) -> list[str]:
    low = (text or "").lower()
    return [c for c, ks in _COMPETENCIES.items() if any(k in low for k in ks)]


def extract_requirements(jd_text: str | None) -> list[dict[str, Any]]:
    """Deterministic requirement statements from the candidate-supplied job description (category: opportunity-provided). Nothing is added that the text
    does not contain; the competency tags are detected from its wording and are labelled as such."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in (jd_text or "")[:MAX_JD_CHARS].splitlines():
        line = _BULLET.sub("", raw).strip(" \t-*•–·")
        bullet = bool(_BULLET.match(raw))
        if not (15 <= len(line) <= 300) or not (bullet or _REQ_CUE.search(line)):
            continue
        key = re.sub(r"\W+", " ", line.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": f"R{len(out) + 1}", "text": line, "competencies": _tags(line)})
        if len(out) >= MAX_REQUIREMENTS:
            break
    return out


# ------------------------------------------------------------------------------------------------------------------------ deterministic assembly
def _units(inputs: PackInputs) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for c in inputs.claims[:MAX_EVIDENCE_UNITS]:
        text = (c.get("display_text") or c.get("edited_text") or c.get("text") or "").strip()
        if text and c.get("review_state") != "rejected":
            units.append({"id": f"C{c['id']}", "kind": "claim", "text": text, "tags": [], "tokens": _tokens(text), "label": c.get("claim_type") or "claim"})
    for st in inputs.stories[:MAX_EVIDENCE_UNITS]:
        parts = [st.get("title"), st.get("situation"), st.get("task"), st.get("action"), st.get("result")]
        text = " ".join(p for p in parts if p).strip()
        tags = [str(t).lower() for t in (st.get("competencies") or [])]
        if text:
            units.append({"id": f"S{st['id']}", "kind": "story", "text": text, "title": st.get("title") or "", "tags": tags, "tokens": _tokens(text),
                          "label": st.get("evidence_state") or "story"})
    return units[:MAX_EVIDENCE_UNITS]


def _align(requirements: list[dict[str, Any]], units: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for r in requirements:
        rt, rc = _tokens(r["text"]), {c.lower() for c in r["competencies"]}
        scored = []
        for u in units:
            shared = len(rt & u["tokens"])
            comp = bool(rc & {t.lower() for t in u["tags"]})
            if shared >= 2 or (comp and shared >= 1):
                scored.append((2, shared, u["id"]))
            elif shared == 1 or comp:
                scored.append((1, shared, u["id"]))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
        strong = [i for lvl, _, i in scored if lvl == 2][:3]
        weak = [i for lvl, _, i in scored if lvl == 1][:3]
        result[r["id"]] = {"status": "supported" if strong else ("needs_verification" if weak else "no_evidence"), "refs": strong or weak}
    return result


def _item(kind: str, text: str, category: Category, *, source_ids=(), ref_ids=(), **meta: str) -> PackItem:
    return PackItem(kind=kind, text=text[:600], category=category, source_ids=list(source_ids), ref_ids=list(ref_ids), meta={k: str(v)[:60] for k, v in meta.items()})


def assemble(inputs: PackInputs, guidance: "PackGuidance | None" = None, *, guidance_failed: bool = False) -> PreparationPackContent:
    """Build the structured Pack. ``guidance`` fills the question and roadmap sections (category ``ai_guidance``); without it those sections are
    ``insufficient_evidence`` (no model call was made) or ``failed`` (``guidance_failed``). Missing information is stated, never filled."""
    opp = inputs.opportunity
    requirements = extract_requirements(inputs.jd_text)
    units = _units(inputs)
    by_id = {u["id"]: u for u in units}
    align = _align(requirements, units)
    sources: list[PackSource] = []
    sections: dict[str, PackSection] = {}

    # --- A overview (candidate/opportunity-provided fields only; missing fields are listed, not guessed) ---
    ov: list[PackItem] = []
    missing: list[str] = []
    for field, kind in (("target_role", "role"), ("title", "title"), ("company_name", "employer"), ("company_location", "location"), ("company_country", "country")):
        v = (opp.get(field) or "").strip() if isinstance(opp.get(field), str) else None
        if v:
            ov.append(_item(kind, v, Category.opportunity_provided))
        elif field != "title":
            missing.append(kind)
    jd = inputs.jd_text or ""
    for rx, kind in ((_SENIORITY, "seniority_cue"), (_WORK_MODEL, "work_model_cue")):
        m = rx.search(jd)
        if m:
            ov.append(_item(kind, m.group(0), Category.opportunity_provided, source="job_description"))
    for kind in ("employment_type", "work_model") if not _WORK_MODEL.search(jd) else ("employment_type",):
        missing.append(kind)
    ov += [_item("missing", k, Category.unavailable) for k in dict.fromkeys(missing)]
    sections["overview"] = PackSection(id="overview", status=SectionStatus.available if len([i for i in ov if i.kind != "missing"]) >= 2 else SectionStatus.partial, items=ov,
                                       notes=[] if jd else ["no_job_description"])

    # --- B company context (existing Company Intelligence report; unsourced facts are dropped, never shown) ---
    co = inputs.company
    comp_items: list[PackItem] = []
    notes: list[str] = []
    status = SectionStatus.insufficient_evidence
    if co is not None:
        known = {s.id: s for s in getattr(co, "sources", [])}
        used: set[str] = set()
        dropped = 0
        for group, kind in ((co.business_market, "business_market"), (co.recent_developments, "recent_development"), (co.culture, "culture")):
            for cl in group:
                if getattr(cl.kind, "value", cl.kind) != "fact":
                    continue
                ids = [i for i in cl.source_ids if i in known]
                if not ids:
                    dropped += 1                                    # a "fact" without a retained source is not shown as verified
                    continue
                used.update(ids)
                comp_items.append(_item(kind, cl.text, Category.verified_external, source_ids=[f"W:{i}" for i in ids]))
        for i in sorted(used):
            s = known[i]
            sources.append(PackSource(id=f"W:{i}", title=s.title[:200], url=s.url, category=Category.verified_external, provider=s.provider,
                                      retrieved_at=s.retrieved_at, effective_date=s.effective_date, self_reported=bool(s.self_reported)))
        for cl in getattr(co, "role_relevance", [])[:5]:
            comp_items.append(_item("role_relevance_hint", cl.text, Category.ai_guidance, method="deterministic"))
        notes += ["unsourced_claims_dropped"] if dropped else []
        st = getattr(co.status, "value", co.status)
        notes.append(f"company_research_{st}")
        has_fact = any(i.category == Category.verified_external for i in comp_items)
        status = SectionStatus.available if (st == "ready" and has_fact) else (SectionStatus.partial if has_fact else SectionStatus.insufficient_evidence)
        for lim in getattr(co, "limitations", [])[:5]:
            comp_items.append(_item("limitation", lim, Category.unavailable))
    else:
        notes.append("company_research_not_run")
    if not comp_items:
        comp_items.append(_item("missing", "company_evidence", Category.unavailable))
    sections["company"] = PackSection(id="company", status=status, items=comp_items, notes=notes)

    # --- C requirements and competencies (the candidate-supplied JD is input about the opportunity, not verification of the employer) ---
    if requirements:
        req_items = [_item("requirement", r["text"], Category.opportunity_provided, ref_ids=[r["id"]], tags=",".join(r["competencies"])) for r in requirements]
        sections["requirements"] = PackSection(id="requirements", status=SectionStatus.available, items=req_items,
                                               notes=["competencies_detected_from_wording"] + (["requirements_truncated"] if len(requirements) >= MAX_REQUIREMENTS else []))
    else:
        sections["requirements"] = PackSection(id="requirements", status=SectionStatus.insufficient_evidence, items=[_item("missing", "requirements", Category.unavailable)],
                                               notes=["no_job_description" if not jd else "no_requirements_detected"])

    # --- D candidate evidence alignment (three honest states; no score, no probability) ---
    if requirements and units:
        al_items = []
        for r in requirements:
            a = align[r["id"]]
            al_items.append(_item("alignment", r["text"], Category.candidate_provided if a["refs"] else Category.unavailable, ref_ids=[r["id"]] + a["refs"], status=a["status"]))
        n_sup = sum(1 for r in requirements if align[r["id"]]["status"] == "supported")
        sections["alignment"] = PackSection(id="alignment", status=SectionStatus.available if n_sup else SectionStatus.partial, items=al_items,
                                            notes=["candidate_claims_not_verified", "alignment_is_not_an_employer_assessment"])
    else:
        sections["alignment"] = PackSection(id="alignment", status=SectionStatus.insufficient_evidence, items=[_item("missing", "candidate_evidence" if not units else "requirements", Category.unavailable)],
                                            notes=["no_candidate_evidence" if not units else "no_requirements_detected"])

    # --- E preparation gaps (never "skill gap": an absent upload is an evidence gap, not proof of a missing skill) ---
    gaps: list[PackItem] = []
    for r in requirements:
        a = align[r["id"]]
        if a["status"] == "no_evidence":
            gaps.append(_item("evidence_gap", r["text"], Category.ai_guidance, ref_ids=[r["id"]], method="deterministic"))
        elif a["status"] == "needs_verification":
            gaps.append(_item("evidence_gap", r["text"], Category.ai_guidance, ref_ids=[r["id"]] + a["refs"], method="deterministic", detail="needs_verification"))
    if not jd:
        gaps.append(_item("information_gap", "job_description", Category.ai_guidance, method="deterministic"))
    if not units:
        gaps.append(_item("information_gap", "candidate_evidence", Category.ai_guidance, method="deterministic"))
    if co is None or sections["company"].status == SectionStatus.insufficient_evidence:
        gaps.append(_item("preparation_gap", "company_research", Category.ai_guidance, method="deterministic"))
    sections["gaps"] = PackSection(id="gaps", status=SectionStatus.available if gaps else SectionStatus.not_applicable, items=gaps,
                                   notes=["absence_of_evidence_is_not_absence_of_skill"])

    # --- F interview questions and H roadmap (model guidance; ai_guidance; no sources) ---
    if guidance is not None:
        q_items = [_item("question", q.question, Category.ai_guidance, ref_ids=q.requirement_ids, method="model", question_type=q.kind,
                         evidence_to_prepare=q.evidence_to_prepare) for q in guidance.questions]
        for q, it in zip(guidance.questions, q_items):
            it.meta["follow_ups"] = " | ".join(f[:120] for f in q.follow_ups[:3])[:400]
        r_items = [_item("roadmap_step", s.text, Category.ai_guidance, ref_ids=s.requirement_ids + s.evidence_ids, method="model", action_type=s.action, order=str(i + 1))
                   for i, s in enumerate(guidance.roadmap)]
        sections["questions"] = PackSection(id="questions", status=SectionStatus.available if q_items else SectionStatus.insufficient_evidence, items=q_items,
                                            notes=["employer_questions_not_predicted"])
        sections["roadmap"] = PackSection(id="roadmap", status=SectionStatus.available if r_items else SectionStatus.insufficient_evidence, items=r_items,
                                          notes=["no_interview_date_assumed"])
    else:
        st = SectionStatus.failed if guidance_failed else SectionStatus.insufficient_evidence
        sections["questions"] = PackSection(id="questions", status=st, items=[_item("missing", "interview_questions", Category.unavailable)], notes=[])
        sections["roadmap"] = PackSection(id="roadmap", status=st, items=[_item("missing", "roadmap", Category.unavailable)], notes=[])

    # --- G achievement examples (the candidate's OWN words, verbatim; nothing is rewritten into a new achievement) ---
    ex: list[PackItem] = []
    shown: set[str] = set()
    for r in requirements:
        for ref in align[r["id"]]["refs"] if align[r["id"]]["status"] == "supported" else []:
            if ref in shown:
                continue
            shown.add(ref)
            u = by_id[ref]
            ex.append(_item("example", u["text"], Category.candidate_provided, ref_ids=[ref, r["id"]], evidence_kind=u["kind"], review=u["label"]))
    sections["examples"] = PackSection(id="examples", status=SectionStatus.available if ex else SectionStatus.insufficient_evidence,
                                       items=ex or [_item("missing", "supported_examples", Category.unavailable)], notes=["candidate_claims_not_verified"])

    # --- I sources, assumptions and limitations ---
    for k in inputs.kb[:10]:
        if k.get("id") and k.get("title"):
            sources.append(PackSource(id=f"K:{k['id']}", title=str(k["title"])[:200], url=k.get("url"), category=Category.knowledge_base, provider="governed_knowledge"))
    assumptions = ["candidate_provided_job_description_describes_the_opportunity_only", "candidate_claims_are_not_verified_by_ask4mo", "no_interview_date_assumed",
                   "no_geography_inferred_from_interface_language"]
    limitations = ["ai_guidance_is_not_a_verified_fact", "not_a_hiring_decision_or_guarantee", "not_human_coaching", "compensation_not_included_p10c",
                   "geographic_and_multilingual_knowledge_coverage_not_assumed_p10d"]
    if not inputs.kb:
        limitations.append("knowledge_base_evidence_not_connected")
    src_items = [_item("source", s.title, s.category, source_ids=[s.id]) for s in sources] or [_item("missing", "sources", Category.unavailable)]
    sections["sources"] = PackSection(id="sources", status=SectionStatus.available if sources else SectionStatus.partial, items=src_items)

    return PreparationPackContent(
        opportunity={k: opp.get(k) for k in ("id", "title", "target_role", "company_name", "company_location", "company_country", "status")},
        inputs={"job_description": bool(jd), "company_research": co is not None, "candidate_claims": bool(inputs.claims), "stories": bool(inputs.stories), "knowledge_base": bool(inputs.kb)},
        sections=[sections[i] for i in SECTION_IDS], sources=sources, assumptions=assumptions, limitations=limitations)


# ------------------------------------------------------------------------------------------------------------------------ guidance (model stage)
class GuidanceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_ids: list[str] = Field(max_length=5)
    kind: str = Field(description="One of: competency, behavioural, technical, leadership, role_specific.")
    question: str = Field(min_length=10, max_length=300)
    evidence_to_prepare: str = Field(min_length=3, max_length=300)
    follow_ups: list[str] = Field(max_length=3)


class GuidanceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(description="One of: review_requirements, prepare_example, practise_questions, study_company, rehearse_role, review_feedback, revise_example.")
    text: str = Field(min_length=10, max_length=300)
    requirement_ids: list[str] = Field(max_length=5)
    evidence_ids: list[str] = Field(max_length=5)


class PackGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: list[GuidanceQuestion] = Field(max_length=MAX_QUESTIONS)
    roadmap: list[GuidanceStep] = Field(max_length=MAX_ROADMAP_STEPS)


_Q_KINDS = frozenset({"competency", "behavioural", "technical", "leadership", "role_specific"})
_ACTIONS = frozenset({"review_requirements", "prepare_example", "practise_questions", "study_company", "rehearse_role", "review_feedback", "revise_example"})


class GuidanceContext(BaseModel):
    """The bounded, caller-owned context handed to the model stage. ``requirements`` and ``evidence`` are untrusted DATA."""

    role: str | None = None
    company: str | None = None
    requirements: list[dict[str, Any]] = Field(default_factory=list)     # {id, text, competencies, status}
    evidence: list[dict[str, Any]] = Field(default_factory=list)         # {id, label, tags}  (titles/labels only, never full text)
    gaps: list[str] = Field(default_factory=list)


class GuidanceGenerator(Protocol):
    def generate(self, context: GuidanceContext) -> PackGuidance: ...


def build_context(inputs: PackInputs) -> tuple[GuidanceContext, set[str], set[str]]:
    requirements = extract_requirements(inputs.jd_text)
    units = _units(inputs)
    align = _align(requirements, units)
    ctx = GuidanceContext(
        role=(inputs.opportunity.get("target_role") or inputs.opportunity.get("title")), company=inputs.opportunity.get("company_name"),
        requirements=[{"id": r["id"], "text": r["text"], "competencies": r["competencies"], "status": align[r["id"]]["status"]} for r in requirements],
        evidence=[{"id": u["id"], "label": (u.get("title") or u["label"])[:80], "tags": u["tags"][:5]} for u in units],
        gaps=[r["id"] for r in requirements if align[r["id"]]["status"] != "supported"])
    return ctx, {r["id"] for r in requirements}, {u["id"] for u in units}


def validate_guidance(raw: PackGuidance | dict | str, requirement_ids: set[str], evidence_ids: set[str]) -> PackGuidance:
    """Schema AND grounding validation. Raises ``PackGenerationError`` with a bounded category and NEVER carries or logs the output. No repair by invention."""
    try:
        if isinstance(raw, PackGuidance):
            g = raw
        else:
            data = json.loads(raw) if isinstance(raw, str) else raw
            g = PackGuidance.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        raise PackGenerationError("schema_invalid") from exc
    seen_q: set[str] = set()
    for q in g.questions:
        if q.kind not in _Q_KINDS or not set(q.requirement_ids) <= requirement_ids:
            raise PackGenerationError("ungrounded_output")
        key = re.sub(r"\W+", " ", q.question.lower()).strip()
        if key in seen_q:
            raise PackGenerationError("ungrounded_output")
        seen_q.add(key)
    for s in g.roadmap:
        if s.action not in _ACTIONS or not set(s.requirement_ids) <= requirement_ids or not set(s.evidence_ids) <= evidence_ids:
            raise PackGenerationError("ungrounded_output")
    blob = " ".join([q.question + " " + q.evidence_to_prepare + " " + " ".join(q.follow_ups) for q in g.questions] + [s.text for s in g.roadmap])
    if _MONEY.search(blob):
        raise PackGenerationError("unsupported_compensation_claim")
    if _URL.search(blob):
        raise PackGenerationError("unsupported_citation")
    if not g.questions and not g.roadmap:
        raise PackGenerationError("empty_output")
    return g


# ------------------------------------------------------------------------------------------------------------------------ download
def render_markdown(content: dict[str, Any], labels: dict[str, str] | None = None) -> str:
    """A deterministic plain Markdown rendering of the stored structured content (English headings; the in-app view is localized). No new content."""
    L = labels or {}
    lines = [f"# {L.get('title', 'Opportunity Preparation Pack')}", "", f"_{L.get('disclaimer', 'AI-assisted interview preparation. Not a hiring decision, a guarantee or human coaching.')}_", ""]
    opp = content.get("opportunity") or {}
    if opp.get("title"):
        lines += [f"**{opp['title']}**", ""]
    for sec in content.get("sections", []):
        lines += [f"## {sec['id'].replace('_', ' ').title()} ({sec['status']})", ""]
        for it in sec.get("items", []):
            ref = f" [{', '.join(it.get('source_ids') or [])}]" if it.get("source_ids") else ""
            lines.append(f"- ({it['category']}) {it['text']}{ref}")
        for n in sec.get("notes", []):
            lines.append(f"- note: {n}")
        lines.append("")
    if content.get("sources"):
        lines += ["## Sources", ""] + [f"- {s['id']}: {s['title']}" + (f" ({s['url']})" if s.get("url") else "") for s in content["sources"]] + [""]
    lines += ["## Assumptions", ""] + [f"- {a}" for a in content.get("assumptions", [])] + ["", "## Limitations", ""] + [f"- {x}" for x in content.get("limitations", [])]
    return "\n".join(lines) + "\n"
