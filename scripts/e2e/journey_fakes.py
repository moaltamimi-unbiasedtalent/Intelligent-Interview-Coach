"""Offline fakes for the 04D candidate journey on a REAL local stack (no provider, no network, no paid call).

The real FastAPI application, authorization, persistence, interview state machine, prompting, schema validation and agent graph run; only the model replies are
fixtures. The fixtures come from ``frontend/e2e/journey/fixtures.json``, the SAME file the Playwright mock world reads, so one journey definition sees identical
content in both modes.

* ``FixtureChatClient``  : stands in for the OpenRouter HTTP client of Interview Practice (strategy, question, evaluation, report, deep dive). It answers from the
  strict JSON schema the service itself sends, so it follows schema changes. ``variant="provider_down"`` raises the client's own provider error (a 503), which is the
  honest "provider is unavailable" path through the real routes. It counts calls, so a test can prove nothing was silently retried into duplicates.
* ``ScriptedAgentModel`` : stands in for Mo's chat model (a plain final answer, no tool calls); ``provider_down`` raises, which the agent maps to its safe failure.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from fastapi import Request

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_PATH = ROOT / "frontend" / "e2e" / "journey" / "fixtures.json"

VARIANTS = ("healthy", "provider_down", "keyless")


def load_fixtures() -> dict:
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ schema-driven synthesis

def synthesize(schema: dict, name_hint: str = "value") -> Any:
    """A minimal valid instance of a (strict) JSON schema. Deterministic; strings are labelled fixture text."""
    defs = schema.get("$defs", {})

    def build(node: dict, hint: str) -> Any:
        if "$ref" in node:
            return build(defs[node["$ref"].split("/")[-1]], hint)
        if "anyOf" in node:
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            return build(options[0], hint) if options else None
        if "enum" in node:
            return node["enum"][0]
        kind = node.get("type")
        if kind == "object":
            return {k: build(v, k) for k, v in (node.get("properties") or {}).items()}
        if kind == "array":
            return [build(node.get("items") or {}, hint) for _ in range(max(int(node.get("minItems") or 1), 1))]
        if kind == "integer":
            return max(int(node.get("minimum", 1)), 1) if node.get("minimum") is not None else 1
        if kind == "number":
            return float(node.get("minimum", 1))
        if kind == "boolean":
            return True
        text = f"Offline fixture {hint.replace('_', ' ')}."
        return text.ljust(int(node.get("minLength") or 0), "x")

    return build(schema, name_hint)


class FixtureChatClient:
    """Interview Practice's model client, answered from fixtures. Thread-safe call counting."""

    def __init__(self, variant: str = "healthy", fixtures: dict | None = None, *, capture_prompts: bool = False) -> None:
        if variant not in ("healthy", "provider_down"):
            raise ValueError("FixtureChatClient supports 'healthy' and 'provider_down'; 'keyless' is the absence of a client")
        self.variant = variant
        self._fx = fixtures or load_fixtures()
        self._lock = threading.Lock()
        self.calls: list[str] = []          # schema names, in call order (no content, no secrets)
        self.prompts: list[str] = []        # message text of every call, ONLY when capture_prompts is set (tests that prove which context reached the model)
        self._capture = capture_prompts

    def close(self) -> None:  # parity with the real client
        return None

    @staticmethod
    def _question_number(messages) -> int | None:
        """The service states the question number in its closing instruction ("... for question number N"); reading it keeps the fixture per interview, not per process."""
        for message in reversed(list(messages or [])):
            found = re.search(r"question number (\d+)", str(message.get("content", "")))
            if found:
                return int(found.group(1))
        return None

    def create_chat_completion(self, **kwargs):
        from src.openrouter_client import ChatResult, ServerError

        fmt = kwargs.get("response_format") or {}
        js = fmt.get("json_schema") or {}
        schema_name = js.get("name") or "unknown"
        with self._lock:
            self.calls.append(schema_name)
            if self._capture:
                self.prompts.append("\n".join(str(m.get("content", "")) for m in (kwargs.get("messages") or [])))
            counted = sum(1 for c in self.calls if c == "InterviewQuestion")
        index = self._question_number(kwargs.get("messages")) or counted
        if self.variant == "provider_down":
            raise ServerError("The AI provider is not responding.", status_code=503, category="server")
        iv = self._fx["interview"]
        schema = js.get("schema") or {}
        payload = synthesize(schema, schema_name)
        if schema_name == "InterviewQuestion":
            questions = iv["questions"]
            payload.update({"question_id": index, "question": questions[min(index, len(questions)) - 1], "question_type": "behavioural", "competency": "judgement", "difficulty": "moderate"})
        elif schema_name == "AnswerEvaluation":
            payload.update(iv["evaluation"])
        elif schema_name == "FinalInterviewReport":
            payload.update(iv["report"])
        content = json.dumps(payload, ensure_ascii=False)
        return ChatResult(content=content, model=kwargs.get("model", "fixture"), prompt_tokens=100, completion_tokens=50, total_tokens=150, reported_cost=None,
                          duration_seconds=0.01, request_id="journey-fixture", finish_reason="stop")


