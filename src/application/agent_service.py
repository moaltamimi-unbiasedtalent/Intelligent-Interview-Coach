"""Agent application service — the thin, safe boundary over the LangGraph agent.

Both a future FastAPI endpoint and tests call this; LangGraph objects never leak
past it. It builds run state, invokes the compiled graph on a fresh random
``run_id`` (also the checkpoint thread id), and returns a safe
:class:`AgentRunResult`. No Streamlit/FastAPI imports.

The service runs the allow-listed tool set defined by ``career_tool_registry``
(``src/agent/registry.py``, the source of truth for tool names and counts): Career tools (thin
adapters over ``CareerApplicationService``, including retrieval-only ``SearchCareerKnowledge``),
three bounded specialist tools and two human-action tools.
Where enough tool data exists, the service builds the existing typed
``PreparationContext`` (reused from ``src/integration``) — never a fabricated one.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

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


def _resolve_language(value: Any) -> str | None:
    """Validate a candidate-supplied conversation language against the allow-list.

    Returns a supported locale code, or None (English/default) for anything unknown or
    blank. Never honours arbitrary text — the value can only ever set the language of
    Mo's prose, and only from this bounded set.
    """
    from src.agent.policies import RESPONSE_LANGUAGE_NAMES

    if value is None:
        return None
    code = str(value).strip().lower()
    return code if code in RESPONSE_LANGUAGE_NAMES else None


def _resolve_coaching_style(value: Any) -> str | None:
    """Validate a candidate-supplied coaching style against the bounded allow-list.

    Returns a supported style, or None (balanced/default → no directive) for anything unknown or
    blank. Never honours arbitrary text — it can only ever set the TONE of Mo's coaching prose,
    and only from this bounded set; it never affects scoring, evidence or grounding.
    """
    from src.coaching_style import COACHING_STYLES

    if value is None:
        return None
    code = str(value).strip().lower()
    return code if code in COACHING_STYLES else None


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
        # P10B-W10.7: governed ORCHESTRATION tunables (only an explicit numeric override; null/absent = inherit the real default) reach the real chat model.
        from src.llm.policy import ModelOperation
        from src.llm.runtime import tunables

        tuned = tunables(ModelOperation.ORCHESTRATION)
        extra: dict = {}
        if "max_output_tokens" in tuned:
            extra["max_tokens"] = int(tuned["max_output_tokens"])
        if "timeout_s" in tuned:
            extra["timeout_s"] = float(tuned["timeout_s"])
        if "max_retries" in tuned:
            extra["max_retries"] = int(tuned["max_retries"])
        return build_chat_model(load_config(), model=agent_spec.openrouter_id, **extra)
    except AgentConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001 - map any config/import issue safely
        raise AgentConfigurationError("The assistant isn't configured.") from exc


def _default_career_service() -> Any:
    from src.application.career_service import CareerApplicationService
    from src.copilot.config import load_config

    return CareerApplicationService(load_config())


@dataclass
class _Admission:
    snapshot: Any = None
    controlled: bool = False
    started: bool = False
    accounted: bool = True
    result: AgentRunResult | None = None


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
        evidence_service: Any | None = None,
        checkpoint_url: str | None = None,
        database_url: str | None = None,
        observability: Any | None = None,
        run_index: Any | None = None,
        usage_session_factory: Any | None = None,
    ) -> None:
        # P10B-W10.12: canonical AI usage capture (one cumulative aggregate per run). None = no capture (tests / offline).
        self._usage_sf = usage_session_factory
        # PRIV-W9-01: durable ownership index for NEW preparation runs (None keeps the previous behaviour for tests).
        self._run_index = run_index
        if registry is None:
            # The owner-scoped evidence service (P5) is threaded to the Candidate
            # Evidence specialist tool; None keeps a safe empty selection.
            registry = career_tool_registry(
                career_service or _default_career_service(), evidence_service=evidence_service)
        # Durable HITL checkpointer (Phase 8). Injectable for tests; otherwise built
        # from configuration (official SQLite/Postgres saver, MemorySaver fallback,
        # or a fail-closed configuration error when durability is required).
        if checkpointer is None:
            from src.agent.checkpoint import build_checkpointer

            info = build_checkpointer(checkpoint_url=checkpoint_url, database_url=database_url)
            self._checkpoint_resource = info  # retain the official saver connection context
            checkpointer = info.saver
            self._checkpoint_durable = info.durable
        else:
            # An injected saver declares its own durability explicitly (never inferred
            # from a class name). Unknown → False, the safe default.
            self._checkpoint_durable = bool(checkpoint_durable)
        self._memory_service = memory_service
        self._checkpointer = checkpointer
        if observability is None:
            from src.observability import build_observability_sink

            observability = build_observability_sink()
        self._obs = observability
        self._registry = registry
        self._model_factory = model_factory or _default_model_factory
        self._streaming = None
        sf = self._usage_sf or getattr(self._run_index, "_sf", None)
        if sf is not None:
            from src.agent.run_control import RunControlStore
            registry.authorizer.set_run_control(RunControlStore(sf).probe)
        self._graph = build_agent_graph(
            model_factory=model_factory or _default_model_factory,
            registry=registry,
            checkpointer=checkpointer,
            memory_service=memory_service,
        )
        # Smallest-safe per-thread serialization: a resume/continue on one thread must
        # not interleave with another on the SAME thread within this process (in-memory
        # locks; the durable admission row is the cross-process authority).
        self._locks_guard = threading.Lock()
        self._thread_locks: dict[str, threading.Lock] = {}

    def _emit_started(self, run_id: str, profile: str) -> None:
        try:
            self._obs.run_started(run_id=run_id, profile=profile)
        except Exception:  # noqa: BLE001 - telemetry is non-critical, never breaks a run
            pass

    def _record_usage(self, result: AgentRunResult, user_id: Any) -> bool:
        """Upsert this run's CUMULATIVE usage aggregate once (never per nested tool call). Best-effort: never raises."""
        if self._usage_sf is None:
            return True
        try:
            from src.reporting.telemetry import record_agent_usage

            return record_agent_usage(self._usage_sf, user_id, result.run_id, result.usage, result.profile)
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _unsettled_result(result: AgentRunResult) -> None:
        result.usage["usage_complete"] = False
        result.usage["estimated_cost_usd"] = None
        missing = result.usage.setdefault("missing_usage_sources", [])
        if "producer_unsettled" not in missing:
            missing.append("producer_unsettled")

    @staticmethod
    def _stop_result(result: AgentRunResult, reason: str) -> None:
        result.status = reason
        result.response = ""
        result.pending_action = None
        result.awaiting_human_input = False
        result.handoff_approved = False
        if result.conversation and result.conversation[-1].get("role") == "assistant":
            result.conversation = result.conversation[:-1]

    def _account_turn(self, result: AgentRunResult, user_id: Any) -> bool:
        accounted = self._record_usage(result, user_id) is not False
        if not accounted:
            self._unsettled_result(result)
            result.status = STATUS_FAILED
        return accounted

    def _emit_completed(self, result: AgentRunResult) -> None:
        """Emit a SANITISED completion trace (safe fields only). Never raises."""
        try:
            from src.observability import safe_hitl_event, safe_tool_events, safe_trace_projection

            for ev in safe_tool_events(result):
                self._obs.tool_event(
                    run_id=result.run_id, tool_name=ev.get("tool_name") or "",
                    status=ev.get("status") or "", failure_category=ev.get("failure_category"))
            hitl = safe_hitl_event(result)
            if hitl:
                self._obs.hitl_event(run_id=result.run_id, hitl_type=hitl["hitl_type"],
                                     status=hitl["status"])
            self._obs.run_completed(run_id=result.run_id, projection=safe_trace_projection(result))
        except Exception:  # noqa: BLE001 - telemetry is non-critical, never breaks a run
            pass

    def _lock_for(self, run_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._thread_locks.get(run_id)
            if lock is None:
                lock = threading.Lock()
                self._thread_locks[run_id] = lock
            return lock

    @contextmanager
    def _admit_producer(self, run_id: str, user_id: str | None, *, initial=None):
        """DB admission is authoritative; the local lock is defense in depth.

        Re-read the checkpoint AFTER claiming. Hold through final canonical usage.
        No expiry-based takeover: process loss leaves the run explicitly unsettled.
        """
        from src.agent.run_control import RunAdmissionConflict, RunControlStore

        # Authenticate ownership even when this instance's producer is busy.
        # A foreign/absent id must remain a 404, never an existence-revealing 409.
        if initial is None:
            self._require_owned(self._snapshot(run_id), user_id)
        lock = self._lock_for(run_id)
        if not lock.acquire(blocking=False):
            raise RunNotResumableError("This run is busy.")
        control, previous = None, None
        admission = _Admission()
        try:
            snapshot = None if initial is not None else self._snapshot(run_id)
            if snapshot is not None:
                self._require_owned(snapshot, user_id)
            required = bool(snapshot and snapshot.values.get("control_required"))
            sf = self._usage_sf or getattr(self._run_index, "_sf", None)
            try:
                if sf is not None:
                    store = RunControlStore(sf)
                    if initial is not None:
                        if store.available():
                            store.create(run_id, user_id)
                            control = store
                            initial["control_required"] = True
                    else:
                        previous = store.claim(run_id, user_id, required=required)
                        if previous is not None:
                            control = store
                elif required:
                    raise RunAdmissionConflict()
            except RunAdmissionConflict as exc:
                raise RunNotResumableError("This run is busy or unavailable.") from exc
            except Exception as exc:
                raise AgentConfigurationError("Durable agent admission is unavailable.") from exc
            admission.controlled = control is not None
            # The earlier snapshot may be stale if a different producer finished
            # before our atomic claim. Never validate a human decision on it.
            admission.snapshot = None if initial is not None else self._snapshot(run_id)
            if admission.snapshot is not None:
                self._require_owned(admission.snapshot, user_id)
            try:
                yield admission
            except BaseException:
                if control is not None:
                    if not admission.started and previous is not None:
                        control.release_unstarted(run_id, user_id, previous)
                    else:
                        control.interrupt(run_id)
                        try:
                            result = self._result_from_snapshot(run_id, self._snapshot(run_id), None)
                            self._unsettled_result(result)
                            self._record_usage(result, user_id)
                        except Exception:
                            pass  # the durable unsettled row still prevents unsafe reuse
                raise
            else:
                if control is not None:
                    if admission.accounted:
                        control.finish(run_id)
                        row = control.owned(run_id, user_id)
                        if admission.result is not None and row and row["status"] in ("cancelled", "expired", "failed"):
                            self._stop_result(admission.result, row["status"])
                    else:
                        control.interrupt(run_id)
                        self._mark_run("failed", run_id)
        finally:
            lock.release()

    def _mark_run(self, state: str, run_id: str) -> None:
        if self._run_index is not None:
            try:
                self._run_index.mark(run_id, state)
            except Exception:  # noqa: BLE001 - lifecycle bookkeeping must never break a run
                pass

    def _ensure_indexed(self, run_id: str, user_id: str | None) -> None:
        """Lazy indexing of a historical run, ONLY after the checkpoint proved this caller owns it."""
        if self._run_index is not None and user_id is not None:
            try:
                self._run_index.register(run_id, int(user_id), source="lazy")
            except Exception:  # noqa: BLE001
                pass

    def purge_run(self, run_id: str) -> bool:
        """Delete one run's checkpoint thread by id. The CALLER must already have established ownership (the ownership index);
        used by account deletion. Uses the saver's official delete API only; refuses (never fakes success) if unsupported."""
        with self._lock_for(run_id):
            if not self.checkpoint_thread_delete_supported:
                raise CheckpointDeleteUnsupportedError("The configured checkpoint store does not support deleting a run.")
            self._checkpointer.delete_thread(run_id)
            return True

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

    def _begin_run(self, request: AgentRunRequest) -> dict:
        """Shared owner/index/initial-state admission for synchronous and streaming runs."""
        run_id = uuid.uuid4().hex
        profile = _resolve_profile(request.profile)
        # Server-enforced capability toggle (#16): when the user turns current-market
        # research OFF, withhold ResearchCurrentMarket from the whole run. Default
        # (None) preserves existing behaviour; the model can never re-enable it.
        disabled_tools = (
            ["ResearchCurrentMarket"]
            if getattr(request, "enable_current_market_research", None) is False
            else []
        )
        initial = {
            "run_id": run_id,
            "user_id": request.user_id,
            "goal": request.goal,
            "target_role": request.target_role,
            "job_description": request.job_description,
            "candidate_background": request.candidate_background,
            "disabled_tools": disabled_tools,
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
            "response_language": _resolve_language(
                getattr(request, "conversation_language", None)
            ),
            "coaching_style": _resolve_coaching_style(
                getattr(request, "coaching_style", None)
            ),
        }
        # Ownership is recorded BEFORE the durable checkpoint exists (SQL and the checkpoint store cannot be atomic, so the safe
        # order is index first). Fail closed: no untracked checkpoint is ever created for a new run.
        if self._run_index is not None:
            try:
                self._run_index.register(run_id, int(request.user_id))
            except Exception as exc:  # noqa: BLE001
                raise AgentError("The assistant could not start the request.") from exc
        self._emit_started(run_id, profile.value)
        return initial

    def streaming(self):
        """Streaming requires the existing application's durable ownership/session factory."""
        if self._streaming is None:
            sf = self._usage_sf or getattr(self._run_index, "_sf", None)
            if sf is None:
                raise AgentConfigurationError("Agent streaming is unavailable in this environment.")
            # Refuse before run admission when an existing database has not
            # received additive migration 0048; synchronous runs stay available.
            from sqlalchemy import inspect
            try:
                with sf() as session:
                    available = inspect(session.get_bind()).has_table("agent_run_controls")
            except Exception as exc:
                raise AgentConfigurationError("Agent streaming is unavailable in this environment.") from exc
            if not available:
                raise AgentConfigurationError("Agent streaming requires its control-table migration.")
            from src.application.agent_streaming import AgentStreamingService
            self._streaming = AgentStreamingService(self, sf)
        return self._streaming

    def run(self, request: AgentRunRequest, *, request_id: str | None = None) -> AgentRunResult:
        initial = self._begin_run(request)
        run_id = initial["run_id"]
        with self._admit_producer(run_id, request.user_id, initial=initial) as admission:
            admission.started = True
            started = time.perf_counter()
            try:
                self._graph.invoke(initial, config=self._config(run_id))
            except AgentError:
                self._mark_run("failed", run_id)
                raise
            except Exception as exc:  # noqa: BLE001 - never leak a raw error
                self._mark_run("failed", run_id)
                raise AgentError("The assistant could not complete the request.") from exc
            self._mark_run("ready", run_id)
            latency_ms = int((time.perf_counter() - started) * 1000)
            # Read authoritative state (detects an interrupt / pending human action).
            result = self._result_from_snapshot(
                run_id, self._snapshot(run_id), request_id, latency_ms=latency_ms)
            self._emit_completed(result)
            admission.accounted = self._account_turn(result, request.user_id)
            admission.result = result
            return result

    def resume(
        self, run_id: str, user_id: str | None, decision: dict, *, request_id: str | None = None
    ) -> AgentRunResult:
        """Continue a paused run on the SAME thread after a validated human decision.

        Ownership is read from the durable checkpoint (survives service recreation);
        the decision is validated against the current pending action BEFORE the graph
        is touched — an invalid decision leaves the run paused and unchanged.
        """
        from langgraph.types import Command

        with self._admit_producer(run_id, user_id) as admission:
            snapshot = admission.snapshot
            if self._registry.authorizer.run_control(run_id, required=bool(snapshot.values.get("control_required"))):
                raise RunNotResumableError("This run was stopped.")
            self._ensure_indexed(run_id, user_id)
            if not self._is_awaiting(snapshot):
                raise RunNotResumableError("This run is not awaiting a decision.")
            pending = (snapshot.values or {}).get("pending_action")
            try:
                normalised = validate_decision(pending, decision or {})
            except InvalidHumanDecision as exc:
                from src.application.errors import ValidationError

                raise ValidationError(str(exc)) from exc
            admission.started = True
            if admission.controlled and not snapshot.values.get("control_required"):
                self._graph.update_state(self._config(run_id), {"control_required": True})
            started = time.perf_counter()
            try:
                self._graph.invoke(Command(resume=normalised), config=self._config(run_id))
            except AgentError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise AgentError("The assistant could not resume the request.") from exc
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = self._result_from_snapshot(
                run_id, self._snapshot(run_id), request_id, latency_ms=latency_ms)
            self._emit_completed(result)
            admission.accounted = self._account_turn(result, user_id)
            admission.result = result
            return result

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

        with self._admit_producer(run_id, user_id) as admission:
            snapshot = admission.snapshot
            if self._registry.authorizer.run_control(run_id, required=bool(snapshot.values.get("control_required"))):
                raise RunNotResumableError("This run was stopped.")
            self._ensure_indexed(run_id, user_id)
            if self._is_awaiting(snapshot):
                # A pending approval must be answered via /resume, never bypassed.
                raise RunNotResumableError("Answer the pending request before continuing.")
            status = (snapshot.values or {}).get("status")
            if status not in (STATUS_COMPLETED, STATUS_STEP_LIMIT):
                raise RunNotResumableError("This run cannot accept a new message yet.")

            # Append the new user turn, reset ONLY the per-turn allowance + terminal
            # flags, and resume at the agent node (as_node="initialise" so the fresh-run
            # initialise does NOT re-run and wipe/duplicate the thread).
            admission.started = True
            self._graph.update_state(
                self._config(run_id),
                {
                    "control_required": admission.controlled,
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
            result = self._result_from_snapshot(
                run_id, self._snapshot(run_id), request_id, latency_ms=latency_ms)
            self._emit_completed(result)
            admission.accounted = self._account_turn(result, user_id)
            admission.result = result
            return result

    def get_run(self, run_id: str, user_id: str | None, *, request_id: str | None = None) -> AgentRunResult:
        snapshot = self._snapshot(run_id)
        self._require_owned(snapshot, user_id)
        self._ensure_indexed(run_id, user_id)
        result = self._result_from_snapshot(run_id, snapshot, request_id)
        if snapshot.values.get("control_required"):
            reason = self._registry.authorizer.run_control(run_id, required=True)
            from src.agent.run_control import RunControlStore
            sf = self._usage_sf or getattr(self._run_index, "_sf", None)
            row = RunControlStore(sf).owned(run_id, user_id) if sf is not None else None
            if row is not None and row["status"] == "failed" and not row["settled"]:
                reason = "failed"
            if reason:
                # Cancellation may win the final control-row transaction just
                # after graph completion. Read that durable decision on every
                # lookup, never expose a completed action after Stop won.
                self._stop_result(result, reason)
            if row is None or not row["settled"]:
                self._unsettled_result(result)
                if "stream_settlement_pending" not in result.usage["missing_usage_sources"]:
                    result.usage["missing_usage_sources"].append("stream_settlement_pending")
        return result

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
            self._ensure_indexed(run_id, user_id)
            if not self.checkpoint_thread_delete_supported:
                raise CheckpointDeleteUnsupportedError(
                    "The configured checkpoint store does not support deleting a run.")
            try:
                self._checkpointer.delete_thread(run_id)
            except AgentError:
                raise
            except Exception as exc:  # noqa: BLE001 - never leak a raw saver error
                raise AgentError("The run could not be deleted.") from exc
            if self._run_index is not None:
                try:
                    self._run_index.remove(run_id)
                except Exception:  # noqa: BLE001
                    pass
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
    conversation = _safe_conversation(messages, run_id)
    if awaiting:
        status = STATUS_AWAITING_HUMAN
    elif state.get("status") in (None, ""):
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
    response_class, policy_flags = None, []
    result_sources = list(state.get("evidence", []) or [])
    if response:
        from src.agent.grounding import guard_agent_answer

        response, grounding_warnings = guard_agent_answer(
            response, citations, retrieval_used=retrieval_used
        )
        warnings.extend(grounding_warnings)
        from src.agent.grounding import apply_candidate_policy

        human = [str(getattr(m, "content", "") or "") for m in messages if getattr(m, "type", "") == "human"]
        tool_text = " ".join(str(getattr(m, "content", "") or "") for m in messages if getattr(m, "type", "") == "tool")
        outcome = apply_candidate_policy(
            response, citations=citations, evidence=list(state.get("evidence", []) or []), query=human[-1] if human else "",
            resolved_geography=state.get("resolved_geography"), retrieval_used=retrieval_used, language=state.get("response_language"),
            allowed_text=" ".join(human + [tool_text]), completed=(status == STATUS_COMPLETED),
        )
        response, policy_warnings, response_class, policy_flags = outcome.answer, outcome.warnings, outcome.response_class, outcome.flags
        if outcome.removed_markers:
            # Keep inline markers, citation metadata and displayed sources consistent: a citation the policy removed from the answer must not survive as a supporting reference.
            gone = set(outcome.removed_markers)
            aligned = len(state.get("evidence", []) or []) == len(citations)
            if aligned:
                result_sources = [e for e, c in zip(list(state.get("evidence", []) or []), citations) if str(c.get("marker")) not in gone]
            citations = [c for c in citations if str(c.get("marker")) not in gone]
        warnings.extend(policy_warnings)
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
        sources=result_sources,
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
        journey=_derive_journey(state),
        handoff_summary=_derive_handoff_summary(state),
        specialist_outputs=_derive_specialist_outputs(state),
        response_class=response_class,
        policy_flags=policy_flags,
        failure_code=_failure_code(state) if status == STATUS_FAILED else None,
        prompt_versions=_run_prompt_versions(state, tools_used),
    )


def _failure_code(state: dict) -> str | None:
    """The stable cause code of a failed run (04D): 'not configured' and 'provider unavailable' are different facts. Any other cause stays None."""
    from src import constants

    return {"not_configured": constants.AI_NOT_CONFIGURED, "model_unavailable": constants.AI_PROVIDER_UNAVAILABLE}.get(str(state.get("last_error") or ""))


def _run_prompt_versions(state: dict, tools_used: list[str]) -> dict:
    """Effective prompt asset versions (declared version + body hash) for the run (01B R6).

    Metadata only, never prompt text. The prompt tree was validated at import (the application
    fails closed otherwise), so this read cannot fail on a running process.
    """
    from src.agent.policies import run_prompt_versions

    return run_prompt_versions(
        state.get("response_language"), tools_used, state.get("coaching_style")
    )


def _derive_specialist_outputs(state: dict) -> dict:
    """Safe projection of the P5 specialists that ran this run (for the diagnostic).

    Includes only bounded structured outputs already stored in state (role brief,
    owner-scoped evidence selection, coaching plan) plus the list of specialists that
    produced output. Never raw documents, secrets or chain-of-thought.
    """
    role_brief = state.get("role_brief")
    evidence_selection = state.get("evidence_selection")
    coaching_plan = state.get("coaching_plan")
    used: list[str] = []
    if role_brief:
        used.append("role_opportunity")
    if evidence_selection:
        used.append("candidate_evidence")
    if coaching_plan:
        used.append("interview_strategy")
    if not used:
        return {}
    return {
        "specialists_used": used,
        "role_brief": role_brief,
        "evidence_selection": evidence_selection,
        "coaching_plan": coaching_plan,
    }


def _derive_journey(state: dict) -> dict:
    from src.agent.journey import derive_journey

    return derive_journey(state)


def _derive_handoff_summary(state: dict) -> dict | None:
    from src.agent.journey import derive_handoff_summary

    return derive_handoff_summary(state)


def _aggregate_usage(state: dict) -> dict:
    """Aggregate the run's safe per-call usage entries into one AgentRunUsage dict."""
    from src.agent.usage import aggregate_usage

    return aggregate_usage(state.get("usage_entries") or []).to_dict()


# The injected long-term-memory DATA block header (see src/agent/nodes.py). Its
# HumanMessage is internal context, never part of the candidate-visible conversation.
_MEMORY_BLOCK_MARKER = "USER-APPROVED PREPARATION MEMORY"


def _safe_conversation(messages: list, run_id: str) -> list[dict[str, Any]]:
    """A bounded, candidate-safe view of the thread: only visible user/assistant text.

    Excludes System prompts, Tool messages, the memory-injection block, and
    assistant messages that carry only tool calls (no visible content). This is what
    the candidate should have seen — never raw LangChain/internal messages.

    Each assistant answer carries a stable, candidate-safe ``response_id``
    (``<run_id>:<absolute assistant index>``) so feedback can identify the EXACT answer
    even when a run has several answers. The index is absolute over the full thread
    (assigned before the bounded tail is taken), so it never shifts when older turns
    scroll out of the projection — and it is NOT a hash of the answer content (P5 §8).
    """
    convo: list[dict[str, Any]] = []
    assistant_index = 0
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
            assistant_index += 1
            convo.append({"role": "assistant", "content": content,
                          "response_id": f"{run_id}:{assistant_index}"})
    return convo[-CONVERSATION_LIMIT:]
