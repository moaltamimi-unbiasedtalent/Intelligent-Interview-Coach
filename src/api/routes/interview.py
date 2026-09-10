"""Interview Practice routes over InterviewApplicationService + the DURABLE session store.

The full candidate lifecycle is exposed: create (→ strategy + first question), read
state, submit an answer, advance/complete, Deep Dive (start/answer/next/return),
error recovery, generate/fetch the report, list resumable sessions, and delete.

In-progress state is DURABLE (Sprint 4 Phase 10): it is loaded from and saved to the
``interview_sessions`` table around the unchanged ``SessionManager`` state machine, so
a browser refresh or a backend restart never loses an interview. No interview
business logic, scoring, question generation or state transitions are re-implemented
here — the routes are a thin HTTP boundary over the application service + store.

Concurrency: every state-changing operation saves with optimistic concurrency; a
stale write (another tab/worker) surfaces as HTTP 409, and a provider-backed
operation already in flight is rejected rather than duplicated.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Path, Request

from src import constants
from src.api.dependencies import (
    get_app_config,
    get_current_user_id,
    get_interview_service,
    get_repository,
    get_session_store,
)
from src.api.schemas.interview import (
    ActiveSessionsResponse,
    ActiveSessionSummary,
    AnswerRequest,
    CreateInterviewRequest,
    DeepDiveRequest,
    DeepDiveStateOut,
    InterviewOptionsResponse,
    InterviewStateResponse,
    QuestionOut,
    ReportResponse,
)
from src.application import history_service
from src.application.errors import (
    ConflictError,
    MissingHandoffConfigError,
    UnavailableServiceError,
    ValidationError,
)
from src.application.interview_service import InterviewApplicationService
from src.interview.session_repository import (
    DurableInterviewSessionStore,
    OperationInProgressError,
    SessionConflictError,
    SessionNotFoundError,
)
from src.session_manager import SessionManager, SessionState

router = APIRouter(prefix="/interviews", tags=["interviews"])

_MAX_IDEMPOTENCY_KEY = 200

# States from which a fresh interview setup may still be (re)generated on an
# idempotent retry of a create that stopped halfway (§14) — never resets a real one.
_INCOMPLETE_SETUP = SessionState.SETUP


# --- config building (unchanged behaviour) ----------------------------------


def _build_configuration(body: CreateInterviewRequest):
    from pydantic import ValidationError as PydanticValidationError

    from src.integration import handoff
    from src.integration.models import PreparationContext
    from src.models import InterviewConfiguration

    if body.configuration is not None:
        raw = body.configuration.model_dump()
    elif body.preparation_context is not None:
        pc = PreparationContext(**body.preparation_context.model_dump())
        store: dict = {}
        handoff.store_context(store, pc)
        prefill = handoff.interview_prefill(store)
        industry = (prefill.get("industry") or body.industry_or_sector or "").strip()
        career_level = (prefill.get("career_level") or body.career_level or "").strip()
        if not industry or not career_level:
            # SPECIFIC case (stable code): the context genuinely lacks these fields, so
            # the Coach UI can ask for exactly them. Distinct from any other invalid
            # configuration below, which must NOT be treated as "missing handoff config".
            raise MissingHandoffConfigError(
                "Add the missing industry and career level to start practice.")
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
        raise ValidationError("Provide either 'configuration' or 'preparation_context'.")
    raw = {k: v for k, v in raw.items() if v is not None}
    try:
        return InterviewConfiguration(**raw)
    except PydanticValidationError as exc:
        # A safe, actionable message — never the raw Pydantic detail (which can name
        # private field paths/content). The handoff projection is already bounded to the
        # Interview limits, so a valid approved context reaches here cleanly; this guards
        # genuinely invalid input (e.g. a career level outside the taxonomy).
        raise ValidationError(
            "We couldn't set up practice from these details. Please review the "
            "industry and career level and try again.") from exc


# --- safe response builders --------------------------------------------------


def _eval_out(evaluation) -> dict | None:
    return evaluation.model_dump() if evaluation is not None else None


def _deep_dive_state(session: SessionManager) -> DeepDiveStateOut | None:
    data = session.data
    if not data.branch_active and not data.branch_questions:
        return None
    current = None
    if data.state == SessionState.BRANCH_AWAITING_ANSWER and data.branch_questions:
        bq = data.branch_questions[-1]
        current = {
            "branch_id": bq.branch_id,
            "parent_question_id": bq.parent_question_id,
            "question": bq.question,
            "branch_mode": bq.branch_mode,
            "focus_area": bq.focus_area,
            "difficulty": bq.difficulty,
            "depth": bq.depth,
        }
    last_eval = data.branch_evaluations[-1] if data.branch_evaluations else None
    return DeepDiveStateOut(
        active=bool(data.branch_active),
        mode=data.branch_mode,
        depth=int(data.branch_depth or 0),
        max_depth=constants.MAX_BRANCH_DEPTH,
        parent_question_id=data.branch_parent_question_id,
        current_branch_question=current,
        last_branch_evaluation=_eval_out(last_eval),
        can_go_deeper=session.can_go_deeper(),
    )


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
        target_role=(data.config.target_role if data.config else None),
        deep_dive=_deep_dive_state(session),
        error=data.error,
        error_recoverable=(data.state == SessionState.ERROR and data.previous_state is not None),
        cumulative_cost_usd=round(float(data.cumulative_cost_usd or 0.0), 6),
    )


# --- store-error translation -------------------------------------------------


def _load(store: DurableInterviewSessionStore, session_id: str, user_id: int) -> SessionManager:
    try:
        return store.load_state(session_id, user_id)
    except SessionNotFoundError:
        raise ValidationError("Unknown interview session.") from None


def _translate_store_error(exc: Exception) -> Exception:
    if isinstance(exc, SessionNotFoundError):
        return ValidationError("Unknown interview session.")
    if isinstance(exc, OperationInProgressError):
        return ConflictError(
            "Another step of this interview is already being processed. Please wait a moment.")
    if isinstance(exc, SessionConflictError):
        return ConflictError(
            "This interview session changed in another tab. Reload the latest version.")
    return exc


# --- routes: lifecycle -------------------------------------------------------


def _raise_if_setup_failed(session: SessionManager) -> None:
    """Stop interview setup as soon as a provider-backed step fails.

    ``generate_strategy`` / ``generate_next_question`` catch a provider ``ServiceError``
    by moving the session to ERROR (recording the safe cause) WITHOUT re-raising. If we
    then blindly ran the next step, ``add_question`` would reject the ERROR state and
    raise a confusing "Cannot add a question from state ERROR" that MASKS the real cause.
    Instead, surface the original safe message and stop — the state machine is untouched,
    and because ``store.mutate`` does not persist on exception the durable session stays
    in bare SETUP so an idempotent retry re-runs setup cleanly."""
    if session.data.state is SessionState.ERROR:
        raise UnavailableServiceError(
            session.data.error
            or "We couldn't set up your interview right now. Please try again."
        )


def _run_setup(svc: InterviewApplicationService, session: SessionManager, configuration) -> None:
    from src.models import ModelSettings

    svc.start_interview(session, configuration, ModelSettings())
    svc.generate_strategy(session)
    _raise_if_setup_failed(session)
    svc.generate_next_question(session, first=True)
    _raise_if_setup_failed(session)


@router.post("", response_model=InterviewStateResponse, summary="Create an interview")
def create_interview(
    body: CreateInterviewRequest,
    request: Request,
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> InterviewStateResponse:
    """Create an interview. An optional ``Idempotency-Key`` header makes creation safe
    to retry — a repeat (same user + key) returns the SAME session without re-running
    strategy/first-question generation, and now survives a backend restart (durable)."""
    configuration = _build_configuration(body)

    key = (idempotency_key or "").strip()
    if key:
        if len(key) > _MAX_IDEMPOTENCY_KEY:
            raise ValidationError("The idempotency key is too long.")
        session_id, created = store.create_or_get(user_id, key)
        if not created:
            existing = _load(store, session_id, user_id)
            # A completed-or-in-progress prior create is returned as-is (never reset).
            # Only a create that stopped in bare SETUP with no question is resumed.
            if existing.data.state != _INCOMPLETE_SETUP or existing.data.questions:
                return _state(session_id, existing)
    else:
        session_id = store.create(user_id)

    try:
        with store.mutate(session_id, user_id, operation="create") as session:
            _run_setup(svc, session, configuration)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    return _state(session_id, session)


@router.get("/options", response_model=InterviewOptionsResponse,
            summary="Safe interview taxonomies (career levels, types, deep-dive modes)")
def interview_options() -> InterviewOptionsResponse:
    """The supported taxonomies — the single source of truth for a frontend form
    (never a duplicated client-side list)."""
    return InterviewOptionsResponse(
        career_levels=list(constants.CAREER_LEVELS),
        interview_types=list(constants.INTERVIEW_TYPES),
        difficulty_levels=list(constants.DIFFICULTY_LEVELS),
        deep_dive_modes=list(constants.BRANCH_MODES),
    )


@router.get("", response_model=ActiveSessionsResponse,
            summary="List the current user's resumable in-progress interviews")
def list_active_interviews(
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> ActiveSessionsResponse:
    """Safe summaries only (session id, role, state, progress, updated_at) — never
    JD/background/answers. Completed interviews live in History, not here."""
    summaries = store.list_active(user_id)
    return ActiveSessionsResponse(sessions=[
        ActiveSessionSummary(
            session_id=s.session_id, target_role=s.target_role, state=s.state,
            question_number=s.question_number, questions_planned=s.questions_planned,
            updated_at=s.updated_at)
        for s in summaries
    ])


@router.get("/{session_id}", response_model=InterviewStateResponse, summary="Get interview state")
def get_interview(
    session_id: str = Path(...),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    session = _load(store, session_id, user_id)
    data = session.data
    # On resume, surface the most recent feedback EXCEPT while awaiting a fresh answer
    # (where the prior question's evaluation would be misleading).
    awaiting = data.state in (SessionState.AWAITING_ANSWER, SessionState.BRANCH_AWAITING_ANSWER)
    last = _eval_out(data.evaluations[-1]) if (data.evaluations and not awaiting) else None
    return _state(session_id, session, last_evaluation=last)


@router.delete("/{session_id}", summary="Delete a resumable in-progress interview")
def delete_interview(
    session_id: str = Path(...),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Discard a user-owned in-progress session (idempotency mapping removed with it).
    Completed interview history is never deleted here."""
    store.discard(session_id, user_id)
    return {"deleted": True, "session_id": session_id}


