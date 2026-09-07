"""Agent application service — the thin, safe boundary over the LangGraph agent.

Both a future FastAPI endpoint and tests call this; LangGraph objects never leak
past it. It builds run state, invokes the compiled graph on a fresh random
``run_id`` (also the checkpoint thread id), and returns a safe
:class:`AgentRunResult`. No Streamlit/FastAPI imports.

Phase 5 registers the four real Career tools (thin adapters over
``CareerApplicationService``). Career retrieval is still NOT an agent tool (Phase 6).
Where enough tool data exists, the service builds the existing typed
``PreparationContext`` (reused from ``src/integration``) — never a fabricated one.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from src.agent.errors import AgentConfigurationError, AgentError
from src.agent.graph import build_agent_graph
from src.agent.models import AgentRunRequest, AgentRunResult
from src.agent.registry import ToolRegistry, career_tool_registry
from src.agent.state import STATUS_FAILED

ModelFactory = Callable[[], Any]


def _default_model_factory() -> Any:
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model

    try:
        return build_chat_model(load_config())
    except Exception as exc:  # noqa: BLE001 - map any config/import issue safely
        raise AgentConfigurationError("The assistant isn't configured.") from exc


def _default_career_service() -> Any:
    from src.application.career_service import CareerApplicationService
    from src.copilot.config import load_config

    return CareerApplicationService(load_config())


class AgentApplicationService:
    def __init__(
        self,
        *,
        model_factory: ModelFactory | None = None,
        career_service: Any | None = None,
        registry: ToolRegistry | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        if registry is None:
            registry = career_tool_registry(career_service or _default_career_service())
        self._graph = build_agent_graph(
            model_factory=model_factory or _default_model_factory,
            registry=registry,
            checkpointer=checkpointer,
        )
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
        return run_id in self._owners and self._owners[run_id] == user_id


def _build_preparation_context(state: dict) -> dict | None:
    """Reuse the existing typed PreparationContext when enough tool data exists."""
    target_role = (state.get("target_role") or "").strip()
    requirements = state.get("requirements")
    if not target_role or not requirements:
        return None
    try:
        from src.copilot.tools.schemas import GapAnalysisResult, RoleRequirements
        from src.integration.preparation_context import build_preparation_context

        role = RoleRequirements(**requirements)
        gap_dict = state.get("gaps")
        gap = GapAnalysisResult(**gap_dict) if gap_dict else None
        ctx = build_preparation_context(
            role_requirements=role,
            gap_result=gap,
            target_role=target_role,
            job_description=state.get("job_description"),
        )
        return ctx.model_dump()
    except Exception:  # noqa: BLE001 - never fabricate a context on error
        return None


def _to_result(run_id: str, state: dict, request_id: str | None) -> AgentRunResult:
    messages = state.get("messages", []) or []
    response = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content and getattr(msg, "type", "") in ("ai", "AIMessageChunk", "assistant"):
            response = content if isinstance(content, str) else str(content)
            break
    tool_history = list(state.get("tool_history", []) or [])
    tools_used = [t["tool"] for t in tool_history if t.get("status") == "ok"]
    warnings: list[str] = []
    if state.get("status") == STATUS_FAILED:
        warnings.append("The run did not complete successfully.")
    return AgentRunResult(
        run_id=run_id,
        status=state.get("status", "unknown"),
        response=response,
        events=list(state.get("events", []) or []),
        tool_calls=tool_history,
        tools_used=tools_used,
        sources=list(state.get("evidence", []) or []),
        citations=list(state.get("citations", []) or []),
        retrieval_used=bool(state.get("retrieval_used", False)),
        resolved_occupation=state.get("resolved_occupation"),
        resolved_geography=state.get("resolved_geography"),
        warnings=warnings,
        step_count=int(state.get("step_count", 0)),
        request_id=request_id,
        preparation_context=_build_preparation_context(state),
    )
