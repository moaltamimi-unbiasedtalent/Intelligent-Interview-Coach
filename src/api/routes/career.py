"""Career Intelligence routes — thin adapters over CareerApplicationService.

Each handler maps an API request to the Phase 1 application method and back to a
safe response schema. No Career business logic, retrieval, tools or security
guards are re-implemented here — the guards run inside the application/domain.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import get_career_service
from src.api.schemas.career import (
    CareerChatRequest,
    CareerChatResponse,
    GapAnalysisRequest,
    JobAnalysisRequest,
    PreparationPlanRequest,
    QuestionsRequest,
    ToolResultResponse,
)
from src.application.career_service import CareerApplicationService
from src.application.models import CareerChatRequest as AppCareerChatRequest

router = APIRouter(prefix="/career", tags=["career"])


@router.post("/chat", response_model=CareerChatResponse, summary="Grounded career chat")
def chat(body: CareerChatRequest,
         svc: CareerApplicationService = Depends(get_career_service)) -> CareerChatResponse:
    result = svc.chat(AppCareerChatRequest(
        query=body.question,
        job_description=body.job_description,
        candidate_background=body.candidate_background,
        days_until_interview=body.days_until_interview,
        hours_per_week=body.hours_per_week,
    ))
    return CareerChatResponse.from_orchestration(result)


@router.post("/job-analysis", response_model=ToolResultResponse,
             summary="Analyse a job description")
def job_analysis(body: JobAnalysisRequest,
                 svc: CareerApplicationService = Depends(get_career_service)) -> ToolResultResponse:
    return ToolResultResponse.from_tool_call(svc.analyze_job_description(body.job_description))


@router.post("/gap-analysis", response_model=ToolResultResponse,
             summary="Analyse candidate gaps against a role")
def gap_analysis(body: GapAnalysisRequest,
                 svc: CareerApplicationService = Depends(get_career_service)) -> ToolResultResponse:
    from src.copilot.tools.schemas import RoleRequirements

    role = RoleRequirements(**body.role_requirements)
    return ToolResultResponse.from_tool_call(
        svc.analyze_candidate_gaps(body.candidate_background, role))


@router.post("/preparation-plan", response_model=ToolResultResponse,
             summary="Build a preparation plan")
def preparation_plan(body: PreparationPlanRequest,
                     svc: CareerApplicationService = Depends(get_career_service)) -> ToolResultResponse:
    from src.copilot.tools.schemas import PriorityGap

    gaps = [PriorityGap(**g) for g in body.priority_gaps]
    return ToolResultResponse.from_tool_call(
        svc.build_preparation_plan(gaps, body.days_until_interview, body.hours_per_week))


@router.post("/questions", response_model=ToolResultResponse,
             summary="Generate interview questions")
def questions(body: QuestionsRequest,
              svc: CareerApplicationService = Depends(get_career_service)) -> ToolResultResponse:
    return ToolResultResponse.from_tool_call(
        svc.generate_questions(body.role, body.requirements, body.focus))
