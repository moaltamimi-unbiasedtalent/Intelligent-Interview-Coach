"""Post-Sprint-4 — agent final-answer citation/grounding guard (P0).

Deterministic (no provider). Fabricated or stale citation markers are stripped from
the final answer; markers backed by the current run's retrieved evidence are kept;
answers that cite nothing are untouched. Also verified end-to-end through the agent
service so a fabricated marker never reaches the candidate-visible response.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.grounding import validate_citations
from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService


def _cites(*markers):
    return [{"marker": m, "title": "ESCO", "source": "ESCO"} for m in markers]


# --- unit: the guard --------------------------------------------------------


def test_valid_citation_preserved():
    text = "Median pay is high [1]."
    clean, warns = validate_citations(text, _cites("[1]"))
    assert clean == text and warns == []


def test_fabricated_marker_removed():
    clean, warns = validate_citations("A strong claim [3].", _cites("[1]"))
    assert "[3]" not in clean and clean == "A strong claim."
    assert warns and "unsupported citation" in warns[0]


def test_stale_marker_from_other_run_blocked():
    # No citations in THIS run → any marker is unsupported and removed.
    clean, warns = validate_citations("As shown earlier [2].", _cites())
    assert "[2]" not in clean and warns


def test_no_retrieval_generic_advice_needs_no_citation():
    text = "Use the STAR method and quantify your impact."
    clean, warns = validate_citations(text, _cites())
    assert clean == text and warns == []


def test_multi_source_only_current_evidence_allowed():
    clean, warns = validate_citations("Bands vary [1][2][9].", _cites("[1]", "[2]"))
    assert "[9]" not in clean and "[1]" in clean and "[2]" in clean and warns


# --- integration: through the agent service ---------------------------------


class _Career:
    def search_knowledge(self, req, *, progress=None):
        from src.copilot.models import Citation, KnowledgeEvidence
        from src.copilot.service import KnowledgeRetrievalResult
        return KnowledgeRetrievalResult(
            evidence=[KnowledgeEvidence(evidence_id="e1", text="band", source_id="esco",
                      source_title="ESCO", source_url="https://esco", evidence_type="compensation",
                      geography="DE", occupation_title="Product manager", reference_year=2024)],
            citations=[Citation(marker="[1]", doc_id="d1", chunk_id="c1", title="ESCO", source="ESCO",
                       source_url="https://esco", page=None)],
            resolved_occupation="Product manager", resolved_geography="DE",
            retrieval_lane="compensation", retrieval_strategy="structured",
            source_count=1, insufficient_evidence=False)


def _model_answering(answer: str):
    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            if not any(isinstance(m, ToolMessage) for m in messages):
                return AIMessage(content="", tool_calls=[{"name": "SearchCareerKnowledge",
                                "args": {"query": "pm salary"}, "id": "c0"}])
            return AIMessage(content=answer)
    return M()


def test_service_strips_fabricated_citation_from_response():
    # Model retrieves (producing [1]) but fabricates [2] and [5] in its answer.
    svc = AgentApplicationService(
        model_factory=lambda: _model_answering("Pay is strong [1], and rising fast [2][5]."),
        career_service=_Career())
    res = svc.run(AgentRunRequest(goal="salary for a PM in Germany?", user_id="u1"))
    assert "[1]" in res.response and "[2]" not in res.response and "[5]" not in res.response
    assert any("unsupported citation" in w for w in res.warnings)
    # The candidate-visible conversation is consistent with the grounded answer.
    assert res.conversation[-1]["role"] == "assistant"
    assert "[2]" not in res.conversation[-1]["content"]