def models_fetcher() -> list[dict]:
    """Offline model metadata (no network): every registry profile advertises strict structured outputs, so the service uses the schema-enforced path."""
    from src.llm.models import ModelProfile, model_id

    params = ["temperature", "max_tokens", "response_format", "structured_outputs", "reasoning"]
    return [{"id": model_id(p), "pricing": {"prompt": "0.0000006", "completion": "0.0000018"}, "supported_parameters": params} for p in ModelProfile]


class ScriptedAgentModel:
    """Mo's chat model: a plain final answer (no tool calls) so the REAL agent graph, checkpoint and ownership index run without a provider."""

    def __init__(self, variant: str = "healthy", fixtures: dict | None = None) -> None:
        self.variant = variant
        self._reply = (fixtures or load_fixtures())["mo"]["reply"]
        self.calls = 0
        self._lock = threading.Lock()

    def bind_tools(self, schemas):  # noqa: ANN001
        return self

    def invoke(self, messages):  # noqa: ANN001
        from langchain_core.messages import AIMessage

        with self._lock:
            self.calls += 1
        if self.variant == "provider_down":
            raise RuntimeError("provider unavailable")      # the agent maps any model exception to its safe 'model unavailable' failure
        return AIMessage(content=self._reply)


def install_offline_interview_services(app, variant: str = "healthy", fixtures: dict | None = None, *, capture_prompts: bool = False):
    """Override the app's pricing and Interview Practice services with fixtures (no network, no key). Returns the ``FixtureChatClient`` (to read its call log).

    ``variant="keyless"`` installs only the offline pricing: the real backend then has no key and raises its own "not configured" error, which is the original
    Start Interview failure's environment."""
    from src.api import dependencies as deps
    from src.application.interview_service import InterviewApplicationService
    from src.evaluation_service import EvaluationService
    from src.interview_service import InterviewService
    from src.pricing_service import PricingService
    from src.report_service import ReportService

    pricing = PricingService(models_fetcher=models_fetcher)
    app.dependency_overrides[deps.get_pricing] = lambda: pricing
    if variant == "keyless":
        # get_interview_service resolves pricing by a direct call, so the Depends override alone would not reach it. The service is rebuilt with the offline pricing and NO fake
        # client: the real client then raises its own "no API key" error, the original defect's path, and nothing tries the network.
        def keyless_service(request: Request):
            return InterviewApplicationService(deps.get_app_config(request), pricing=pricing)

        app.dependency_overrides[deps.get_interview_service] = keyless_service
        return None
    client = FixtureChatClient(variant, fixtures, capture_prompts=capture_prompts)
    services = (InterviewService(client, pricing), EvaluationService(client, pricing), ReportService(client, pricing), client)

    def interview_service(request: Request):
        return InterviewApplicationService(deps.get_app_config(request), pricing=pricing, services=services)

    app.dependency_overrides[deps.get_interview_service] = interview_service
    return client


class NoRetrievalCareerService:
    """Stands in for the Career service where a hosted-like offline stack cannot build its vector store. Any use is a loud error, never a silent empty result."""

    def __getattr__(self, name: str):
        raise RuntimeError(f"retrieval is not available in the offline journey stack ({name})")
