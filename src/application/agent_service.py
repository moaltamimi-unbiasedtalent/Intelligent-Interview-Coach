"""Agent application service — the thin, safe boundary over the LangGraph agent.

Both a future FastAPI endpoint and tests call this; LangGraph objects never leak
past it. It builds run state, invokes the compiled graph on a fresh random
``run_id`` (also the checkpoint thread id), and returns a safe
:class:`AgentRunResult`. No Streamlit/FastAPI imports.

Phase 4 is a foundation: only the deterministic foundation tool is registered.
Real Career tools are migrated in Phase 5.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from src.agent.errors import AgentConfigurationError, AgentError
from src.agent.graph import build_agent_graph
from src.agent.models import AgentRunRequest, AgentRunResult
from src.agent.registry import ToolRegistry
from src.agent.state import STATUS_FAILED

ModelFactory = Callable[[], Any]


def _default_model_factory() -> Any:
    """Build the tool-calling chat model from Career config; raise a safe agent
    configuration error when no provider is configured."""
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model

    try:
        return build_chat_model(load_config())
    except Exception as exc:  # noqa: BLE001 - map any config/import issue safely
        raise AgentConfigurationError("The assistant isn't configured.") from exc


class AgentApplicationService:
    def __init__(
        self,
        *,
        model_factory: ModelFactory | None = None,
        registry: ToolRegistry | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self._graph = build_agent_graph(
            model_factory=model_factory or _default_model_factory,
            registry=registry,
            checkpointer=checkpointer,
        )
        # run_id -> owner user id, so a future get-run surface can enforce isolation.
        self._owners: dict[str, str | None] = {}

    def run(self, request: AgentRunRequest, *, request_id: str | None = None) -> AgentRunResult:
        run_id = uuid.uuid4().hex
        self._owners[run_id] = request.user_id
        initial = {
            "run_id": run_id,
            "user_id": request.user_id,
            "goal": request.goal,
            "target_role": request.target_role,
            "job_description": request.job_description,
            "candidate_background": request.candidate_background,
            "events": [],
            "tool_history": [],
            "step_count": 0,
        }
        try:
            final = self._graph.invoke(initial, config={"configurable": {"thread_id": run_id}})
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak a raw error
            raise AgentError("The assistant could not complete the request.") from exc

        return _to_result(run_id, final, request_id)

    def owns(self, run_id: str, user_id: str | None) -> bool:
        """Whether ``user_id`` owns ``run_id`` (user-isolation seam)."""
        return run_id in self._owners and self._owners[run_id] == user_id


def _to_result(run_id: str, state: dict, request_id: str | None) -> AgentRunResult:
    messages = state.get("messages", []) or []
    response = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        # The final answer is the last AI/assistant message with text content.
        if content and getattr(msg, "type", "") in ("ai", "AIMessageChunk", "assistant"):
            response = content if isinstance(content, str) else str(content)
            break
    tool_history = state.get("tool_history", []) or []
    warnings: list[str] = []
    if state.get("status") == STATUS_FAILED:
        warnings.append("The run did not complete successfully.")
    return AgentRunResult(
        run_id=run_id,
        status=state.get("status", "unknown"),
        response=response,
        events=list(state.get("events", []) or []),
        tool_calls=list(tool_history),
        sources=[],
        warnings=warnings,
        step_count=int(state.get("step_count", 0)),
        request_id=request_id,
    )
