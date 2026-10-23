"""04C: safe progress via astream_events v2; provider calls remain non-streaming.

Disconnect never cancels an in-flight provider future: it drains, records actual
usage and checkpoints before settlement. A durable cancellation blocks subsequent
model/tool calls. An SSE reconnect only observes the same thread; it never reruns it.
"""
from __future__ import annotations

import asyncio
import json
import time

from src.agent.async_checkpoint import AsyncCheckpointBridge
from src.agent.events import AgentEventType
from src.agent.graph import build_agent_graph
from src.agent.run_control import RunControlStore
from src.application.agent_service import RunNotFoundError

_ALLOWED = {e.value for e in AgentEventType}


def safe_progress(event: dict) -> dict | None:
    """Only code-owned event kinds and bounded scalar metadata, never free text."""
    kind = event.get("event_type")
    if not isinstance(kind, str) or kind not in _ALLOWED:
        return None
    out = {"event_type": kind}
    for key in ("step", "duration_ms", "source_count"):
        value = event.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1_000_000:
            out[key] = value
    # Status/category/message/tool strings are intentionally not forwarded. The
    # candidate progress UI derives its wording solely from event_type.
    return out


def sse(kind: str, data: dict, event_id: int | None = None) -> str:
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return prefix + f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


class AgentStreamingService:
    def __init__(self, service, session_factory, *, timeout_s=180):
        self.service = service
        self.controls = RunControlStore(session_factory)
        self.timeout_s = timeout_s
        self.tasks: set[asyncio.Task] = set()
        self.activity: dict[str, str] = {}
        # 01D's pre-handler probe and the agent node read the same durable facts.
        service._registry.authorizer.set_run_control(self.controls.probe)
        self.graph = build_agent_graph(model_factory=service._model_factory, registry=service._registry,
                                       checkpointer=AsyncCheckpointBridge(service._checkpointer),
                                       memory_service=service._memory_service)

    async def start(self, request, request_id=None) -> str:
        initial = await asyncio.to_thread(self.service._begin_run, request)
        run_id = initial["run_id"]
        await asyncio.to_thread(self.controls.create, run_id, request.user_id, self.timeout_s)
        initial["control_required"] = True
        task = asyncio.create_task(self._produce(initial, request_id))
        self.tasks.add(task)
        def finished(done):
            self.tasks.discard(done)
            if not done.cancelled():
                done.exception()  # consume any store failure without logging raw internals
        task.add_done_callback(finished)
        return run_id

    def require_owned(self, run_id: str, owner: str) -> dict:
        row = self.controls.owned(run_id, owner)
        if row is None:
            raise RunNotFoundError("Run not found.")
        return row

    async def _produce(self, initial, request_id):
        run_id = initial["run_id"]
        lock = self.service._lock_for(run_id)
        claim = asyncio.create_task(asyncio.to_thread(lock.acquire, False))
        try:
            acquired = await asyncio.shield(claim)
        except asyncio.CancelledError:
            # If shutdown wins this tiny acquisition window, the worker still
            # completes; release its claim without ever blocking the event loop.
            def release_claim(done):
                if not done.cancelled() and done.result():
                    lock.release()
            claim.add_done_callback(release_claim)
            await asyncio.shield(asyncio.to_thread(self.controls.interrupt, run_id))
            raise
        if not acquired:
            await asyncio.to_thread(self.controls.finish, run_id, True)
            return
        failed = False
        interrupted = False
        try:
            # Consume all internal events privately. SSE reads only checkpointed,
            # explicit AgentEvents; callback payloads never cross the trust boundary.
            stages = {"agent": "request_understood", "tools": "tool_started", "human_review": "human_input_required"}
            async for event in self.graph.astream_events(initial, config=self.service._config(run_id), version="v2"):
                # Map only code-owned node names to existing safe progress kinds.
                # No callback content, tags, arguments or metadata are copied.
                if event.get("event") == "on_chain_start" and event.get("name") in stages:
                    self.activity[run_id] = stages[event["name"]]
            reason = await asyncio.to_thread(self.service._registry.authorizer.run_control, run_id, True)
            if reason:
                await asyncio.to_thread(self.service._graph.update_state, self.service._config(run_id),
                                        {"status": reason, "cancelled": True, "completed": True})
            snapshot = await asyncio.to_thread(self.service._snapshot, run_id)
            # Capture the settled graph usage itself. Public get_run deliberately
            # labels a still-unsettled Stop as unknown; persisting that overlay
            # here would lose the actual usage just drained from the provider.
            result = await asyncio.to_thread(self.service._result_from_snapshot, run_id, snapshot, request_id)
            await asyncio.to_thread(self.service._record_usage, result, initial["user_id"])
            await asyncio.to_thread(self.service._emit_completed, result)
            await asyncio.to_thread(self.service._mark_run, "ready", run_id)
        except asyncio.CancelledError:
            interrupted = True
            # Process shutdown is different from an HTTP disconnect. Usage may
            # remain unknown; never label an interrupted producer settled.
            await asyncio.shield(asyncio.to_thread(self.controls.interrupt, run_id))
            raise
        except Exception:  # safe terminal record; never publish an exception or raw graph payload
            failed = True
            # A failed/cancelled call may have unreported usage. Preserve unknowns.
            try:
                result = await asyncio.to_thread(self.service.get_run, run_id, initial["user_id"])
                result.usage["usage_complete"] = False
                missing = result.usage.setdefault("missing_usage_sources", [])
                if "stream_interrupted" not in missing:
                    missing.append("stream_interrupted")
                await asyncio.to_thread(self.service._record_usage, result, initial["user_id"])
            except Exception:
                pass
            await asyncio.to_thread(self.service._mark_run, "failed", run_id)
        finally:
            try:
                if not interrupted:
                    await asyncio.to_thread(self.controls.finish, run_id, failed)
            finally:
                self.activity.pop(run_id, None)
                lock.release()

    async def events(self, run_id: str, owner: str, request_id=None, after=-1, serialize=None):
        yield sse("run", {"run_id": run_id})
        cursor = max(-1, min(int(after), 100000))
        last_heartbeat = time.monotonic()
        reported_stop = False
        last_activity = None
        while True:
            # Recheck durable ownership every poll; account deletion removes the
            # control row and stops emission. Foreign and absent ids are identical.
            row = await asyncio.to_thread(self.require_owned, run_id, owner)
            reason = await asyncio.to_thread(self.service._registry.authorizer.run_control, run_id, True)
            try:
                result = await asyncio.to_thread(self.service.get_run, run_id, owner, request_id=request_id)
            except RunNotFoundError:
                result = None  # the first checkpoint may not have committed yet
            stage = self.activity.get(run_id)
            if stage and stage != last_activity:
                yield sse("progress", {"event_type": stage})
                last_activity = stage
            if result:
                for index, event in enumerate(result.events):
                    if index > cursor:
                        projection = safe_progress(event)
                        if projection:
                            yield sse("progress", projection, index)
                        cursor = index
            if row["status"] == "failed" and not row["settled"]:
                yield sse("error", {"code": "agent_stream_interrupted", "run_id": run_id, "settlement_pending": True})
                return
            if row["settled"]:
                if result and row["status"] != "failed":
                    payload = serialize(result) if serialize else {"run_id": result.run_id, "status": result.status}
                    if serialize:
                        payload["events"] = [p for event in result.events if (p := safe_progress(event)) is not None]
                        # Tool history is coarse metadata, never arbitrary model-proposed names.
                        payload["tool_calls"] = [{"tool": item.get("tool") if self.service._registry.has(item.get("tool", "")) else "unregistered",
                                                  "status": item.get("status") if item.get("status") in {"ok", "error", "denied", "rejected"} else "unknown"}
                                                 for item in result.tool_calls]
                    yield sse("result", payload)
                else:
                    yield sse("error", {"code": "agent_stream_failed", "run_id": run_id})
                return
            if reason and not reported_stop:
                yield sse("stopping", {"status": reason, "settlement_pending": True})
                reported_stop = True  # keep observing until usage settles; disconnect never cancels the producer
            if time.monotonic() - last_heartbeat >= 10:
                yield ": keep-alive\n\n"
                last_heartbeat = time.monotonic()
            await asyncio.sleep(0.1)
