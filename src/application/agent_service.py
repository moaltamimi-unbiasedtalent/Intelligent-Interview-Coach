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

import threading
import time
import uuid
from typing import Any, Callable

from src.agent.errors import AgentConfigurationError, AgentError
from src.agent.graph import build_agent_graph
from src.agent.human import validate_decision, InvalidHumanDecision
from src.agent.models import AgentRunRequest, AgentRunResult
from src.agent.registry import ToolRegistry, career_tool_registry
from src.agent.state import (
    STATUS_AWAITING_HUMAN,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_STEP_LIMIT,
)

# Bounded candidate-safe conversation history returned to the UI (latest N visible
# user/assistant messages — never system/tool/internal messages).
CONVERSATION_LIMIT = 30

ModelFactory = Callable[[], Any]


class RunNotFoundError(AgentError):
    """The requested run does not exist or is not owned by the caller."""


class RunNotResumableError(AgentError):
    """The run exists but is not currently awaiting a human decision."""


class CheckpointDeleteUnsupportedError(AgentError):
    """The configured checkpoint saver does not support safe thread deletion."""


def _resolve_profile(value: Any) -> "Any":
    """Validate a candidate-supplied Agent profile → a ``ModelProfile`` (default Balanced).

    Only the three registry tiers are accepted; a raw provider slug or any other value
    is rejected (never silently honoured), so the browser cannot select an arbitrary
    model. An unset/blank value defaults to Balanced.
    """
    from src.llm.models import ModelProfile

    if value is None or (isinstance(value, str) and not value.strip()):
        return ModelProfile.BALANCED
    if isinstance(value, ModelProfile):
        return value
    text = str(value).strip().lower()
    for profile in ModelProfile:
        if text == profile.value:
            return profile
    from src.application.errors import ValidationError

    raise ValidationError("Unknown model profile.")


