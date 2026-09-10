"""Citation reliability under verbose queries (Phase 5.1, Defect B).

The first golden-demo rehearsal produced NO visible citation: the agent decided to
retrieve, but issued a verbose, occupation-bearing natural-language query
("Senior Product Manager typical responsibilities and core skills B2B SaaS fintech")
and the deterministic occupation resolver — which then only handled question-scaffolded
phrasing — matched nothing, so retrieval returned 0 sources.

These held-out tests pin the GENERAL fix (no role, prompt, industry or geography is
special-cased):

  * verbose, occupation-leading queries resolve to the role for occupations present in
    the fixtures (registered nurse, product manager, financial analyst);
  * an unknown occupation returns no candidate — a real occupation word buried in an
    otherwise-unrelated phrase is NOT plucked into a wrong role;
  * end to end, a verbose query resolves → source_count > 0 with citation metadata,
    while an unknown occupation yields insufficient evidence and NO fabricated source —
    and neither path invokes any provider (retrieval only; synthesis never runs).

All wiring is in-memory and deterministic: no built knowledge base, no network, no
provider call.
"""

from __future__ import annotations

import pytest

from src.copilot.knowledge.resolver import resolve_occupation
from src.copilot.knowledge.retrieval import StructuredRetrievalCoordinator
from src.copilot.knowledge.roles import NormalisedOccupation, RoleRepository, Skill
from src.copilot.service import CareerIntelligenceService


# --- Fixtures: a small, real, in-memory role store ---------------------------

def _role_repo() -> RoleRepository:
    repo = RoleRepository(":memory:")
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:29-1141", title="Registered Nurse", source_id="onet",
        tasks=["Assess patient conditions", "Administer treatments", "Coordinate care"],
        skills=[Skill(name="Patient assessment"), Skill(name="Clinical judgement"),
                Skill(name="Medication administration")]))
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:11-2021", title="Product Manager", source_id="onet",
        tasks=["Own the roadmap", "Prioritise the backlog", "Define outcome metrics"],
        skills=[Skill(name="Stakeholder management"), Skill(name="Discovery"),
                Skill(name="Prioritisation")]))
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:13-2051", title="Financial Analyst", source_id="onet",
        tasks=["Build financial models", "Analyse variance", "Forecast revenue"],
        skills=[Skill(name="Financial modelling"), Skill(name="Forecasting"),
                Skill(name="Valuation")]))
    return repo


_MANIFEST = [
    type("E", (), {"source_id": "onet", "title": "O*NET", "source_url": "https://onet.org",
                   "publisher": "US DOL", "authority_level": 1, "region": "US",
                   "country": "US"})()
]


class _ExplodingResponder:
    """Fails the test loudly if synthesis (a provider call) is ever invoked."""

    def __call__(self, messages):  # pragma: no cover - must never run
        raise AssertionError("retrieve_evidence must not invoke the synthesis model")


def _service(role_repo: RoleRepository) -> CareerIntelligenceService:
    coord = StructuredRetrievalCoordinator(role_repo=role_repo, manifest_entries=_MANIFEST)
    return CareerIntelligenceService(
        knowledge_coordinator=coord,
        synthesis_responder=_ExplodingResponder(),  # proves no synthesis on retrieval
        retriever=None,                              # no vector/provider retrieval
    )


# --- Resolver unit tests (the core of Defect B) ------------------------------

class TestVerboseOccupationResolution:
    @pytest.mark.parametrize("query, expected_title", [
        ("Senior Product Manager typical responsibilities and core skills B2B SaaS fintech",
         "Product Manager"),
        ("registered nurse day-to-day responsibilities and essential clinical skills",
         "Registered Nurse"),
        ("financial analyst core skills and typical duties in corporate finance",
         "Financial Analyst"),
    ])
    def test_verbose_leading_query_resolves_role(self, query, expected_title):
        repo = _role_repo()
        resolved = resolve_occupation(repo, query)
        assert resolved.best is not None, "verbose occupation-leading query must resolve"
        assert resolved.best.title == expected_title
        assert not resolved.ambiguous

    def test_clean_scaffolded_query_still_resolves(self):
        # Stage 1 (phrase extraction) is unchanged — no regression for clean phrasing.
        repo = _role_repo()
        resolved = resolve_occupation(
            repo, "What skills and responsibilities are important for a product manager?")
        assert resolved.best is not None
        assert resolved.best.title == "Product Manager"

    def test_unknown_occupation_returns_no_candidate(self):
        repo = _role_repo()
        resolved = resolve_occupation(
            repo, "intergalactic vibe curator typical responsibilities and core skills")
        assert resolved.best is None  # nothing fabricated

    def test_buried_real_occupation_word_is_not_plucked(self):
        # "manager" appears mid-phrase but the query does not LEAD with a real role —
        # the window scan is anchored to the start, so no wrong role is invented.
        repo = _role_repo()
        resolved = resolve_occupation(
            repo, "quantum flux something manager of interdimensional vibes")
        assert resolved.best is None


# --- End-to-end citation acceptance (retrieval only, no provider) ------------

class TestVerboseQueryCitationAcceptance:
    def test_verbose_query_produces_grounded_sources_with_metadata(self):
        svc = _service(_role_repo())
        result = svc.retrieve_evidence(
            "Senior Product Manager typical responsibilities and core skills B2B SaaS fintech")

        assert result.source_count > 0
        assert not result.insufficient_evidence
        assert result.retrieval_lane == "structured_role"
        # Citation metadata is present and displayable (not chunk ids/scores).
        assert result.citations
        assert all(c.marker for c in result.citations)
        assert any((c.title or c.source_url) for c in result.citations)

    def test_unknown_occupation_yields_no_fabricated_source(self):
        svc = _service(_role_repo())
        result = svc.retrieve_evidence(
            "intergalactic vibe curator typical responsibilities and core skills")

        assert result.source_count == 0
        assert result.insufficient_evidence
        assert result.citations == []
