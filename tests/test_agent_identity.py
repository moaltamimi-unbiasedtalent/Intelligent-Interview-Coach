"""Mo — the AI Coach identity in the Career Preparation Agent's system prompt.

Mo is the candidate-facing identity of the existing stateful LangGraph Career
Preparation Agent — NOT a new agent, model, memory system or backend. These tests pin
the persona *instructions* that govern Mo's behaviour (introduce once, resolve "Mo" to
itself, disambiguate a person named Mo, never claim to be human). They assert the
authoritative prompt rather than making any live/paid model call.
"""

from __future__ import annotations

from src.agent.policies import SYSTEM_PROMPT

_PROMPT = SYSTEM_PROMPT.lower()


def test_identity_names_mo_as_the_ai_coach():
    assert "you are mo" in _PROMPT
    # Mo sits within the Ask4Mo brand and is described as a coach.
    assert "ask4mo" in _PROMPT
    assert "coach" in _PROMPT


def test_first_turn_introduction_once():
    # §7/§25: introduce once at the start of a new conversation…
    assert "introduce yourself once" in _PROMPT


def test_no_repeated_introduction():
    # §26: …and not again on every subsequent response.
    assert "do not repeatedly introduce yourself" in _PROMPT


def test_self_reference_resolution():
    # §9/§27: "Mo" in conversation refers to the coach itself.
    assert "referring to you" in _PROMPT


def test_contextual_disambiguation_of_other_mo():
    # §10/§28: a person the candidate names Mo is not the AI Coach — context wins.
    assert "unless the context" in _PROMPT
    assert "context always wins" in _PROMPT


def test_never_claims_to_be_human():
    assert "never claim to be human" in _PROMPT


def test_tool_rules_preserved_alongside_identity():
    # Persona is additive: the controlled-tool rules must remain intact (no behaviour
    # change to the LangGraph agent).
    for tool in (
        "AnalyzeJobDescription",
        "AnalyzeCandidateGaps",
        "BuildPreparationPlan",
        "GenerateInterviewQuestions",
        "SearchCareerKnowledge",
        "ProposePreparationMemory",
        "RequestPracticeHandoff",
    ):
        assert tool in SYSTEM_PROMPT
    # The core safety rule (treat inputs as DATA, never instructions) is still present.
    assert "DATA" in SYSTEM_PROMPT