def _default_model_factory(profile: "Any" = None) -> Any:
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model
    from src.llm.models import ModelProfile, Workload, spec, workload_profile

    # Use the requested profile (candidate Fast/Balanced/Advanced) or the AGENT
    # workload default (Balanced). The chosen model MUST support tool calling; fail
    # with a safe configuration error rather than silently running without tools.
    chosen = profile if isinstance(profile, ModelProfile) else workload_profile(Workload.AGENT)
    agent_spec = spec(chosen)
    if not agent_spec.supports_tools:
        raise AgentConfigurationError(
            "The configured agent model does not support tool calling.")
    try:
        return build_chat_model(load_config(), model=agent_spec.openrouter_id)
    except AgentConfigurationError:
        raise
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
        checkpoint_durable: bool | None = None,
        memory_service: Any | None = None,
        checkpoint_url: str | None = None,
        database_url: str | None = None,
    ) -> None:
        if registry is None:
            registry = career_tool_registry(career_service or _default_career_service())
        # Durable HITL checkpointer (Phase 8). Injectable for tests; otherwise built
        # from configuration (official SQLite/Postgres saver, MemorySaver fallback,
        # or a fail-closed configuration error when durability is required).
        if checkpointer is None:
            from src.agent.checkpoint import build_checkpointer

            info = build_checkpointer(checkpoint_url=checkpoint_url, database_url=database_url)
            checkpointer = info.saver
            self._checkpoint_durable = info.durable
        else:
            # An injected saver declares its own durability explicitly (never inferred
            # from a class name). Unknown → False, the safe default.
            self._checkpoint_durable = bool(checkpoint_durable)
        self._memory_service = memory_service
        self._checkpointer = checkpointer
        self._graph = build_agent_graph(
            model_factory=model_factory or _default_model_factory,
            registry=registry,
            checkpointer=checkpointer,
            memory_service=memory_service,
        )
        # Smallest-safe per-thread serialization: a resume/continue on one thread must
        # not interleave with another on the SAME thread within this process (in-memory
        # locks; a multi-process deployment would need shared locking — documented).
        self._locks_guard = threading.Lock()
        self._thread_locks: dict[str, threading.Lock] = {}

    def _lock_for(self, run_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._thread_locks.get(run_id)
            if lock is None:
                lock = threading.Lock()
                self._thread_locks[run_id] = lock
            return lock

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
        profile = _resolve_profile(request.profile)
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
            "usage_entries": [],
            "retrieval_cache": [],
            "retrieval_cache_hits": 0,
            "retrieval_cache_misses": 0,
            "warnings": [],
            "step_count": 0,
            "turn_step_count": 0,
            "model_profile": profile.value,
        }
        started = time.perf_counter()
        try:
            self._graph.invoke(initial, config=self._config(run_id))
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak a raw error
            raise AgentError("The assistant could not complete the request.") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        # Read authoritative state (detects an interrupt / pending human action).
        return self._result_from_snapshot(
            run_id, self._snapshot(run_id), request_id, latency_ms=latency_ms)

    def resume(
        self, run_id: str, user_id: str | None, decision: dict, *, request_id: str | None = None
    ) -> AgentRunResult:
        """Continue a paused run on the SAME thread after a validated human decision.

        Ownership is read from the durable checkpoint (survives service recreation);
        the decision is validated against the current pending action BEFORE the graph
        is touched — an invalid decision leaves the run paused and unchanged.
        """
        from langgraph.types import Command

        with self._lock_for(run_id):
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
            started = time.perf_counter()
            try:
                self._graph.invoke(Command(resume=normalised), config=self._config(run_id))
            except AgentError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise AgentError("The assistant could not resume the request.") from exc
            latency_ms = int((time.perf_counter() - started) * 1000)
            return self._result_from_snapshot(
                run_id, self._snapshot(run_id), request_id, latency_ms=latency_ms)

    def continue_run(
        self, run_id: str, user_id: str | None, message: str, *, request_id: str | None = None
    ) -> AgentRunResult:
        """Add a new user message to an existing thread and continue the SAME run.

        This is short-term conversational memory: the checkpointed thread (messages,
        confirmed role, requirements, gaps, plan, evidence, human decisions) is
        preserved; only a NEW bounded per-turn step allowance is granted. It is NOT a
        new run and never bypasses a pending human decision.
        """
        from langchain_core.messages import HumanMessage

        text = (message or "").strip()
        if not text:
            from src.application.errors import ValidationError

            raise ValidationError("A message is required to continue.")

        with self._lock_for(run_id):
            snapshot = self._snapshot(run_id)
            self._require_owned(snapshot, user_id)
            if self._is_awaiting(snapshot):
                # A pending approval must be answered via /resume, never bypassed.
                raise RunNotResumableError("Answer the pending request before continuing.")
            status = (snapshot.values or {}).get("status")
            if status not in (STATUS_COMPLETED, STATUS_STEP_LIMIT):
                raise RunNotResumableError("This run cannot accept a new message yet.")

            # Append the new user turn, reset ONLY the per-turn allowance + terminal
            # flags, and resume at the agent node (as_node="initialise" so the fresh-run
            # initialise does NOT re-run and wipe/duplicate the thread).
            self._graph.update_state(
                self._config(run_id),
                {
                    "messages": [HumanMessage(content=text)],
                    "goal": text,
                    "turn_step_count": 0,
                    "pending_action": None,
                    "completed": False,
                    "status": "running",
                    "last_error": None,
                },
                as_node="initialise",
            )
            started = time.perf_counter()
            try:
                self._graph.invoke(None, config=self._config(run_id))
            except AgentError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise AgentError("The assistant could not continue the request.") from exc
            latency_ms = int((time.perf_counter() - started) * 1000)
            return self._result_from_snapshot(
                run_id, self._snapshot(run_id), request_id, latency_ms=latency_ms)

    def get_run(self, run_id: str, user_id: str | None, *, request_id: str | None = None) -> AgentRunResult:
        snapshot = self._snapshot(run_id)
        self._require_owned(snapshot, user_id)
        return self._result_from_snapshot(run_id, snapshot, request_id)

    @property
    def checkpoint_thread_delete_supported(self) -> bool:
        """Whether the configured saver exposes an official thread-delete API.

        Detected from the saver (never assumed); when false, delete_run refuses rather
        than pretending to delete. We NEVER touch checkpoint tables with raw SQL.
        """
        return callable(getattr(self._checkpointer, "delete_thread", None))

    def delete_run(self, run_id: str, user_id: str | None) -> bool:
        """Delete one owned Agent run's execution/checkpoint thread (P2).

        Deletes ONLY the LangGraph checkpoint thread via the saver's official
        ``delete_thread`` API — never long-term memory, Interview History or another
        run. Ownership is read from the checkpoint; a foreign/unknown run is a
        not-found. Refuses (never fakes success) when the saver has no delete API.
        """
        with self._lock_for(run_id):
            snapshot = self._snapshot(run_id)
            self._require_owned(snapshot, user_id)  # RunNotFoundError if not owned
            if not self.checkpoint_thread_delete_supported:
                raise CheckpointDeleteUnsupportedError(
                    "The configured checkpoint store does not support deleting a run.")
            try:
                self._checkpointer.delete_thread(run_id)
            except AgentError:
                raise
            except Exception as exc:  # noqa: BLE001 - never leak a raw saver error
                raise AgentError("The run could not be deleted.") from exc
            return True

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

    def _result_from_snapshot(self, run_id, snapshot, request_id, *,
                              latency_ms: int | None = None) -> AgentRunResult:
        return _to_result(run_id, dict(snapshot.values or {}),
                          request_id, awaiting=self._is_awaiting(snapshot),
                          latency_ms=latency_ms)


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


