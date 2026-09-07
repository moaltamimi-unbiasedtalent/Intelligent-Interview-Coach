"""Career Intelligence application service (Streamlit-free).

Thin façade over the existing ``src/copilot`` domain: it constructs the career
service and tool invoker via Streamlit-free factories, calls the unchanged domain
methods, and returns typed results. It performs **no rendering** and touches **no
``st.session_state``**.

Returned from :meth:`chat` is the domain :class:`OrchestrationResult`. Its
``.response`` (a Pydantic ``ChatResponse``) is the safe, serialisable shape for a
future JSON API — it deliberately excludes the pipeline trace and the
handoff-only ``preparation_artifacts`` (those stay in-process for the RAG
Inspector and the Career→Interview handoff respectively).
"""

from __future__ import annotations

from typing import Any

from src.application.errors import UnavailableServiceError
from src.application.factories import build_career_service, build_tool_invoker
from src.application.models import CareerChatRequest, ToolCallResult
from src.copilot import constants
from src.copilot.config import CopilotConfig
from src.core.errors import SafeError


class CareerApplicationService:
    """Callable Career Intelligence operations for any frontend."""

    def __init__(
        self,
        config: CopilotConfig,
        *,
        store: Any | None = None,
        translation_cache: Any | None = None,
        service: Any | None = None,
        tool_invoker: Any | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._translation_cache = translation_cache
        self._service = service  # injectable for tests / reuse
        self._tool_invoker = tool_invoker

    # -- chat / RAG -----------------------------------------------------------

    def chat(self, request: CareerChatRequest, *, progress=None):
        """Run one grounded Career chat turn. Returns ``OrchestrationResult``.

        Validation and the prompt-injection guard run inside the domain service
        exactly as before. Unexpected downstream failures are translated into a
        safe :class:`UnavailableServiceError`; the domain's own safe results
        (e.g. an injection refusal) are returned normally.
        """
        service = self._service or build_career_service(
            self._config,
            store=self._store,
            translation_cache=self._translation_cache,
            retrieval_mode=request.retrieval_mode,
        )
        try:
            return service.answer(
                request.query,
                job_description=request.job_description,
                candidate_background=request.candidate_background,
                days_until_interview=request.days_until_interview,
                hours_per_week=request.hours_per_week,
                company_context=request.company_context,
                model=request.model,
                progress=progress,
            )
        except SafeError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak a raw stack trace
            raise UnavailableServiceError(
                "The career assistant is temporarily unavailable. Please try again."
            ) from exc

    def plan(self, request: CareerChatRequest):
        """Deterministic, free preview of what a query would trigger (no LLM)."""
        service = self._service or build_career_service(
            self._config, store=self._store,
            translation_cache=self._translation_cache,
            retrieval_mode=request.retrieval_mode,
        )
        return service.plan(
            request.query,
            job_description=request.job_description,
            candidate_background=request.candidate_background,
            days_until_interview=request.days_until_interview,
            hours_per_week=request.hours_per_week,
        )

    # -- domain tools ---------------------------------------------------------

    def _invoke(self, name: str, args: dict) -> ToolCallResult:
        invoker = self._tool_invoker or build_tool_invoker(self._config)
        result = invoker.invoke(name, args)
        return ToolCallResult(
            value=result.result if result.ok else None,
            execution=result.execution,
            ok=result.ok,
            error=result.execution.error if not result.ok else None,
        )

    def analyze_job_description(self, job_description: str) -> ToolCallResult:
        return self._invoke(constants.TOOL_JOB_ANALYZER,
                            {"job_description": job_description})

    def analyze_candidate_gaps(self, candidate_background: str,
                               role_requirements) -> ToolCallResult:
        return self._invoke(
            constants.TOOL_GAP_ANALYZER,
            {"candidate_background": candidate_background,
             "role_requirements": role_requirements.model_dump()},
        )

    def build_preparation_plan(self, priority_gaps, days_until_interview: int,
                               hours_per_week: float) -> ToolCallResult:
        return self._invoke(
            constants.TOOL_PREP_PLANNER,
            {"priority_gaps": [g.model_dump() for g in priority_gaps],
             "days_until_interview": int(days_until_interview),
             "hours_per_week": float(hours_per_week)},
        )

    def generate_questions(self, role: str, requirements: list[str],
                           focus: list[str]) -> ToolCallResult:
        return self._invoke(
            constants.TOOL_QUESTION_GENERATOR,
            {"role": role, "requirements": requirements, "focus": focus},
        )
