"""Post-Sprint-4 P0.1 — agent final-answer output guard + grounding policy.

Deterministic (no provider). The agent final answer is passed through the shared
Sprint-3 output guard (secret redaction, system-instruction leakage flag, citation-
provenance validation) plus an agent-specific uncited-retrieval observability policy.
Verified both as a unit and end-to-end through the agent service so an unsafe/fabricated
reference never reaches the candidate-visible response. No provider calls anywhere here.

Scope note: removing an unsupported citation marker is a PROVENANCE fix, not a claim
that the sentence is factually wrong. Semantic claim-level faithfulness stays an
evaluation concern (RAGAS / live benchmark), never a runtime cost.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.grounding import guard_agent_answer, validate_citations
from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService


def _cites(*markers):
    return [{"marker": m, "title": "ESCO", "source": "ESCO"} for m in markers]


# --- unit: the 8 required grounding/output-guard scenarios -------------------


def test_1_valid_current_citation_preserved():
    text = "Median pay is high [1]."
    clean, warns = guard_agent_answer(text, _cites("[1]"), retrieval_used=True)
    assert clean == text and warns == []


def test_2_fabricated_marker_removed():
    clean, warns = guard_agent_answer("A strong claim [3].", _cites("[1]"), retrieval_used=True)
    assert "[3]" not in clean and clean == "A strong claim."
    # A provenance finding is raised; it does not claim the sentence is false.
    assert any("citation" in w.lower() for w in warns)


def test_3_stale_marker_from_other_run_removed():
    # No citations in THIS run → any marker is unsupported (stale) and removed.
    clean, warns = guard_agent_answer("As shown earlier [2].", _cites(), retrieval_used=False)
    assert "[2]" not in clean and any("citation" in w.lower() for w in warns)


def test_4_secret_like_string_redacted():
    answer = "For reference the key is sk-or-v1-abcdef0123456789 — keep it safe."
    clean, warns = guard_agent_answer(answer, _cites(), retrieval_used=False)
    assert "sk-or-v1-abcdef0123456789" not in clean and "[REDACTED]" in clean
    assert any("secret" in w.lower() for w in warns)


def test_5_system_prompt_leakage_flagged_safely():
    # Verbatim system-instruction fragment surfacing in the answer is flagged (not
    # silently emitted as if normal). The warning itself is safe/observability-only.
    answer = "Sure — grounding rules say I must cite everything I claim."
    clean, warns = guard_agent_answer(answer, _cites(), retrieval_used=False)
    assert any("system-instruction leakage" in w.lower() for w in warns)


def test_6_retrieval_used_with_citations_but_no_inline_reference_warns():
    # Retrieval genuinely ran and produced [1], but the answer cites nothing inline.
    clean, warns = guard_agent_answer(
        "Pay bands vary widely by region and seniority.", _cites("[1]"), retrieval_used=True
    )
    assert clean == "Pay bands vary widely by region and seniority."
    assert any("did not include an inline source reference" in w for w in warns)


def test_7_no_retrieval_generic_advice_needs_no_citation():
    text = "Use the STAR method and quantify your impact."
    clean, warns = guard_agent_answer(text, _cites(), retrieval_used=False)
    assert clean == text and warns == []


def test_8_insufficient_evidence_needs_no_fabricated_citation():
    # Retrieval ran but produced NO citations; the answer honestly declines. There is
    # nothing to cite, so no uncited-retrieval warning is raised and nothing is added.
    text = "I don't have enough evidence to give a reliable pay range for that role."
    clean, warns = guard_agent_answer(text, _cites(), retrieval_used=True)
    assert clean == text and warns == []


# --- unit: extra provenance edge cases --------------------------------------


def test_multi_source_only_current_evidence_allowed():
    clean, warns = guard_agent_answer("Bands vary [1][2][9].", _cites("[1]", "[2]"), retrieval_used=True)
    assert "[9]" not in clean and "[1]" in clean and "[2]" in clean and warns


def test_validate_citations_wrapper_is_provenance_only():
    # The thin wrapper never raises the retrieval-context signal (retrieval_used=False).
    _, warns = validate_citations("Pay bands vary.", _cites("[1]"))
    assert not any("inline source reference" in w for w in warns)


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
    assert any("citation" in w.lower() for w in res.warnings)
    # The candidate-visible conversation is consistent with the grounded answer.
    assert res.conversation[-1]["role"] == "assistant"
    assert "[2]" not in res.conversation[-1]["content"]


def test_service_redacts_secret_in_response():
    svc = AgentApplicationService(
        model_factory=lambda: _model_answering("The internal key sk-or-v1-abcdef0123456789 backs [1]."),
        career_service=_Career())
    res = svc.run(AgentRunRequest(goal="salary for a PM in Germany?", user_id="u1"))
    assert "sk-or-v1-abcdef0123456789" not in res.response and "[REDACTED]" in res.response
    assert any("secret" in w.lower() for w in res.warnings)


def test_service_warns_when_retrieval_used_but_answer_uncited():
    svc = AgentApplicationService(
        model_factory=lambda: _model_answering("Pay varies a lot by seniority and location."),
        career_service=_Career())
    res = svc.run(AgentRunRequest(goal="salary for a PM in Germany?", user_id="u1"))
    assert res.retrieval_used is True
    assert any("did not include an inline source reference" in w for w in res.warnings)
