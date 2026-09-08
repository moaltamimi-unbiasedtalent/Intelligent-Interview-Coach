"""FastAPI dependencies: resource lifecycle, auth boundary, request ids.

Resource lifecycle (Phase 2, §18):
- **Application-lifetime** (built once, cached on ``app.state`` under a lock, reused
  across requests): the career config, the interview ``AppConfig``, the expensive
  vector store, the shared translation cache, the pricing service, the repository,
  and the in-memory interview session store.
- **Request-scoped** (cheap wrappers built per request over the shared resources):
  ``CareerApplicationService`` and ``InterviewApplicationService``.
- **No global mutable per-user state** beyond the explicitly user-scoped, bounded
  in-memory session store.

These are FastAPI dependency functions (no DI container). Tests override them via
``app.dependency_overrides`` so no real provider/DB/vector resources are built.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, Header, Request

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
    """The transitional in-memory interview session store (set up in lifespan)."""
    return request.app.state.session_store


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
    x_user_subject: str | None = Header(default=None),
    x_user_provider: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
) -> AuthUser:
    """Resolve the caller's identity for data scoping (TRANSITIONAL boundary).

    In development the anonymous developer identity is used unless an
    ``X-User-Subject`` header is supplied (which lets a trusted upstream gateway —
    or a test — select the user whose data is scoped). This does not grant
    privileges; it only identifies whose records apply. **Production must place a
    real authenticating gateway / OIDC in front of the API and set these headers
    only from verified claims** — see docs/sprint4_architecture.md.
    """
    if x_user_subject:
        return AuthUser(
            subject=x_user_subject,
            provider=(x_user_provider or "api"),
            display_name=x_user_name,
            email=x_user_email,
        )
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
