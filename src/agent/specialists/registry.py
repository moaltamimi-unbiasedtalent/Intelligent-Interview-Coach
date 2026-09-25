"""Specialist registry — a strict allowlist of bounded specialists (Capstone P5).

Analogous to the tool ``ToolRegistry``: the set of specialists is fixed and closed.
Each entry declares which E4 model operation it runs under and whether it is
model-backed or deterministic. A name outside this allowlist is never valid — there is
no dynamic dispatch, no recursion, and no agent-to-agent free chat. The registry is the
single place that answers "which specialists exist and what are their bounds?".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.llm.policy import ModelOperation

__all__ = ["SpecialistName", "SpecialistSpec", "SPECIALISTS", "is_valid_specialist", "specialist_spec"]


class SpecialistName(str, Enum):
    ROLE_OPPORTUNITY = "role_opportunity"
    CANDIDATE_EVIDENCE = "candidate_evidence"
    INTERVIEW_STRATEGY = "interview_strategy"


@dataclass(frozen=True)
class SpecialistSpec:
    name: SpecialistName
    operation: ModelOperation
    model_backed: bool
    reads_private_evidence: bool
    tool_name: str          # the allowlisted tool the model calls to reach it
    description: str


SPECIALISTS: dict[SpecialistName, SpecialistSpec] = {
    SpecialistName.ROLE_OPPORTUNITY: SpecialistSpec(
        name=SpecialistName.ROLE_OPPORTUNITY,
        operation=ModelOperation.SPECIALIST_ROLE_ANALYSIS,
        model_backed=True,
        reads_private_evidence=False,
        tool_name="AnalyzeRoleOpportunity",
        description="Structured role/opportunity brief: key competencies, interview "
        "themes and priorities from a JD / prior analysis / role name.",
    ),
    SpecialistName.CANDIDATE_EVIDENCE: SpecialistSpec(
        name=SpecialistName.CANDIDATE_EVIDENCE,
        operation=ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS,
        model_backed=False,  # deterministic by policy
        reads_private_evidence=True,
        tool_name="FindCandidateEvidence",
        description="Owner-scoped, deterministic selection of the candidate's APPROVED "
        "claims and verified stories matching a stated need.",
    ),
    SpecialistName.INTERVIEW_STRATEGY: SpecialistSpec(
        name=SpecialistName.INTERVIEW_STRATEGY,
        operation=ModelOperation.SPECIALIST_COACHING,
        model_backed=True,
        reads_private_evidence=False,  # receives ONLY the bounded evidence packet
        tool_name="BuildCoachingStrategy",
        description="Coaching recommendations mapping approved evidence to role "
        "competencies; raises clarifications instead of inventing metrics.",
    ),
}


def is_valid_specialist(name: str) -> bool:
    try:
        SpecialistName(str(name))
        return True
    except ValueError:
        return False


def specialist_spec(name: "SpecialistName | str") -> SpecialistSpec:
    key = name if isinstance(name, SpecialistName) else SpecialistName(str(name))
    return SPECIALISTS[key]
