"""Experimental agent route (Sprint 4 preview).

`POST /api/v1/agent/run` invokes the LangGraph foundation agent via the application
service. It is explicitly experimental and does NOT replace `/career/chat`. The run
is scoped to the current user; only safe result data is returned.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.agent.models import AgentRunRequest as AppAgentRunRequest
from src.api.dependencies import get_agent_service, get_current_user_id, get_request_id
from src.api.schemas.agent import AgentRunRequest, AgentRunResponse

router = APIRouter(prefix="/agent", tags=["agent"])


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
        ),
        request_id=request_id,
    )
    return AgentRunResponse(
        run_id=result.run_id,
        status=result.status,
        response=result.response,
        events=result.events,
        tool_calls=result.tool_calls,
        warnings=result.warnings,
        step_count=result.step_count,
    )
