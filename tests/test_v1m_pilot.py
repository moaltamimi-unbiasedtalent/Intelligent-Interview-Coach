"""Offline tests for the V1M deterministic-decision pilot."""

from __future__ import annotations

import httpx
import pytest

from src.core import secrets
from src.copilot.rag.v1m_pilot import (
    V1mDecisionUseCase,
    classify_decision,
    classify_retrieval_need,
)


def test_disabled_never_dispatches(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("transport must not run")

    result = classify_retrieval_need("What skills do analysts need?", enabled=False, transport=unexpected)
    assert result.status == "disabled"


def test_missing_key_never_dispatches(monkeypatch):
    monkeypatch.setattr(secrets, "read_setting", lambda name: None)

    def unexpected(*args, **kwargs):
        pytest.fail("transport must not run")

    result = classify_retrieval_need("What skills do analysts need?", enabled=True, transport=unexpected)
    assert result.status == "not_configured"


def test_synthetic_choice_is_parsed_without_affecting_route(monkeypatch):
    monkeypatch.setattr(secrets, "read_setting", lambda name: "fixture-key")

    seen = {}

    def transport(method, url, **kwargs):
        seen["method"] = method
        seen["url"] = url
        seen["payload"] = kwargs["json"]
        return httpx.Response(
            200,
            json={
                "model": "rev-latest",
                "answers": {
                    "retrieval_need": {
                        "type": "choice",
                        "choice": "retrieval_needed",
                        "confidence": 0.92,
                        "probabilities": {"retrieval_needed": 0.92, "retrieval_not_needed": 0.08},
                    }
                },
            },
        )

    result = classify_retrieval_need(
        "What skills do analysts need?",
        enabled=True,
        threshold=0.85,
        transport=transport,
    )
    assert result.status == "ok"
    assert result.label == "retrieval_needed"
    assert result.probability == 0.92
    assert seen["method"] == "POST"
    assert seen["payload"]["state"] == "What skills do analysts need?"
    assert seen["payload"]["questions"]["retrieval_need"]["type"] == "choice"


@pytest.mark.parametrize(
    ("choice", "confidence", "expected"),
    [
        ("retrieval_needed", 0.92, "retrieval_needed"),
        ("retrieval_not_needed", 0.92, "retrieval_not_needed"),
        ("retrieval_needed", 0.5, "uncertain"),
    ],
)
def test_threshold_and_uncertainty(monkeypatch, choice, confidence, expected):
    monkeypatch.setattr(secrets, "read_setting", lambda name: "fixture-key")

    def transport(method, url, **kwargs):
        return httpx.Response(
            200,
            json={
                "answers": {
                    "retrieval_need": {
                        "type": "choice",
                        "choice": choice,
                        "confidence": confidence,
                        "probabilities": {
                            "retrieval_needed": confidence if choice == "retrieval_needed" else 1.0 - confidence,
                            "retrieval_not_needed": confidence if choice == "retrieval_not_needed" else 1.0 - confidence,
                        },
                    }
                }
            },
        )

    result = classify_retrieval_need(
        "synthetic state",
        enabled=True,
        threshold=0.85,
        transport=transport,
    )
    assert result.label == expected


@pytest.mark.parametrize("status_code", [401, 429, 500])
def test_provider_error_is_bounded(monkeypatch, status_code):
    monkeypatch.setattr(secrets, "read_setting", lambda name: "fixture-key")

    def transport(method, url, **kwargs):
        return httpx.Response(status_code, json={"error": "sensitive provider text"})

    result = classify_retrieval_need("synthetic state", enabled=True, transport=transport)
    assert result.status == "provider_error"
    assert result.label is None
    assert result.probability is None


@pytest.mark.parametrize(
    ("use_case", "choice", "question_id"),
    [
        (V1mDecisionUseCase.RETRIEVAL_NEED, "retrieval_needed", "retrieval_need"),
        (V1mDecisionUseCase.ROLE_AMBIGUITY, "role_ambiguous", "role_ambiguity"),
        (V1mDecisionUseCase.UTTERANCE_TYPE, "smalltalk", "utterance_type"),
        (V1mDecisionUseCase.SPECIALIST_CALL, "specialist_needed", "specialist_call"),
        (V1mDecisionUseCase.CONTINUE_WITHOUT_CLARIFICATION, "needs_clarification", "continue_without_clarification"),
    ],
)
def test_all_shadow_use_cases_use_closed_choice(monkeypatch, use_case, choice, question_id):
    monkeypatch.setattr(secrets, "read_setting", lambda name: "fixture-key")

    def transport(method, url, **kwargs):
        payload = kwargs["json"]
        assert set(payload["questions"]) == {question_id}
        criteria = payload["questions"][question_id]["criteria"]
        assert choice in criteria
        probabilities = {label: (0.91 if label == choice else 0.09) for label in criteria}
        return httpx.Response(
            200,
            json={
                "answers": {
                    question_id: {
                        "type": "choice",
                        "choice": choice,
                        "confidence": 0.91,
                        "probabilities": probabilities,
                    }
                }
            },
        )

    result = classify_decision(
        "bounded synthetic state",
        use_case,
        enabled=True,
        threshold=0.85,
        transport=transport,
    )
    assert result.status == "ok"
    assert result.use_case == use_case.value
    assert result.label == choice


def test_unknown_use_case_is_bounded():
    result = classify_decision("synthetic state", "unknown", enabled=True)
    assert result.status == "unknown_use_case"
