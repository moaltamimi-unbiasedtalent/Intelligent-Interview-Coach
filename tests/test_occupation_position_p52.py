"""Position-agnostic occupation resolution + citation acceptance (Phase 5.2, P1).

Golden Demo Live Rehearsal #2 produced NO citation because the Agent reformulated the
question with the role TRAILING — "typical skills and responsibilities expected of a
Senior Product Manager" — and the resolver (which only handled scaffolded questions and
occupation-LEADING keyword queries) matched nothing, so retrieval returned 0 sources.

These deterministic tests (no KB build, no vector lane, no provider) pin the general
fix: the occupation is resolved wherever it sits, as long as it is introduced by a
role-scaffolding connective ("expected of a…", "for a…", "as a…", "does a…") or leads
the query — while an unknown role, even behind such a connective, is never mapped to an
unrelated occupation, and genuinely ambiguous roles surface as ambiguity.

No role, prompt, industry or geography is special-cased.
"""

from __future__ import annotations

import pytest

from src.copilot.knowledge.resolver import resolve_occupation
from src.copilot.knowledge.retrieval import StructuredRetrievalCoordinator
from src.copilot.knowledge.roles import NormalisedOccupation, RoleRepository, Skill
from src.copilot.service import CareerIntelligenceService


# --- fixtures: a small, real, in-memory role store ---------------------------

def _role_repo() -> RoleRepository:
    repo = RoleRepository(":memory:")
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:11-2021", title="Product Manager", source_id="onet",
        tasks=["Own the roadmap", "Prioritise the backlog"],
        skills=[Skill(name="Discovery"), Skill(name="Prioritisation")]))
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:29-1141", title="Registered Nurse", source_id="onet",
        tasks=["Assess patient conditions", "Administer treatments"],
        skills=[Skill(name="Clinical judgement"), Skill(name="Patient assessment")]))
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:13-2051", title="Financial Analyst", source_id="onet",
        tasks=["Build financial models", "Forecast revenue"],
        skills=[Skill(name="Financial modelling"), Skill(name="Forecasting")]))
    return repo


def _ambiguous_repo() -> RoleRepository:
    repo = RoleRepository(":memory:")
    for code, title in [("a", "Data Analyst"), ("b", "Data Scientist")]:
        repo.add_occupation(NormalisedOccupation(
            occupation_code=code, title=title, source_id="onet",
            tasks=["Work with data"], skills=[Skill(name="SQL")]))
    return repo


_MANIFEST = [type("E", (), {"source_id": "onet", "title": "O*NET",
                            "source_url": "https://onet.org", "publisher": "US DOL",
                            "authority_level": 1, "region": "US", "country": "US"})()]


class _ExplodingResponder:
    def __call__(self, messages):  # pragma: no cover - retrieval must not synthesize
        raise AssertionError("retrieve_evidence must not invoke the synthesis model")


def _service(repo: RoleRepository) -> CareerIntelligenceService:
    coord = StructuredRetrievalCoordinator(role_repo=repo, manifest_entries=_MANIFEST)
    return CareerIntelligenceService(
        knowledge_coordinator=coord, synthesis_responder=_ExplodingResponder(),
        retriever=None)


# --- §10 resolver matrix: occupation in every position -----------------------

class TestPositionAgnosticResolution:
    @pytest.mark.parametrize("query, expected", [
        # Leading role (Phase 5.1 shape).
        ("Senior Product Manager typical responsibilities and core skills", "Product Manager"),
        # Trailing role behind scaffolding — the exact Rehearsal #2 failing shape.
        ("typical skills and responsibilities expected of a Senior Product Manager", "Product Manager"),
        # §10 scaffolded shapes.
        ("what skills are expected of a product manager", "Product Manager"),
        ("typical responsibilities of a registered nurse", "Registered Nurse"),
        ("what does a financial analyst usually do", "Financial Analyst"),
        ("skills required for a product manager in software", "Product Manager"),
        ("for a registered nurse, which competencies matter most", "Registered Nurse"),
        # Clean documented user query (unchanged).
        ("What skills and responsibilities are typically expected of a Senior Product Manager?",
         "Product Manager"),
    ])
    def test_role_resolves_regardless_of_position(self, query, expected):
        resolved = resolve_occupation(_role_repo(), query)
        assert resolved.best is not None, f"should resolve: {query!r}"
        assert resolved.best.title == expected
        assert not resolved.ambiguous

    def test_rehearsal2_trailing_shape_regression(self):
        # Explicit regression for the precise Agent-generated query that failed live.
        resolved = resolve_occupation(
            _role_repo(),
            "typical skills and responsibilities expected of a Senior Product Manager")
        assert resolved.best is not None and resolved.best.title == "Product Manager"

    @pytest.mark.parametrize("query", [
        "intergalactic vibe curator typical responsibilities and core skills",  # leading
        "what are the duties of a intergalactic vibe curator",                  # scaffolded
        "skills expected of a wizard",                                          # scaffolded
    ])
    def test_unknown_role_is_never_mapped_to_a_supported_one(self, query):
        # A connective does NOT license mapping an unsupported title to an unrelated role.
        assert resolve_occupation(_role_repo(), query).best is None

    def test_materially_ambiguous_role_reports_ambiguity(self):
        resolved = resolve_occupation(_ambiguous_repo(), "skills for a data professional")
        assert resolved.ambiguous
        assert {c.title for c in resolved.candidates} >= {"Data Analyst", "Data Scientist"}


# --- §11 end-to-end citation acceptance (deterministic, no provider) ---------

class TestCitationAcceptance:
    @pytest.mark.parametrize("query", [
        "typical skills and responsibilities expected of a Senior Product Manager",
        "what skills are expected of a product manager",
        "Senior Product Manager typical responsibilities and core skills",
    ])
    def test_resolved_query_produces_grounded_sources(self, query):
        result = _service(_role_repo()).retrieve_evidence(query)
        assert result.source_count > 0
        assert not result.insufficient_evidence
        assert result.retrieval_lane == "structured_role"
        assert result.citations and all(c.marker for c in result.citations)
        assert any((c.title or c.source_url) for c in result.citations)

    def test_unknown_role_yields_no_fabricated_source(self):
        result = _service(_role_repo()).retrieve_evidence(
            "typical responsibilities expected of a chief vibe officer")
        assert result.source_count == 0
        assert result.insufficient_evidence
        assert result.citations == []

    def test_ambiguous_role_does_not_fabricate_a_single_source(self):
        result = _service(_ambiguous_repo()).retrieve_evidence(
            "skills expected of a data professional")
        # Ambiguous → the coordinator does not emit one role's evidence as if certain.
        assert result.source_count == 0
        assert result.insufficient_evidence
