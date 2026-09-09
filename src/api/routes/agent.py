"""Experimental agent route (Sprint 4 preview) with human-in-the-loop.

`POST /api/v1/agent/run` invokes the LangGraph agent via the application service. A
run may pause for a human decision (Phase 8): it returns `awaiting_human_input` with
a safe `pending_action`. The client answers via
`POST /api/v1/agent/runs/{run_id}/resume` (typed decision), which continues the SAME
graph thread. `GET /api/v1/agent/runs/{run_id}` returns the current safe status.

Everything is owner-scoped and does NOT replace `/career/chat`. Only safe result
data is returned — never chain-of-thought, prompts, raw provider output or raw
checkpoint state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from src.agent.models import AgentRunRequest as AppAgentRunRequest
from src.application.agent_service import (
    CheckpointDeleteUnsupportedError,
    RunNotFoundError,
    RunNotResumableError,
)
from src.api.dependencies import get_agent_service, get_current_user_id, get_request_id
from src.api.schemas.agent import (
    AgentContinueRequest,
    AgentRunDeleteResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentUsageResponse,
    HumanDecisionRequest,
)

router = APIRouter(prefix="/agent", tags=["agent"])


def _to_response(result) -> AgentRunResponse:
    usage = AgentUsageResponse(**result.usage) if getattr(result, "usage", None) else None
    return AgentRunResponse(
        run_id=result.run_id,
        status=result.status,
        response=result.response,
        tools_used=result.tools_used,
        retrieval_used=result.retrieval_used,
        sources=result.sources,
        citations=result.citations,
        resolved_occupation=result.resolved_occupation,
        resolved_geography=result.resolved_geography,
        memory_used=result.memory_used,
        memory_count=result.memory_count,
        memory_loaded=result.memory_loaded,
        awaiting_human_input=result.awaiting_human_input,
        pending_action=result.pending_action,
        handoff_approved=result.handoff_approved,
        events=result.events,
        tool_calls=result.tool_calls,
        warnings=result.warnings,
        step_count=result.step_count,
        turn_step_count=result.turn_step_count,
        conversation=result.conversation,
        preparation_context=result.preparation_context,
        usage=usage,
        profile=result.profile,
        latency_ms=result.latency_ms,
        cache_hits=result.cache_hits,
        cache_misses=result.cache_misses,
        journey=result.journey,
        handoff_summary=result.handoff_summary,
    )


@router.post("/run", response_model=AgentRunResponse,
             summary="Run the experimental preparation agent (Sprint 4 preview)")
def run_agent(
    body: AgentRunRequest,
    service=Depends(get_agent_service),
    user_id: int = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
) -> AgentRunResponse:
    result = service.run(
        AppAgentRunRequest(
            goal=body.goal,
            target_role=body.target_role,
            job_description=body.job_description,
            candidate_background=body.candidate_background,
            user_id=str(user_id),
            profile=body.profile,
        ),
        request_id=request_id,
    )
    return _to_response(result)


@router.get("/runs/{run_id}", response_model=AgentRunResponse,
            summary="Get the current safe status of an agent run (owner-scoped)")
def get_agent_run(
    run_id: str = Path(..., min_length=1, max_length=64),
    service=Depends(get_agent_service),
    user_id: int = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
) -> AgentRunResponse:
    try:
        result = service.get_run(run_id, str(user_id), request_id=request_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _to_response(result)


@router.post("/runs/{run_id}/messages", response_model=AgentRunResponse,
             summary="Continue an agent run with a new user message (owner-scoped)")
def continue_agent_run(
    body: AgentContinueRequest,
    run_id: str = Path(..., min_length=1, max_length=64),
    service=Depends(get_agent_service),
    user_id: int = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
) -> AgentRunResponse:
    try:
        result = service.continue_run(run_id, str(user_id), body.message, request_id=request_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found.")
    except RunNotResumableError:
        raise HTTPException(status_code=409, detail="This run cannot accept a new message right now.")
    return _to_response(result)


@router.post("/runs/{run_id}/resume", response_model=AgentRunResponse,
             summary="Resume a paused agent run with a human decision (owner-scoped)")
def resume_agent_run(
    body: HumanDecisionRequest,
    run_id: str = Path(..., min_length=1, max_length=64),
    service=Depends(get_agent_service),
    user_id: int = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
) -> AgentRunResponse:
    decision: dict = {"action_id": body.action_id, "decision": body.decision,
                      "selected_role": body.selected_role}
    # Edit-before-save (APPROVE_MEMORY only): pass the edited memory through for
    # validation in the service. Absent → the originally proposed memory is used.
    if body.memory is not None:
        decision["memory"] = body.memory.model_dump()
    try:
        result = service.resume(run_id, str(user_id), decision, request_id=request_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found.")
    except RunNotResumableError:
        raise HTTPException(status_code=409, detail="This run is not awaiting a decision.")
    return _to_response(result)


@router.delete("/runs/{run_id}", response_model=AgentRunDeleteResponse,
               summary="Delete an owned Coach run's execution/checkpoint thread")
def delete_agent_run(
    run_id: str = Path(..., min_length=1, max_length=64),
    service=Depends(get_agent_service),
    user_id: int = Depends(get_current_user_id),
) -> AgentRunDeleteResponse:
    # Deletes ONLY this run's checkpoint thread — not long-term memory, Interview
    # History or other runs. Foreign/unknown run → 404; unsupported saver → 501
    # (never a fake success).
    try:
        service.delete_run(run_id, str(user_id))
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found.")
    except CheckpointDeleteUnsupportedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return AgentRunDeleteResponse(deleted=True, run_id=run_id)
