"""FastAPI dependencies: resource lifecycle, auth boundary, request ids.

Resource lifecycle (Phase 2, §18):
- **Application-lifetime** (built once, cached on ``app.state`` under a lock, reused
  across requests): the career config, the interview ``AppConfig``, the expensive
  vector store, the shared translation cache, the pricing service, the repository,
  and the durable interview session store (``DurableInterviewSessionStore``, Phase
  10 — in-progress interviews persist in the database, surviving refresh/restart).
- **Request-scoped** (cheap wrappers built per request over the shared resources):
  ``CareerApplicationService`` and ``InterviewApplicationService``.
- **No global mutable per-user state**: in-progress interview state lives in the
  durable, user-scoped ``interview_sessions`` table, not in process memory.

These are FastAPI dependency functions (no DI container). Tests override them via
``app.dependency_overrides`` so no real provider/DB/vector resources are built.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, Header, HTTPException, Request

from src.application.career_service import CareerApplicationService
from src.application.interview_service import InterviewApplicationService
from src.auth import ANONYMOUS_USER, AuthUser


# --- app-lifetime resource cache --------------------------------------------


def _shared(request: Request, key: str, factory: Callable[[], Any]) -> Any:
    """Return an app-lifetime resource, building it once under the app lock."""
    state = request.app.state
    cache = state.resources
    with state.resources_lock:
        if key not in cache:
            cache[key] = factory()
        return cache[key]


def get_app_config(request: Request):
    """Interview-side ``AppConfig`` (cached for the app lifetime)."""
    from src.config import load_config

    return _shared(request, "app_config", load_config)


def get_copilot_config(request: Request):
    """Career-side ``CopilotConfig`` (cached for the app lifetime)."""
    from src.copilot.config import load_config

    return _shared(request, "copilot_config", load_config)


def get_vector_store(request: Request):
    """The Career vector store — expensive, built once and shared."""
    from src.application import factories

    return _shared(
        request, "vector_store",
        lambda: factories.build_vector_store(get_copilot_config(request)),
    )


def get_translation_cache(request: Request):
    from src.copilot.cache import TTLCache

    def _build():
        cfg = get_copilot_config(request)
        return TTLCache(ttl_seconds=cfg.query_cache_ttl_seconds,
                        max_entries=cfg.query_cache_max_entries)

    return _shared(request, "translation_cache", _build)


def get_pricing(request: Request):
    from src.application import factories

    return _shared(request, "pricing", factories.build_pricing_service)


def get_repository(request: Request):
    """App-lifetime repository over the configured database."""
    from src.application import factories

    return _shared(
        request, "repository",
        lambda: factories.build_repository(get_app_config(request)),
    )


def get_memory_repository(request: Request):
    """App-lifetime preparation-memory repository, sharing the interview DB engine."""
    from src.repository import MemoryRepository

    return _shared(
        request, "memory_repository",
        lambda: MemoryRepository(get_repository(request).session_factory),
    )


def get_memory_service(request: Request):
    """Request-scoped preparation-memory application service (Phase 7)."""
    from src.application.memory_service import MemoryApplicationService

    return MemoryApplicationService(get_memory_repository(request))


def get_session_store(request: Request):
    """The DURABLE, user-scoped interview session store (Sprint 4 Phase 10).

    In-progress interview state is persisted (SessionData serialised to the
    ``interview_sessions`` table) so it survives a browser refresh and a backend
    restart. Built once for the app lifetime over the shared repository engine. The
    old in-process ``InMemorySessionStore`` is no longer the production path (it
    remains for unit tests / legacy Streamlit helpers).
    """
    from src.interview.session_repository import DurableInterviewSessionStore

    return _shared(
        request, "durable_session_store",
        lambda: DurableInterviewSessionStore(get_repository(request).session_factory),
    )


def get_agent_service(request: Request):
    """App-lifetime LangGraph agent application service (experimental, Phase 4).

    The graph is compiled once (no provider call at construction); the model is
    built per run from Career config. Tests override this dependency with a
    fake-model service so no provider is required.
    """
    from src.application.agent_service import AgentApplicationService

    # Inject long-term memory (Phase 7) + a durable HITL checkpointer (Phase 8). The
    # checkpoint DB is derived from AGENT_CHECKPOINT_DATABASE_URL or the app database
    # URL (a dedicated sqlite file / Postgres); it is never exposed to clients.
    def _build():
        from src.agent.errors import AgentConfigurationError
        from src.application.errors import ConfigurationError

        database_url = getattr(get_app_config(request), "database_url", None)
        try:
            return AgentApplicationService(
                memory_service=get_memory_service(request),
                database_url=database_url,
            )
        except AgentConfigurationError as exc:
            # Fail closed: durable checkpointing configured but unavailable → a safe
            # 503 (never a silent transient downgrade). Message carries no URL.
            raise ConfigurationError(str(exc)) from exc

    return _shared(request, "agent_service", _build)


def _session_owned(store, session_id: str, user_id) -> bool:
    """True only if the durable interview session belongs to this user (read-only)."""
    try:
        store.load_state(session_id, user_id)
        return True
    except Exception:  # noqa: BLE001 - not owned / unknown / unreadable → not-found
        return False


def get_feedback_service(request: Request):
    """Request-scoped candidate-feedback service (P5).

    Ownership verifiers prove the rated target belongs to the caller before any
    feedback is accepted: an Agent answer's run must be owned; an interview
    evaluation / final report's session must be owned. A foreign/unknown target is a
    not-found. Feedback events also flow to the (default no-op) observability sink.
    """
    from src.application.feedback_service import FeedbackApplicationService
    from src.repository import FeedbackRepository

    def _agent_owns(target_id: str, user_id: int) -> bool:
        run_id = (target_id or "").split(":", 1)[0]
        try:
            return bool(get_agent_service(request).owns(run_id, str(user_id)))
        except Exception:  # noqa: BLE001 - agent service unavailable → not-found
            return False

    def _session_verifier(target_id: str, user_id: int) -> bool:
        session_id = (target_id or "").split(":", 1)[0]
        return _session_owned(get_session_store(request), session_id, user_id)

    from src.observability import build_observability_sink

    repo = _shared(request, "feedback_repository",
                   lambda: FeedbackRepository(get_repository(request).session_factory))
    obs = _shared(request, "observability", build_observability_sink)
    return FeedbackApplicationService(
        repo,
        target_verifiers={
            "agent_answer": _agent_owns,
            "interview_evaluation": _session_verifier,
            "final_report": _session_verifier,
        },
        observability=obs,
    )


# --- request-scoped application services -------------------------------------


def get_career_service(request: Request) -> CareerApplicationService:
    return CareerApplicationService(
        get_copilot_config(request),
        store=get_vector_store(request),
        translation_cache=get_translation_cache(request),
    )


def get_interview_service(request: Request) -> InterviewApplicationService:
    return InterviewApplicationService(get_app_config(request), pricing=get_pricing(request))


# --- request id --------------------------------------------------------------


def get_request_id(request: Request) -> str:
    """The per-request id set by the request-id middleware."""
    return getattr(request.state, "request_id", "")


# --- auth boundary (transitional) --------------------------------------------


def get_current_user(
    request: Request,
    x_user_subject: str | None = Header(default=None),
    x_user_provider: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
) -> AuthUser:
    """Resolve the caller's identity for data scoping (TRANSITIONAL boundary).

    An ``X-User-Subject`` header (set only by a trusted upstream gateway from verified
    claims, or by a test) selects the user whose data is scoped. It does not grant
    privileges; it only identifies whose records apply.

    **Fail-closed in production:** if no identity is supplied, a non-development
    environment REJECTS the request (401) rather than silently sharing one anonymous
    identity across callers. Development/test keep the convenient anonymous developer
    identity. Production must still place a real authenticating gateway / OIDC in front
    of the API — see docs/sprint4_security_privacy.md.
    """
    if x_user_subject:
        return AuthUser(
            subject=x_user_subject,
            provider=(x_user_provider or "api"),
            display_name=x_user_name,
            email=x_user_email,
        )
    env = str(getattr(getattr(request.app.state, "settings", None), "env", "development")).lower()
    if env not in ("development", "dev", "test", "testing", "local"):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return ANONYMOUS_USER


def get_current_user_id(
    user: AuthUser = Depends(get_current_user),
    repo=Depends(get_repository),
) -> int:
    """Resolve the identity to an internal user id (scopes all history access)."""
    return repo.get_or_create_user(
        subject=user.subject,
        provider=user.provider,
        display_name=user.display_name,
        email=user.email,
    )
