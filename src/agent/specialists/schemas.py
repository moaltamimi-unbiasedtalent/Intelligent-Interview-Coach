"""Typed, schema-validated I/O contracts for the bounded specialists (Capstone P5).

Every specialist runtime takes a validated input model and returns a validated output
model — there is no free-form string channel between specialists and no agent-to-agent
chat. All model-produced identifiers (evidence ids) are ints that the caller
re-resolves through owner-scoped repositories before use (a specialist can never assert
ownership by emitting an id). Bounds are enforced here so a specialist's output is
always small, safe and predictable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "Confidence",
    "RoleAnalysisInput",
    "RoleBrief",
    "EvidenceRequest",
    "EvidenceItem",
    "EvidenceSelection",
    "CoachingInput",
    "CoachingRecommendation",
    "CoachingPlan",
]

# Bounded confidence vocabulary (never a fabricated numeric certainty).
Confidence = str  # one of: "high" | "medium" | "low"
_CONFIDENCE = {"high", "medium", "low"}


def _norm_confidence(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in _CONFIDENCE else "low"


# --- A. Role & Opportunity specialist ---------------------------------------


class RoleAnalysisInput(BaseModel):
    """What the Role & Opportunity specialist needs. No private candidate documents."""

    target_role: str | None = Field(default=None, max_length=200)
    job_description: str | None = Field(default=None, max_length=12000)
    # A prior structured job analysis (RoleRequirements.model_dump()), if Mo already ran it.
    requirements: dict | None = None


class RoleBrief(BaseModel):
    """A bounded, structured role brief. Advisory only — never a hiring decision."""

    role_title: str = Field(default="", max_length=200)
    seniority: str | None = Field(default=None, max_length=80)
    key_competencies: list[str] = Field(default_factory=list, max_length=20)
    interview_themes: list[str] = Field(default_factory=list, max_length=20)
    priorities: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=10)
    confidence: Confidence = "low"
    # Provenance of the brief: "job_analysis" (governed LLM op) | "requirements"
    # (reused prior analysis) | "role_only" (name only) | "insufficient".
    source: str = Field(default="insufficient", max_length=40)


# --- B. Candidate Evidence specialist (deterministic, owner-scoped) ----------


class EvidenceRequest(BaseModel):
    """What the Candidate Evidence specialist is asked to find in the OWNER's approved
    evidence. The owner user_id is NEVER part of this model — it is injected from
    trusted run state, never supplied by the model."""

    need: str = Field(default="", max_length=2000, description="What evidence is needed.")
    competencies: list[str] = Field(default_factory=list, max_length=30)
    limit: int = Field(default=8, ge=1, le=20)


class EvidenceItem(BaseModel):
    """One safe projection of an approved claim or a valid story. Never a raw document."""

    kind: str = Field(max_length=16)              # "claim" | "story"
    id: int
    label: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=1200)
    provenance: str = Field(default="", max_length=200)
    competencies: list[str] = Field(default_factory=list, max_length=30)


class EvidenceSelection(BaseModel):
    """The bounded evidence packet the Coach may reason over. Owner-scoped, approved-only."""

    items: list[EvidenceItem] = Field(default_factory=list, max_length=20)
    covered_competencies: list[str] = Field(default_factory=list, max_length=30)
    uncovered_competencies: list[str] = Field(default_factory=list, max_length=30)
    claim_count: int = 0
    story_count: int = 0
    notes: list[str] = Field(default_factory=list, max_length=10)


# --- C. Interview Strategy / Coach specialist -------------------------------


class CoachingInput(BaseModel):
    """Role requirements + bounded approved evidence → coaching. Advisory only."""

    role_brief: RoleBrief
    evidence: EvidenceSelection
    gaps: dict | None = None


class CoachingRecommendation(BaseModel):
    recommendation: str = Field(max_length=600)
    competency: str | None = Field(default=None, max_length=200)
    # Ints referencing EvidenceItem.id — re-resolved owner-scoped before display.
    supporting_evidence_ids: list[int] = Field(default_factory=list, max_length=20)


class CoachingPlan(BaseModel):
    """The Coach's advisory output. It never invents metrics/outcomes — where evidence
    is missing it raises a clarification instead of asserting an achievement."""

    recommendations: list[CoachingRecommendation] = Field(default_factory=list, max_length=20)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    gaps: list[str] = Field(default_factory=list, max_length=20)
    # CLARIFICATION_NEEDED prompts — what to ask the candidate rather than fabricate.
    clarifications: list[str] = Field(default_factory=list, max_length=20)
    confidence: Confidence = "low"
