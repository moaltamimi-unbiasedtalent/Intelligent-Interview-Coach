"""Structured-output producer built on the OpenRouter chat model via LangChain.

Turns a chat model into a callable that returns a validated Pydantic instance,
using LangChain's ``with_structured_output``. Injectable so the LLM-backed tools
can be tested without any network call.
"""

from __future__ import annotations

from typing import Any, Callable

from src.copilot import constants
from src.copilot.config import CopilotConfig
from src.copilot.tools.errors import ToolDependencyError

__all__ = ["StructuredProducer", "build_structured_producer"]

#: A producer maps chat messages to a validated schema instance.
StructuredProducer = Callable[[list[dict]], Any]

_ROLE_MAP = {"system": "system", "user": "human", "assistant": "ai"}


def build_structured_producer(
    config: CopilotConfig | None,
    schema: type,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = constants.STRUCTURED_MAX_OUTPUT_TOKENS,
) -> StructuredProducer:
    """Build a structured-output producer for ``schema`` over OpenRouter.

    ``max_tokens`` defaults to a generous structured budget so multi-field results
    (e.g. RoleRequirements, InterviewQuestionSet) are not truncated — a small cap
    yields a ``LengthFinishReasonError`` from the structured-output parser.
    """
    if config is None:
        raise ToolDependencyError(
            "This tool needs a configured model. Provide a producer or a config "
            "with an OpenRouter API key."
        )
    from src.copilot.llm.openrouter import CopilotConfigError, build_chat_model

    # P10B-W10.7: governed STRUCTURED_GENERATION tunables (only when an active configuration changed them) reach the real chat model.
    from src.llm.policy import ModelOperation
    from src.llm.runtime import tunables

    tuned = tunables(ModelOperation.STRUCTURED_GENERATION)
    extra: dict = {}
    if "timeout_s" in tuned:
        extra["timeout_s"] = float(tuned["timeout_s"])
    if "max_retries" in tuned:
        extra["max_retries"] = int(tuned["max_retries"])
    if "max_output_tokens" in tuned:
        max_tokens = int(tuned["max_output_tokens"])
    try:
        chat_model = build_chat_model(
            config, model=model, temperature=temperature, max_tokens=max_tokens, **extra
        )
    except CopilotConfigError as exc:
        raise ToolDependencyError(str(exc)) from exc

    structured = chat_model.with_structured_output(schema)

    def produce(messages: list[dict]) -> Any:
        lc_messages = [(_ROLE_MAP.get(m["role"], "human"), m["content"]) for m in messages]
        return structured.invoke(lc_messages)

    return produce
