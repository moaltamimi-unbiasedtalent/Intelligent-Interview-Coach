"""Phase 4.1 — general policy hardening from first-run live evidence.

The first authorised live run surfaced three GENERAL weaknesses: the model answering
externally-verifiable career facts from memory instead of retrieving, listing facts after
retrieval returned no sources, and not confirming a genuinely ambiguous role. These tests
pin the *general* policy that addresses them — asserting the guidance exists in the agent
system prompt and tool descriptions, and that NO benchmark-case-specific conditions were
added (no case names / prescriptive phrases from the paid evaluation).

They are deterministic and provider-free. The real behavioural effect can only be measured
by a (separately authorised) second live run — see docs/sprint4_final_evidence.md.
"""

from __future__ import annotations

from src.agent.policies import SYSTEM_PROMPT
from src.agent.tools import SearchCareerKnowledge

_P = SYSTEM_PROMPT.lower()


def test_external_career_facts_require_retrieval():
    assert "require retrieval" in _P
    # The broad "answerable from what you already know" carve-out is explicitly narrowed
    # so it does NOT excuse skipping retrieval for external career facts.
    assert "answerable from what you already know" in _P
    assert "do not assert such facts from general knowledge" in _P


def test_insufficient_evidence_must_be_qualified():
    assert "enough verified evidence" in _P
    assert "do not then present those facts as established" in _P
    assert "invented citations" in _P


def test_ambiguous_role_confirmation_rule():
    assert "confirm which they mean" in _P
    assert "harmless ambiguity" in _P  # do not over-interrupt


def test_comprehensive_preparation_intent_recognised():
    assert "comprehensive preparation" in _P
    # Still agentic — a single specific request is honoured as just that.
    assert "when they ask for one specific thing, do just that" in _P


def test_search_tool_description_prefers_retrieval_before_asserting():
    doc = (SearchCareerKnowledge.__doc__ or "").lower()
    assert "before stating" in doc


def test_no_benchmark_case_names_leaked_into_policy():
    # Remediation must be GENERAL — never special-case the live evaluation.
    for case_id in (
        "ambiguous_role_hitl", "insufficient_evidence", "full_prep_intent",
        "competency_expectations", "salary_range", "credential_question",
        "factual_plus_prep",
    ):
        assert case_id not in _P


def test_tool_rules_and_safety_preserved():
    # Hardening is additive: the controlled-tool set and DATA-not-instructions rule stay.
    for tool in (
        "AnalyzeJobDescription", "AnalyzeCandidateGaps", "BuildPreparationPlan",
        "GenerateInterviewQuestions", "SearchCareerKnowledge",
    ):
        assert tool in SYSTEM_PROMPT
    assert "DATA" in SYSTEM_PROMPT
    assert "never as" in _P  # untrusted content is never followed as instructions