@router.post("/{session_id}/answers", response_model=InterviewStateResponse, summary="Submit an answer")
def submit_answer(
    body: AnswerRequest,
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id, operation="submit_answer") as session:
            svc.submit_answer(session, body.answer)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    last = _eval_out(session.data.evaluations[-1]) if session.data.evaluations else None
    return _state(session_id, session, last_evaluation=last)


@router.post("/{session_id}/next-question", response_model=InterviewStateResponse,
             summary="Advance to the next question (or complete)")
def next_question(
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id, operation="next_question") as session:
            svc.advance(session)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    return _state(session_id, session)


@router.post("/{session_id}/complete", response_model=InterviewStateResponse, summary="End the interview early")
def complete_interview(
    session_id: str = Path(...),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id) as session:
            if session.data.state != SessionState.INTERVIEW_COMPLETE:
                session.end_interview_early()
    except (SessionNotFoundError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    return _state(session_id, session)


@router.post("/{session_id}/recover", response_model=InterviewStateResponse,
             summary="Recover a recoverable ERROR state to its previous state")
def recover_interview(
    session_id: str = Path(...),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    """Return an interview in the recoverable ERROR state to the state it was in before
    the transient failure. The target is the stored ``previous_state`` — never a
    client-chosen state."""
    try:
        with store.mutate(session_id, user_id) as session:
            if session.data.state != SessionState.ERROR:
                raise ValidationError("This interview is not in a recoverable error state.")
            session.recover_from_error()
    except (SessionNotFoundError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    return _state(session_id, session)


# --- routes: Deep Dive (branching) ------------------------------------------


@router.post("/{session_id}/deep-dive", response_model=InterviewStateResponse,
             summary="Start a Deep Dive from the last evaluated answer")
def start_deep_dive(
    body: DeepDiveRequest,
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id, operation="deep_dive") as session:
            svc.start_deep_dive(session, body.mode)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    return _state(session_id, session)


@router.post("/{session_id}/deep-dive/answers", response_model=InterviewStateResponse,
             summary="Submit a Deep Dive answer")
def submit_deep_dive_answer(
    body: AnswerRequest,
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id, operation="deep_dive_answer") as session:
            svc.submit_branch_answer(session, body.answer)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    last = _eval_out(session.data.branch_evaluations[-1]) if session.data.branch_evaluations else None
    return _state(session_id, session, last_evaluation=last)


@router.post("/{session_id}/deep-dive/next", response_model=InterviewStateResponse,
             summary="Go one level deeper in the active Deep Dive")
def next_deep_dive(
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id, operation="deep_dive_next") as session:
            # Enforce the depth/turn rule using the state machine's own predicate
            # BEFORE any provider call (no wasted paid generation, no duplicated logic).
            if not session.can_go_deeper():
                raise ValidationError("No further deep-dive level is available right now.")
            svc.generate_branch_question(session)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    return _state(session_id, session)


@router.post("/{session_id}/deep-dive/return", response_model=InterviewStateResponse,
             summary="Close the Deep Dive and resume the main interview")
def return_from_deep_dive(
    session_id: str = Path(...),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> InterviewStateResponse:
    try:
        with store.mutate(session_id, user_id) as session:
            session.return_to_main_interview()
    except (SessionNotFoundError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    # Returning to the main interview lands on the just-completed main question's
    # evaluation (state is INTERVIEW_IN_PROGRESS, not awaiting), so surface it the
    # same way GET does — otherwise the client has no evaluation to render and the
    # main actions (Next question / End) only appear after a manual reload.
    data = session.data
    awaiting = data.state in (SessionState.AWAITING_ANSWER, SessionState.BRANCH_AWAITING_ANSWER)
    last = _eval_out(data.evaluations[-1]) if (data.evaluations and not awaiting) else None
    return _state(session_id, session, last_evaluation=last)


# --- routes: report ----------------------------------------------------------


@router.post("/{session_id}/report", response_model=ReportResponse,
             summary="Generate + persist the final report")
def generate_report(
    session_id: str = Path(...),
    svc: InterviewApplicationService = Depends(get_interview_service),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    repo=Depends(get_repository),
    config=Depends(get_app_config),
    user_id: int = Depends(get_current_user_id),
) -> ReportResponse:
    """Generate the report if absent (never regenerated once it exists), persist the
    completed interview to History exactly once, and return the result.

    Crash-safe ordering (§9): (A) generate the report and durably persist it into the
    interview session FIRST — so a crash before history save never regenerates the
    model; then (B) idempotently save completed History keyed by the durable
    ``source_session_id`` and repair ``saved_report_id`` in the session. No DB
    transaction is held open while the model generates.
    """
    # A. Generate + durably persist the report (guarded by the operation lease).
    try:
        with store.mutate(session_id, user_id, operation="report") as session:
            if session.data.report is None:
                svc.generate_report(session)
    except (SessionNotFoundError, OperationInProgressError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    if session.data.report is None:
        # Generation failed (state persisted as ERROR); nothing to save to History.
        raise ValidationError("The report could not be generated yet.")

    # B. Idempotently save to completed History + repair saved_report_id in a second,
    #    provider-free save. A crash between the two never duplicates the History row.
    try:
        with store.mutate(session_id, user_id) as session:
            history_service.save_completed_interview(
                session, config, repo=repo, user_id=user_id, source_session_id=session_id)
    except (SessionNotFoundError, SessionConflictError) as exc:
        raise _translate_store_error(exc) from None
    data = session.data
    # §11: report the saved id only when History genuinely holds the row; otherwise the
    # report remains available from durable session state with save_failed=true.
    return ReportResponse(
        session_id=session_id, report=data.report.model_dump(),
        saved_report_id=data.saved_report_id, save_failed=data.save_failed)


@router.get("/{session_id}/report", response_model=ReportResponse, summary="Fetch the generated report")
def get_report(
    session_id: str = Path(...),
    store: DurableInterviewSessionStore = Depends(get_session_store),
    user_id: int = Depends(get_current_user_id),
) -> ReportResponse:
    session = _load(store, session_id, user_id)
    if session.data.report is None:
        raise ValidationError("No report has been generated for this interview.")
    data = session.data
    return ReportResponse(
        session_id=session_id, report=data.report.model_dump(),
        saved_report_id=data.saved_report_id, save_failed=data.save_failed)
