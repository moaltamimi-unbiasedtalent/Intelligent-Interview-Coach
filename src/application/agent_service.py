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
from src.agent.human import validate_decision, InvalidHumanDecision
from src.agent.models import AgentRunRequest, AgentRunResult
from src.agent.registry import ToolRegistry, career_tool_registry
from src.agent.state import STATUS_AWAITING_HUMAN, STATUS_COMPLETED, STATUS_FAILED

ModelFactory = Callable[[], Any]


class RunNotFoundError(AgentError):
    """The requested run does not exist or is not owned by the caller."""


class RunNotResumableError(AgentError):
    """The run exists but is not currently awaiting a human decision."""


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
        memory_service: Any | None = None,
        checkpoint_url: str | None = None,
        database_url: str | None = None,
    ) -> None:
        if registry is None:
            registry = career_tool_registry(career_service or _default_career_service())
        # Durable HITL checkpointer (Phase 8). Injectable for tests; otherwise built
        # from configuration (official SQLite/Postgres saver, MemorySaver fallback).
        self._checkpoint_durable = False
        if checkpointer is None:
            from src.agent.checkpoint import build_checkpointer

            info = build_checkpointer(checkpoint_url=checkpoint_url, database_url=database_url)
            checkpointer = info.saver
            self._checkpoint_durable = info.durable
        self._memory_service = memory_service
        self._graph = build_agent_graph(
            model_factory=model_factory or _default_model_factory,
            registry=registry,
            checkpointer=checkpointer,
            memory_service=memory_service,
        )

    @property
    def checkpoint_durable(self) -> bool:
        return self._checkpoint_durable

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _config(run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def _snapshot(self, run_id: str):
        """The current graph StateSnapshot for a run (empty values if unknown)."""
        return self._graph.get_state(self._config(run_id))

    def _load_memory(self, request: AgentRunRequest) -> list[dict]:
        """Deterministically load a bounded set of relevant memories (no model call).

        Never raises into the run: any memory-loading failure degrades to no memory.
        """
        if self._memory_service is None or not request.user_id:
            return []
        try:
            user_id = int(request.user_id)
        except (TypeError, ValueError):
            return []
        try:
            items = self._memory_service.load_for_agent(user_id, request.target_role)
            return [m.to_agent_context() for m in items]
        except Exception:  # noqa: BLE001 - memory is supplemental; never break a run
            return []

    # -- run / resume / lookup ------------------------------------------------

    def run(self, request: AgentRunRequest, *, request_id: str | None = None) -> AgentRunResult:
        run_id = uuid.uuid4().hex
        initial = {
            "run_id": run_id,
            "user_id": request.user_id,
            "goal": request.goal,
            "target_role": request.target_role,
            "job_description": request.job_description,
            "candidate_background": request.candidate_background,
            "memory_items": self._load_memory(request),
            "pending_action": None,
            "human_decisions": [],
            "handoff_approved": False,
            "events": [],
            "tool_history": [],
            "step_count": 0,
        }
        try:
            self._graph.invoke(initial, config=self._config(run_id))
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak a raw error
            raise AgentError("The assistant could not complete the request.") from exc
        # Read authoritative state (detects an interrupt / pending human action).
        return self._result_from_snapshot(run_id, self._snapshot(run_id), request_id)

    def resume(
        self, run_id: str, user_id: str | None, decision: dict, *, request_id: str | None = None
    ) -> AgentRunResult:
        """Continue a paused run on the SAME thread after a validated human decision.

        Ownership is read from the durable checkpoint (survives service recreation);
        the decision is validated against the current pending action BEFORE the graph
        is touched — an invalid decision leaves the run paused and unchanged.
        """
        from langgraph.types import Command

        snapshot = self._snapshot(run_id)
        self._require_owned(snapshot, user_id)
        if not self._is_awaiting(snapshot):
            raise RunNotResumableError("This run is not awaiting a decision.")
        pending = (snapshot.values or {}).get("pending_action")
        try:
            normalised = validate_decision(pending, decision or {})
        except InvalidHumanDecision as exc:
            from src.application.errors import ValidationError

            raise ValidationError(str(exc)) from exc
        try:
            self._graph.invoke(Command(resume=normalised), config=self._config(run_id))
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AgentError("The assistant could not resume the request.") from exc
        return self._result_from_snapshot(run_id, self._snapshot(run_id), request_id)

    def get_run(self, run_id: str, user_id: str | None, *, request_id: str | None = None) -> AgentRunResult:
        snapshot = self._snapshot(run_id)
        self._require_owned(snapshot, user_id)
        return self._result_from_snapshot(run_id, snapshot, request_id)

    # -- ownership / status ---------------------------------------------------

    @staticmethod
    def _is_awaiting(snapshot) -> bool:
        return bool(getattr(snapshot, "next", ()) or ()) and bool(
            (snapshot.values or {}).get("pending_action"))

    def _require_owned(self, snapshot, user_id: str | None) -> None:
        values = getattr(snapshot, "values", None) or {}
        if not values or "user_id" not in values:
            raise RunNotFoundError("Run not found.")
        # Ownership comes from the durable checkpoint, never from the request body.
        if values.get("user_id") != user_id:
            raise RunNotFoundError("Run not found.")

    def owns(self, run_id: str, user_id: str | None) -> bool:
        try:
            self._require_owned(self._snapshot(run_id), user_id)
            return True
        except RunNotFoundError:
            return False

    def _result_from_snapshot(self, run_id, snapshot, request_id) -> AgentRunResult:
        return _to_result(run_id, dict(snapshot.values or {}),
                          request_id, awaiting=self._is_awaiting(snapshot))


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


def _to_result(run_id: str, state: dict, request_id: str | None, *, awaiting: bool = False) -> AgentRunResult:
    messages = state.get("messages", []) or []
    response = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content and getattr(msg, "type", "") in ("ai", "AIMessageChunk", "assistant"):
            response = content if isinstance(content, str) else str(content)
            break
    tool_history = list(state.get("tool_history", []) or [])
    tools_used = [t["tool"] for t in tool_history if t.get("status") == "ok"]
    memory_items = list(state.get("memory_items", []) or [])
    pending_action = state.get("pending_action") if awaiting else None
    if awaiting:
        status = STATUS_AWAITING_HUMAN
    elif state.get("status") in (None, "", "running"):
        status = STATUS_COMPLETED
    else:
        status = state.get("status")
    warnings: list[str] = []
    if status == STATUS_FAILED:
        warnings.append("The run did not complete successfully.")
    return AgentRunResult(
        run_id=run_id,
        status=status,
        response="" if awaiting else response,
        events=list(state.get("events", []) or []),
        tool_calls=tool_history,
        tools_used=tools_used,
        sources=list(state.get("evidence", []) or []),
        citations=list(state.get("citations", []) or []),
        retrieval_used=bool(state.get("retrieval_used", False)),
        resolved_occupation=state.get("resolved_occupation"),
        resolved_geography=state.get("resolved_geography"),
        memory_used=bool(memory_items),
        memory_count=len(memory_items),
        awaiting_human_input=awaiting,
        pending_action=pending_action,
        handoff_approved=bool(state.get("handoff_approved", False)),
        warnings=warnings,
        step_count=int(state.get("step_count", 0)),
        request_id=request_id,
        preparation_context=_build_preparation_context(state),
    )
