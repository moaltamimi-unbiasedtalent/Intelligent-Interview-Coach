"""Post-Sprint-4 P1 — safe, bounded, per-thread retrieval cache.

An equivalent factual request already answered in the SAME thread reuses evidence
instead of paying for the deterministic pipeline again. The cache is thread-scoped
(never shared across users or runs), bounded, and invalidates whenever the query
changes materially (country / role / seniority / recency). No provider calls; the
fake pipeline records exactly how many times it was invoked.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService
from src.copilot.models import Citation, KnowledgeEvidence
from src.copilot.service import KnowledgeRetrievalResult


class FakeCareer:
    """Records every deterministic-pipeline query so cache hits are provable."""

    def __init__(self):
        self.queries: list[str] = []

    def search_knowledge(self, req, *, progress=None):
        self.queries.append(req.query)
        return KnowledgeRetrievalResult(
            evidence=[KnowledgeEvidence(evidence_id="e1", text="band", source_id="s",
                      source_title="ESCO", source_url="https://x", evidence_type="compensation",
                      geography="DE", occupation_title="PM", reference_year=2024)],
            citations=[Citation(marker="[1]", doc_id="d", chunk_id="c", title="ESCO",
                       source="ESCO", source_url="https://x", page=None)],
            resolved_occupation="PM", resolved_geography="DE", retrieval_lane="compensation",
            retrieval_strategy="structured", source_count=1, insufficient_evidence=False)


def _scripted(*queries):
    """A model that issues one SearchCareerKnowledge call per query, then finalises."""
    calls = [{"name": "SearchCareerKnowledge", "args": {"query": q}, "id": f"c{i}"}
             for i, q in enumerate(queries)]

    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            idx = sum(1 for m in messages if isinstance(m, ToolMessage))
            if idx < len(calls):
                return AIMessage(content="", tool_calls=[calls[idx]])
            return AIMessage(content="done [1]")
    return M()


def _run(queries, career=None, user_id="u1"):
    career = career or FakeCareer()
    svc = AgentApplicationService(model_factory=lambda: _scripted(*queries), career_service=career)
    res = svc.run(AgentRunRequest(goal="q", user_id=user_id))
    return res, career


# --- core hit / miss --------------------------------------------------------


def test_same_thread_equivalent_request_is_a_cache_hit():
    res, career = _run(["PM salary Germany", "pm salary germany"])  # 2nd is case-equivalent
    assert career.queries == ["PM salary Germany"]  # pipeline invoked exactly once
    assert res.cache_hits == 1 and res.cache_misses == 1


def test_cache_hit_avoids_a_duplicate_pipeline_retrieval():
    # A, B, A → A reused on its second appearance; pipeline sees only A and B.
    res, career = _run(["PM salary Germany", "nurse demand France", "PM salary Germany"])
    assert career.queries == ["PM salary Germany", "nurse demand France"]
    assert res.cache_hits == 1 and res.cache_misses == 2


def test_explain_that_reuses_existing_evidence():
    # An equivalent restated factual request reuses the prior evidence (no 2nd call).
    res, career = _run(["salary for PMs in Germany", "salary for PMs in Germany"])
    assert career.queries == ["salary for PMs in Germany"]
    assert res.cache_hits == 1


# --- invalidation (§29 / §31) -----------------------------------------------


def test_new_geography_is_a_miss():
    res, career = _run(["PM salary Germany", "PM salary France"])
    assert career.queries == ["PM salary Germany", "PM salary France"]
    assert res.cache_hits == 0 and res.cache_misses == 2


def test_new_role_is_a_miss():
    res, career = _run(["Product Manager salary Germany", "Engineering Manager salary Germany"])
    assert len(career.queries) == 2 and res.cache_hits == 0


def test_material_seniority_change_is_a_miss():
    res, career = _run(["mid-level PM compensation Germany", "senior PM compensation Germany"])
    assert len(career.queries) == 2 and res.cache_hits == 0


# --- isolation (§32) --------------------------------------------------------


def test_different_run_does_not_reuse_cache():
    # Each run() is a fresh thread → an empty cache → the pipeline runs again.
    career = FakeCareer()
    svc = AgentApplicationService(model_factory=lambda: _scripted("PM salary Germany"),
                                  career_service=career)
    svc.run(AgentRunRequest(goal="q", user_id="u1"))
    svc.run(AgentRunRequest(goal="q", user_id="u1"))
    assert career.queries == ["PM salary Germany", "PM salary Germany"]


def test_different_user_has_no_shared_cache():
    # Distinct users → distinct runs/threads → no shared private cache.
    career = FakeCareer()
    svc = AgentApplicationService(model_factory=lambda: _scripted("PM salary Germany"),
                                  career_service=career)
    svc.run(AgentRunRequest(goal="q", user_id="user-a"))
    svc.run(AgentRunRequest(goal="q", user_id="user-b"))
    assert career.queries == ["PM salary Germany", "PM salary Germany"]


# --- observability ----------------------------------------------------------


def test_cache_counters_exposed_without_keys():
    res, _ = _run(["PM salary Germany", "pm salary germany"])
    # Safe aggregate counters are present; the query text is never surfaced as a key.
    assert isinstance(res.cache_hits, int) and isinstance(res.cache_misses, int)
    assert not any("key" in (e.get("message") or "").lower() for e in res.events)
