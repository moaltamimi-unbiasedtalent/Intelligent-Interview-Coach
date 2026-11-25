"""Opt-in V1M System One pilot for bounded retrieval-need classification.

This module is advisory and never changes career routing or synthesis.
The default is disabled; live use is explicitly enabled by the operator.
Only a 512-character synthetic or user query is sent by the caller.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from src.core import secrets

V1M_ENDPOINT = "https://v1m.ir/v1/systemone"
V1M_MODEL = "rev-latest"
PILOT_ENABLED = "V1M_PILOT_ENABLED"
PILOT_THRESHOLD = "V1M_PILOT_CONFIDENCE_THRESHOLD"
DEFAULT_THRESHOLD = 0.85
MAX_STATE_CHARS = 512


@dataclass(frozen=True)
class V1mPilotResult:
    status: str
    label: str | None = None
    probability: float | None = None
    latency_ms: float | None = None


def pilot_enabled(environ: dict[str, str] | None = None) -> bool:
    if environ is None:
        return secrets.read_bool(PILOT_ENABLED, default=False)
    raw = environ.get(PILOT_ENABLED, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def confidence_threshold() -> float:
    raw = secrets.read_float(PILOT_THRESHOLD, DEFAULT_THRESHOLD)
    return min(1.0, max(0.0, raw))


def classify_retrieval_need(
    state: str,
    *,
    enabled: bool | None = None,
    threshold: float | None = None,
    timeout_s: float = 10.0,
    transport: Callable[..., Any] | None = None,
) -> V1mPilotResult:
    """Classify whether a bounded state needs career retrieval.

    Returns a safe unavailable result on every configuration, HTTP, or response
    failure. It never raises provider text or affects the caller's route.
    """
    if enabled is None:
        enabled = pilot_enabled()
    if not enabled:
        return V1mPilotResult(status="disabled")

    secrets.load_dotenv_once()
    key = secrets.read_setting("V1M_API_KEY")
    if not key:
        return V1mPilotResult(status="not_configured")

    clean = (state or "").strip()[:MAX_STATE_CHARS]
    if not clean:
        return V1mPilotResult(status="invalid_state")

    payload = {
        "model": V1M_MODEL,
        "state": clean,
        "questions": {
            "retrieval_needed": {
                "type": "choice",
                "instructions": (
                    "Does this question need verified career knowledge, role, "
                    "skills, labour-market, qualification, or interview evidence?"
                ),
                "criteria": {
                    "retrieval_needed": "The state needs verified career evidence or knowledge retrieval.",
                    "retrieval_not_needed": "The state is only a greeting, acknowledgement, or interface instruction.",
                },
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
            return V1mPilotResult(status="provider_error", latency_ms=elapsed)
        data = response.json()
        answer = data.get("answers", {}).get("retrieval_needed")
        if not isinstance(answer, dict):
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed)
        choice = answer.get("choice")
        probabilities = answer.get("probabilities")
        confidence = answer.get("confidence")
        if (
            answer.get("type") != "choice"
            or choice not in {"retrieval_needed", "retrieval_not_needed"}
            or not isinstance(probabilities, dict)
        ):
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed)
        winning_probability = probabilities.get(choice)
        if isinstance(winning_probability, bool) or not isinstance(winning_probability, (int, float)):
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed)
        winning_probability = float(winning_probability)
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = winning_probability
        else:
            confidence = float(confidence)
        if winning_probability < 0.0 or winning_probability > 1.0 or confidence < 0.0 or confidence > 1.0:
            return V1mPilotResult(status="invalid_response", latency_ms=elapsed)
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
        )
    except Exception:
        elapsed = round((time.perf_counter() - started) * 1000.0, 2)
        return V1mPilotResult(status="provider_error", latency_ms=elapsed)