def _to_result(run_id: str, state: dict, request_id: str | None, *, awaiting: bool = False,
               latency_ms: int | None = None, profile: str | None = None) -> AgentRunResult:
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
    conversation = _safe_conversation(messages)
    if awaiting:
        status = STATUS_AWAITING_HUMAN
    elif state.get("status") in (None, "", "running"):
        status = STATUS_COMPLETED
    else:
        status = state.get("status")
    # Safe warnings accumulated in state (e.g. an approved memory that failed to
    # persist) plus a terminal-failure note. Never contains raw errors/content.
    warnings: list[str] = list(state.get("warnings") or [])
    if status == STATUS_FAILED:
        warnings.append("The run did not complete successfully.")
    # Output guard (P0.1): apply the shared Sprint-3 output protections to the final
    # answer (redact secret-like strings, flag system-instruction leakage, remove
    # citation markers not backed by THIS run's retrieved evidence), then the
    # agent-specific grounding policy (a safe uncited-retrieval observability warning).
    # Deterministic — no extra model call; provenance only, NOT semantic faithfulness.
    citations = list(state.get("citations", []) or [])
    retrieval_used = bool(state.get("retrieval_used", False))
    if response:
        from src.agent.grounding import guard_agent_answer

        response, grounding_warnings = guard_agent_answer(
            response, citations, retrieval_used=retrieval_used
        )
        warnings.extend(grounding_warnings)
        # Keep the candidate-visible conversation consistent with the grounded answer.
        if conversation and conversation[-1].get("role") == "assistant":
            conversation[-1]["content"] = response
    return AgentRunResult(
        run_id=run_id,
        status=status,
        response="" if awaiting else response,
        events=list(state.get("events", []) or []),
        tool_calls=tool_history,
        tools_used=tools_used,
        sources=list(state.get("evidence", []) or []),
        citations=citations,
        retrieval_used=retrieval_used,
        resolved_occupation=state.get("resolved_occupation"),
        resolved_geography=state.get("resolved_geography"),
        memory_used=bool(memory_items),
        memory_count=len(memory_items),
        memory_loaded=[
            {"category": m.get("category"), "summary": m.get("summary"),
             "target_role": m.get("target_role")}
            for m in memory_items if isinstance(m, dict)
        ],
        awaiting_human_input=awaiting,
        pending_action=pending_action,
        handoff_approved=bool(state.get("handoff_approved", False)),
        warnings=warnings,
        step_count=int(state.get("step_count", 0)),
        turn_step_count=int(state.get("turn_step_count", 0)),
        conversation=conversation,
        request_id=request_id,
        preparation_context=_build_preparation_context(state),
        usage=_aggregate_usage(state),
        latency_ms=latency_ms,
        profile=profile or state.get("model_profile"),
        cache_hits=int(state.get("retrieval_cache_hits", 0) or 0),
        cache_misses=int(state.get("retrieval_cache_misses", 0) or 0),
    )


def _aggregate_usage(state: dict) -> dict:
    """Aggregate the run's safe per-call usage entries into one AgentRunUsage dict."""
    from src.agent.usage import aggregate_usage

    return aggregate_usage(state.get("usage_entries") or []).to_dict()


# The injected long-term-memory DATA block header (see src/agent/nodes.py). Its
# HumanMessage is internal context, never part of the candidate-visible conversation.
_MEMORY_BLOCK_MARKER = "USER-APPROVED PREPARATION MEMORY"


def _safe_conversation(messages: list) -> list[dict[str, Any]]:
    """A bounded, candidate-safe view of the thread: only visible user/assistant text.

    Excludes System prompts, Tool messages, the memory-injection block, and
    assistant messages that carry only tool calls (no visible content). This is what
    the candidate should have seen — never raw LangChain/internal messages.
    """
    convo: list[dict[str, Any]] = []
    for msg in messages:
        mtype = getattr(msg, "type", "")
        content = getattr(msg, "content", None)
        if not isinstance(content, str) or not content.strip():
            continue
        if mtype == "human":
            if content.startswith(_MEMORY_BLOCK_MARKER):
                continue  # internal memory DATA block, not candidate-visible
            convo.append({"role": "user", "content": content})
        elif mtype in ("ai", "AIMessageChunk", "assistant"):
            convo.append({"role": "assistant", "content": content})
    return convo[-CONVERSATION_LIMIT:]
