"""Interview Practice routes over InterviewApplicationService + the session store.

The core linear flow is exposed: create (→ strategy + first question), read state,
submit an answer, advance to the next question (or complete), end early, and
generate/fetch the report. In-progress state lives in the transitional in-memory
session store, scoped to the caller. Deep Dive endpoints are deferred to a later
phase (the application service already supports them; the HTTP surface is not yet
exposed).

No interview business logic, scoring or persistence rules are re-implemented here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request

from src.api.dependencies import (
    get_app_config,
    get_current_user_id,
    get_interview_service,
    get_repository,
    get_session_store,
)
from src.api.schemas.interview import (
    AnswerRequest,
    CreateInterviewRequest,
    InterviewStateResponse,
    QuestionOut,
    ReportResponse,
)
from src.api.session_store import InMemorySessionStore, SessionNotFoundError
from src.application import history_service
from src.application.errors import ValidationError
from src.application.interview_service import InterviewApplicationService
from src.session_manager import SessionManager, SessionState

router = APIRouter(prefix="/interviews", tags=["interviews"])


# --- helpers -----------------------------------------------------------------


def _build_configuration(body: CreateInterviewRequest):
    from pydantic import ValidationError as PydanticValidationError

    from src.integration import handoff
    from src.integration.models import PreparationContext
    from src.models import InterviewConfiguration

    if body.configuration is not None:
        c = body.configuration
        raw = c.model_dump()
    elif body.preparation_context is not None:
        pc = PreparationContext(**body.preparation_context.model_dump())
        store: dict = {}
        handoff.store_context(store, pc)
        prefill = handoff.interview_prefill(store)
        industry = (prefill.get("industry") or body.industry_or_sector or "").strip()
        career_level = (prefill.get("career_level") or body.career_level or "").strip()
        if not industry or not career_level:
            raise ValidationError(
                "The preparation context is missing an industry/sector or career "
                "level; supply 'industry_or_sector' and 'career_level'.")
        raw = {
            "target_role": prefill["target_role"],
            "industry_or_sector": industry,
            "career_level": career_level,
            "interview_types": body.interview_types,
            "interviewer_persona": body.interviewer_persona,
            "difficulty": prefill.get("difficulty") or body.difficulty,
            "response_detail": body.response_detail,
            "job_description": prefill.get("job_description") or None,
            "candidate_background": prefill.get("candidate_background") or None,
            "company_context": prefill.get("company_context") or None,
        }
        if body.number_of_questions is not None:
            raw["number_of_questions"] = body.number_of_questions
    else:
        raise ValidationError(
            "Provide either 'configuration' or 'preparation_context'.")
    raw = {k: v for k, v in raw.items() if v is not None}
    try:
        return InterviewConfiguration(**raw)
    except PydanticValidationError as exc:
        raise ValidationError("Invalid interview configuration.") from exc


def _state(session_id: str, session: SessionManager,
           last_evaluation: dict | None = None) -> InterviewStateResponse:
    data = session.data
    state_value = getattr(data.state, "value", str(data.state))
    current = None
    if data.state == SessionState.AWAITING_ANSWER and data.questions:
        q = data.questions[-1]
        current = QuestionOut(
            question_id=q.question_id, question=q.question,
            question_type=q.question_type, competency=q.competency,
            difficulty=q.difficulty)
    planned = data.config.number_of_questions if data.config else None
    return InterviewStateResponse(
        session_id=session_id,
        state=state_value,
        question_number=data.current_question_number,
        questions_planned=planned,
        current_question=current,
        report_available=data.report is not None,
        last_evaluation=last_evaluation,
    )


def _session(store: InMemorySessionStore, session_id: str, user_id: int) -> SessionManager:
    try:
        backing = store.store_for(session_id, user_id)
    except SessionNotFoundError:
        raise ValidationError("Unknown interview session.") from None
    return SessionManager(store=backing)


# --- routes ------------------------------------------------------------------


@router.post("", response_model=InterviewStateResponse, summary="Create an interview")
def create_interview(
    body: CreateInterviewRequest,
    request: Request,
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: InMemorySessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    from src.models import ModelSettings

    configuration = _build_configuration(body)
    session_id = store.create(user_id)
    session = _session(store, session_id, user_id)
    svc.start_interview(session, configuration, ModelSettings())
    svc.generate_strategy(session)
    svc.generate_next_question(session, first=True)
    return _state(session_id, session)


@router.get("/{session_id}", response_model=InterviewStateResponse,
            summary="Get interview state")
def get_interview(
    session_id: str = Path(...),
    store: InMemorySessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    return _state(session_id, _session(store, session_id, user_id))


@router.post("/{session_id}/answers", response_model=InterviewStateResponse,
             summary="Submit an answer")
def submit_answer(
    body: AnswerRequest,
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: InMemorySessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    session = _session(store, session_id, user_id)
    svc.submit_answer(session, body.answer)
    last = session.data.evaluations[-1].model_dump() if session.data.evaluations else None
    return _state(session_id, session, last_evaluation=last)


@router.post("/{session_id}/next-question", response_model=InterviewStateResponse,
             summary="Advance to the next question (or complete)")
def next_question(
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: InMemorySessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    session = _session(store, session_id, user_id)
    svc.advance(session)
    return _state(session_id, session)


@router.post("/{session_id}/complete", response_model=InterviewStateResponse,
             summary="End the interview early")
def complete_interview(
    session_id: str = Path(...),
    store: InMemorySessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    session = _session(store, session_id, user_id)
    if session.data.state != SessionState.INTERVIEW_COMPLETE:
        session.end_interview_early()
    return _state(session_id, session)


@router.post("/{session_id}/report", response_model=ReportResponse,
             summary="Generate + persist the final report")
def generate_report(
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: InMemorySessionStore = Depends(get_session_store),
    repo=Depends(get_repository),
    config=Depends(get_app_config),
    user_id: int = Depends(get_current_user_id),
) -> ReportResponse:
    session = _session(store, session_id, user_id)
    if session.data.report is None:
        svc.generate_report(session)
    if session.data.report is None:
        raise ValidationError("The report could not be generated yet.")
    history_service.save_completed_interview(
        session, config, repo=repo, user_id=user_id)
    data = session.data
    return ReportResponse(
        session_id=session_id,
        report=data.report.model_dump(),
        saved_report_id=data.saved_report_id,
        save_failed=data.save_failed,
    )


@router.get("/{session_id}/report", response_model=ReportResponse,
            summary="Fetch the generated report")
def get_report(
    session_id: str = Path(...),
    store: InMemorySessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> ReportResponse:
    session = _session(store, session_id, user_id)
    if session.data.report is None:
        raise ValidationError("No report has been generated for this interview.")
    data = session.data
    return ReportResponse(
        session_id=session_id,
        report=data.report.model_dump(),
        saved_report_id=data.saved_report_id,
        save_failed=data.save_failed,
    )
