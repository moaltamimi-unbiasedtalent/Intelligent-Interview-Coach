"""Opt-in V1M System One shadow pilot for bounded micro-decisions.

This module is advisory and never changes career routing, synthesis,
specialist execution, or interview decisions. Live use is explicitly enabled
by the operator. Each request is a closed choice with at most 512 characters
of state. Candidate-private data must not be sent by a shadow integration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import httpx

from src.core import secrets

V1M_ENDPOINT = "https://v1m.ir/v1/systemone"
V1M_MODEL = "rev-latest"
PILOT_ENABLED = "V1M_PILOT_ENABLED"
PILOT_THRESHOLD = "V1M_PILOT_CONFIDENCE_THRESHOLD"
DEFAULT_THRESHOLD = 0.85
MAX_STATE_CHARS = 512


class V1mDecisionUseCase(str, Enum):
    RETRIEVAL_NEED = "retrieval_need"
    ROLE_AMBIGUITY = "role_ambiguity"
    UTTERANCE_TYPE = "utterance_type"
    SPECIALIST_CALL = "specialist_call"
    CONTINUE_WITHOUT_CLARIFICATION = "continue_without_clarification"


@dataclass(frozen=True)
class V1mDecisionSpec:
    question_id: str
    instructions: str
    criteria: dict[str, str]


_DECISION_SPECS: dict[V1mDecisionUseCase, V1mDecisionSpec] = {
    V1mDecisionUseCase.RETRIEVAL_NEED: V1mDecisionSpec(
        question_id="retrieval_need",
        instructions=(
            "Does this state need verified career knowledge, role, skills, "
            "labour-market, qualification, or interview evidence?"
        ),
        criteria={
            "retrieval_needed": "Verified career evidence or knowledge retrieval is needed.",
            "retrieval_not_needed": "This is a greeting, acknowledgement, or interface instruction.",
        },
    ),
    V1mDecisionUseCase.ROLE_AMBIGUITY: V1mDecisionSpec(
        question_id="role_ambiguity",
        instructions="Does the state identify one reasonably clear target role or several materially different roles?",
        criteria={
            "role_unambiguous": "One target role is reasonably clear.",
            "role_ambiguous": "Several materially different target roles are plausible.",
        },
    ),
    V1mDecisionUseCase.UTTERANCE_TYPE: V1mDecisionSpec(
        question_id="utterance_type",
        instructions="Is the state small talk or a candidate career or interview question?",
        criteria={
            "smalltalk": "Greeting, acknowledgement, thanks, or an interface-only remark.",
            "candidate_question": "A substantive career, role, preparation, or interview question.",
        },
    ),
    V1mDecisionUseCase.SPECIALIST_CALL: V1mDecisionSpec(
        question_id="specialist_call",
        instructions="Would an existing specialist add useful bounded advice for this state?",
        criteria={
            "specialist_needed": "The state has enough known role, evidence, or coaching context for a specialist.",
            "specialist_not_needed": "No bounded specialist advice is needed from the current state.",
        },
    ),
    V1mDecisionUseCase.CONTINUE_WITHOUT_CLARIFICATION: V1mDecisionSpec(
        question_id="continue_without_clarification",
        instructions="Is enough information available to continue, or is clarification required first?",
        criteria={
            "continue_without_clarification": "Enough information is available to continue safely.",
            "needs_clarification": "A missing or ambiguous required fact would make continuation unsafe.",
        },
    ),
}


@dataclass(frozen=True)
class V1mPilotResult:
    status: str
    label: str | None = None
    probability: float | None = None
    latency_ms: float | None = None
    use_case: str | None = None


def pilot_enabled(environ: dict[str, str] | None = None) -> bool:
    if environ is None:
        return secrets.read_bool(PILOT_ENABLED, default=False)
    raw = environ.get(PILOT_ENABLED, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def confidence_threshold() -> float:
    raw = secrets.read_float(PILOT_THRESHOLD, DEFAULT_THRESHOLD)
    return min(1.0, max(0.0, raw))


def classify_decision(
    state: str,
    use_case: V1mDecisionUseCase | str,
    *,
    enabled: bool | None = None,
    threshold: float | None = None,
    timeout_s: float = 10.0,
    transport: Callable[..., Any] | None = None,
) -> V1mPilotResult:
    """Return a bounded V1M shadow decision for one closed use case."""
    try:
        decision = use_case if isinstance(use_case, V1mDecisionUseCase) else V1mDecisionUseCase(str(use_case))
    except ValueError:
        return V1mPilotResult(status="unknown_use_case", use_case=str(use_case))

    spec = _DECISION_SPECS[decision]
    if enabled is None:
        enabled = pilot_enabled()
    if not enabled:
        return V1mPilotResult(status="disabled", use_case=decision.value)

    secrets.load_dotenv_once()
    key = secrets.read_setting("V1M_API_KEY")
    if not key:
        return V1mPilotResult(status="not_configured", use_case=decision.value)

    clean = (state or "").strip()[:MAX_STATE_CHARS]
    if not clean:
        return V1mPilotResult(status="invalid_state", use_case=decision.value)

    payload = {
        "model": V1M_MODEL,
        "state": clean,
        "questions": {
            spec.question_id: {
                "type": "choice",
                "instructions": spec.instructions,
                "criteria": spec.criteria,
            }
        },
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    started = time.perf_counter()

    try:
        if transport is not None:
            response = transport(
                "POST",
                V1M_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=timeout_s,
                follow_redirects=False,
            )
        else:
            with httpx.Client(timeout=timeout_s, follow_redirects=False) as client:
                response = client.post(V1M_ENDPOINT, headers=headers, json=payload)
        elapsed = round((time.perf_counter() - started) * 1000.0, 2)

        if response.status_code != 200:
            return V1mPilotResult(status="provider_error", latency_ms=elapsed, use_case=decision.value)
        data = response.json()
        answer = data.get("answers", {}).get(spec.question_id)
        if not isinstance(answer, dict):
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed, use_case=decision.value)
        choice = answer.get("choice")
        probabilities = answer.get("probabilities")
        confidence = answer.get("confidence")
        if (
            answer.get("type") != "choice"
            or choice not in spec.criteria
            or not isinstance(probabilities, dict)
        ):
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed, use_case=decision.value)
        winning_probability = probabilities.get(choice)
        if isinstance(winning_probability, bool) or not isinstance(winning_probability, (int, float)):
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed, use_case=decision.value)
        winning_probability = float(winning_probability)
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = winning_probability
        else:
            confidence = float(confidence)
        if winning_probability < 0.0 or winning_probability > 1.0 or confidence < 0.0 or confidence > 1.0:
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed, use_case=decision.value)
        limit = confidence_threshold() if threshold is None else min(1.0, max(0.0, threshold))
        if confidence >= limit:
            label = choice
        else:
            label = "uncertain"
        return V1mPilotResult(
            status="ok",
            label=label,
            probability=confidence,
            latency_ms=elapsed,
            use_case=decision.value,
        )
    except Exception:
        elapsed = round((time.perf_counter() - started) * 1000.0, 2)
        return V1mPilotResult(status="provider_error", latency_ms=elapsed, use_case=decision.value)


def classify_retrieval_need(
    state: str,
    *,
    enabled: bool | None = None,
    threshold: float | None = None,
    timeout_s: float = 10.0,
    transport: Callable[..., Any] | None = None,
) -> V1mPilotResult:
    """Compatibility wrapper for the retrieval-only pilot."""
    return classify_decision(
        state,
        V1mDecisionUseCase.RETRIEVAL_NEED,
        enabled=enabled,
        threshold=threshold,
        timeout_s=timeout_s,
        transport=transport,
    )
