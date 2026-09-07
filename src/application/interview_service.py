"""Interview Practice application service (Streamlit-free).

Encapsulates the interview orchestration that used to live in the Streamlit
handlers (``src/interview/studio_app.py``): build the interview/evaluation/report
services, call the unchanged domain, apply the result to the (store-agnostic)
:class:`SessionManager`, and close the client. It performs **no rendering** and
touches **no ``st.session_state``** — the ``SessionManager`` it drives may sit over
Streamlit's session_state (UI) or a plain ``dict`` (tests / a future API).

Scoring, question generation and the session state machine are unchanged; this
class only relocates the glue. Live/Type/Record behaviour is untouched, and Live
remains feature-flagged OFF by default.
"""

from __future__ import annotations

from typing import Any

from src import constants, security, ui_helpers
from src.application.errors import ConfigurationError, ValidationError
from src.application.factories import build_interview_services, build_pricing_service
from src.config import AppConfig
from src.integration import handoff
from src.interview_service import QuestionHistory, ServiceError
from src.session_manager import SessionManager, SessionState


class InterviewApplicationService:
    """Callable Interview Practice operations for any frontend."""

    def __init__(
        self,
        config: AppConfig,
        *,
        pricing: Any | None = None,
        services: tuple | None = None,
    ) -> None:
        self._config = config
        self._pricing = pricing
        # Injected services (tests / reuse) are owned by the caller; internally
        # built services own a fresh client that this class closes per call.
        self._injected = services

    def _build(self):
        if self._injected is not None:
            return self._injected
        pricing = self._pricing or build_pricing_service()
        return build_interview_services(self._config, pricing=pricing)

    def _close(self, client) -> None:
        if self._injected is None:
            client.close()

    def require_configured(self) -> None:
        if not self._config.is_configured:
            raise ConfigurationError(
                "No OpenRouter API key is configured; this action needs a model."
            )

    # -- setup / handoff ------------------------------------------------------

    def preparation_prefill(self, store) -> dict:
        """Editable setup defaults from a stored PreparationContext (or ``{}``)."""
        return handoff.interview_prefill(store)

    def start_interview(self, session: SessionManager, configuration, settings=None):
        """Begin a new interview (state → strategy stage). No provider call."""
        return session.start_new_interview(configuration, settings)

    # -- strategy / questions / answers --------------------------------------

    def generate_strategy(self, session: SessionManager) -> None:
        interview_service, _, _, client = self._build()
        try:
            strategy, usage = interview_service.generate_strategy(
                session.data.config, session.data.settings
            )
            session.save_strategy(strategy)
            session.record_usage(usage)
        except ServiceError as exc:
            session.enter_error(exc.message, recover_to=SessionState.SETUP)
        finally:
            self._close(client)

    def generate_next_question(self, session: SessionManager, *, first: bool = False) -> None:
        interview_service, _, _, client = self._build()
        data = session.data
        history = QuestionHistory(
            questions=list(data.questions),
            answers=list(data.answers),
            evaluations=list(data.evaluations),
        )
        recover = SessionState.STRATEGY_READY if first else SessionState.INTERVIEW_IN_PROGRESS
        try:
            question, usage = interview_service.generate_next_question(
                data.config,
                data.settings,
                current_question_number=len(data.questions) + 1,
                history=history,
            )
            session.add_question(question)
            session.record_usage(usage)
            session.add_chat_message(
                "assistant",
                f"**Question {len(session.data.questions)}** "
                f"({session.data.questions[-1].competency})\n\n{question.question}",
            )
        except ServiceError as exc:
            session.enter_error(exc.message, recover_to=recover)
        finally:
            self._close(client)

    def submit_answer(self, session: SessionManager, answer: str) -> None:
        answer = self._validate_answer(answer)
        _, evaluation_service, _, client = self._build()
        data = session.data
        current_question = data.questions[-1].question
        try:
            session.add_candidate_answer(answer)
            session.add_chat_message("user", answer)
            evaluation, usage = evaluation_service.evaluate_answer(
                data.config, current_question, answer, data.settings
            )
            session.add_evaluation(evaluation)
            session.record_usage(usage)
            session.add_chat_message(
                "assistant",
                f"Recorded — overall score **{evaluation.overall_score}/100**. "
                "Detailed feedback is shown below.",
            )
        except ServiceError as exc:
            session.enter_error(exc.message, recover_to=SessionState.AWAITING_ANSWER)
        finally:
            self._close(client)

    # -- deep dive (branch) ---------------------------------------------------

    def start_deep_dive(self, session: SessionManager, mode: str) -> None:
        session.start_branch(mode)
        self.generate_branch_question(session)

    def generate_branch_question(self, session: SessionManager) -> None:
        interview_service, _, _, client = self._build()
        data = session.data
        depth = len(data.branch_questions) + 1
        try:
            branch_question, usage = interview_service.generate_branch_question(
                data.config,
                data.settings,
                parent_question=data.questions[-1],
                candidate_answer=data.answers[-1],
                evaluation=data.evaluations[-1],
                branch_mode=data.branch_mode,
                depth=depth,
                branch_id=session.next_branch_id(),
                previous_branch_questions=[q.question for q in data.branch_questions],
                previous_branch_answers=list(data.branch_answers),
            )
            session.add_branch_question(branch_question)
            session.record_usage(usage)
            mode_label = ui_helpers.label_for_id(ui_helpers.BRANCH_MODES, data.branch_mode)
            session.add_chat_message(
                "assistant",
                f"🔎 **Deep Dive — Level {branch_question.depth} of "
                f"{constants.MAX_BRANCH_DEPTH}** · {mode_label}\n\n"
                f"{branch_question.question}",
            )
        except ServiceError as exc:
            session.enter_error(exc.message, recover_to=SessionState.INTERVIEW_IN_PROGRESS)
        finally:
            self._close(client)

    def submit_branch_answer(self, session: SessionManager, answer: str) -> None:
        answer = self._validate_answer(answer)
        _, evaluation_service, _, client = self._build()
        data = session.data
        branch_question = data.branch_questions[-1].question
        try:
            session.add_branch_answer(answer)
            session.add_chat_message("user", answer)
            evaluation, usage = evaluation_service.evaluate_answer(
                data.config, branch_question, answer, data.settings
            )
            session.add_branch_evaluation(evaluation)
            session.record_usage(usage)
            session.add_chat_message(
                "assistant",
                f"Deep-dive feedback — overall score "
                f"**{evaluation.overall_score}/100**. See details below.",
            )
        except ServiceError as exc:
            session.enter_error(exc.message, recover_to=SessionState.BRANCH_AWAITING_ANSWER)
        finally:
            self._close(client)

    # -- report ---------------------------------------------------------------

    def generate_report(self, session: SessionManager) -> None:
        _, _, report_service, client = self._build()
        data = session.data
        try:
            report, usage = report_service.generate_report(
                data.config,
                list(data.questions[: len(data.evaluations)]),
                list(data.answers),
                list(data.evaluations),
                data.settings,
            )
            session.save_final_report(report)
            session.record_usage(usage)
        except ServiceError as exc:
            session.enter_error(exc.message, recover_to=SessionState.INTERVIEW_COMPLETE)
        finally:
            self._close(client)

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _validate_answer(answer: str) -> str:
        try:
            return security.validate_field(answer, "candidate_answer")
        except security.InputValidationError as exc:
            raise ValidationError(str(exc)) from exc
