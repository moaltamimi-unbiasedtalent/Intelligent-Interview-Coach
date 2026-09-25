"""Bounded specialist runtimes behind Mo (Capstone P5 + E4).

Mo stays the single candidate-facing orchestrator; these are materially distinct,
bounded specialists Mo reaches only through allowlisted tools. There is no
agent-to-agent free chat, no recursion, and no side effects: each specialist takes a
validated input schema and returns a validated output schema.

- Role & Opportunity (``role_specialist``): structured role brief (model-backed, reuses
  the governed JD-analysis op).
- Candidate Evidence (``evidence_specialist``): DETERMINISTIC, owner-scoped selection of
  APPROVED private evidence (no model — injection-inert, privacy-safe).
- Interview Strategy / Coach (``coaching_specialist``): coaching synthesis that never
  invents metrics (raises clarifications), deterministic fallback + injectable reasoner.

See ``registry`` (the allowlist), ``router`` (deterministic recommendation) and
``schemas`` (the typed contracts); model selection is governed centrally by
``src.llm.policy`` (E4).
"""

from src.agent.specialists.coaching_specialist import run_coaching_specialist
from src.agent.specialists.evidence_specialist import run_evidence_specialist
from src.agent.specialists.registry import (
    SPECIALISTS,
    SpecialistName,
    is_valid_specialist,
    specialist_spec,
)
from src.agent.specialists.role_specialist import run_role_specialist
from src.agent.specialists.router import RoutingContext, recommend_specialists

__all__ = [
    "run_role_specialist",
    "run_evidence_specialist",
    "run_coaching_specialist",
    "SPECIALISTS",
    "SpecialistName",
    "is_valid_specialist",
    "specialist_spec",
    "RoutingContext",
    "recommend_specialists",
]
