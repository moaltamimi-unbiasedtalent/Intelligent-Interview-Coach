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

# Environments where the transitional dev conveniences (anonymous fallback + the
# X-User-Subject header) are permitted. Any other env (e.g. "production") is
# fail-closed: identity comes only from a trusted session cookie.
DEV_ENVS = ("development", "dev", "test", "testing", "local")


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
    from src.observability import build_observability_sink

    return _shared(
        request, "durable_session_store",
        lambda: DurableInterviewSessionStore(
            get_repository(request).session_factory,
            observability=_shared(request, "observability", build_observability_sink)),
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


def get_feedback_service(request: Request):
    """Request-scoped candidate-feedback service (P5, exact-target validation P5.1).

    Each verifier proves BOTH that the parent resource belongs to the caller AND that
    the EXACT rated output exists — an Agent response with that response_id, an
    Interview question that has a completed evaluation, or a session that has generated
    its final report. A foreign, unknown or nonexistent target is indistinguishable
    (not-found). Verifiers FAIL CLOSED: any parse/service/missing-resource error is
    False, never an ownership grant. Feedback events flow to the (default no-op) sink.
    """
    from src.api.feedback_targets import (
        agent_answer_verifier,
        final_report_verifier,
        interview_evaluation_verifier,
    )
    from src.application.feedback_service import FeedbackApplicationService
    from src.observability import build_observability_sink
    from src.repository import FeedbackRepository

    # Verifiers resolve the owned services lazily so an unavailable service (e.g. a
    # misconfigured agent checkpointer) becomes a not-found, never an ownership grant.
    def _agent(target_id: str, user_id: int) -> bool:
        try:
            svc = get_agent_service(request)
        except Exception:  # noqa: BLE001
            return False
        return agent_answer_verifier(svc)(target_id, user_id)

    def _eval(target_id: str, user_id: int) -> bool:
        return interview_evaluation_verifier(get_session_store(request))(target_id, user_id)

    def _report(target_id: str, user_id: int) -> bool:
        return final_report_verifier(get_session_store(request))(target_id, user_id)

    repo = _shared(request, "feedback_repository",
                   lambda: FeedbackRepository(get_repository(request).session_factory))
    obs = _shared(request, "observability", build_observability_sink)
    return FeedbackApplicationService(
        repo,
        target_verifiers={
            "agent_answer": _agent,
            "interview_evaluation": _eval,
            "final_report": _report,
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


# --- identity/platform resources (Capstone P1/E1) ----------------------------


# These identity repositories are built over the INJECTED repository's session
# factory (via ``Depends(get_repository)``), so a single ``get_repository`` override
# in tests reconfigures the entire auth stack to the test database — the same seam the
# rest of the API uses. They are cheap wrappers over the shared, cached engine.


def get_account_repository(repo=Depends(get_repository)):
    from src.auth_repository import AccountRepository

    return AccountRepository(repo.session_factory)


def get_session_repository(repo=Depends(get_repository)):
    from src.auth_repository import SessionRepository

    return SessionRepository(repo.session_factory)


def get_auth_token_repository(repo=Depends(get_repository)):
    from src.auth_repository import TokenRepository

    return TokenRepository(repo.session_factory)


def get_audit_repository(repo=Depends(get_repository)):
    from src.auth_repository import AuditRepository

    return AuditRepository(repo.session_factory)


def get_email_sender(request: Request):
    from src.mail import build_email_sender

    return _shared(request, "email_sender", build_email_sender)


def get_auth_config(request: Request):
    from src.application.auth_service import AuthConfig

    return _shared(request, "auth_config", AuthConfig.from_env)


def get_oidc_provider(request: Request):
    """The configured social-login provider, or ``None`` when disabled/unconfigured.

    Google login is off unless ``FEATURE_GOOGLE_LOGIN`` is set AND client credentials
    are present. Tests override this dependency with a fake provider to exercise the
    flow deterministically (no live Google call).
    """
    import os

    from src.application.oidc import GoogleOidcProvider, google_enabled

    if not google_enabled():
        return None
    return GoogleOidcProvider(
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    )


def get_auth_service(
    request: Request,
    repo=Depends(get_repository),
    email=Depends(get_email_sender),
):
    """Authentication service over the identity repositories (override-friendly).

    Built from the injected repository so overriding ``get_repository`` (and,
    optionally, ``get_email_sender``) in a test wires the whole service to the test
    database and an in-memory email capture — no separate per-repo overrides needed.
    """
    from src.application.auth_service import AuthenticationService
    from src.auth_repository import (
        AccountRepository,
        AuditRepository,
        SessionRepository,
        TokenRepository,
    )

    sf = repo.session_factory
    return AuthenticationService(
        accounts=AccountRepository(sf),
        sessions=SessionRepository(sf),
        auth_tokens=TokenRepository(sf),
        audit=AuditRepository(sf),
        email=email,
        config=get_auth_config(request),
    )


# --- request id --------------------------------------------------------------


def get_request_id(request: Request) -> str:
    """The per-request id set by the request-id middleware."""
    return getattr(request.state, "request_id", "")


# --- auth boundary (Capstone P1/E1) ------------------------------------------


def _env(request: Request) -> str:
    return str(getattr(getattr(request.app.state, "settings", None), "env", "development")).lower()


def _session_cookie_name(request: Request) -> str:
    try:
        return get_auth_config(request).cookie_name
    except Exception:  # noqa: BLE001 - fall back to the default name
        return "ask4mo_session"


def get_current_user(
    request: Request,
    x_user_subject: str | None = Header(default=None),
    x_user_provider: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
) -> AuthUser:
    """Resolve a header/anonymous identity descriptor (dev/transitional only).

    Retained for the development ``X-User-Subject`` path; the production identity is a
    trusted session cookie resolved in :func:`get_current_user_id`. In a non-dev
    environment with no session cookie, this fails closed (401).
    """
    if x_user_subject and _env(request) in DEV_ENVS:
        return AuthUser(
            subject=x_user_subject,
            provider=(x_user_provider or "api"),
            display_name=x_user_name,
            email=x_user_email,
        )
    if _env(request) not in DEV_ENVS:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return ANONYMOUS_USER


def get_current_user_id(
    request: Request,
    repo=Depends(get_repository),
    x_user_subject: str | None = Header(default=None),
    x_user_provider: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
) -> int:
    """Resolve the caller to an internal user id (scopes ALL user-owned access).

    Resolution order:

    1. **Trusted session cookie** (production AND dev). A valid cookie always wins —
       a user-controlled dev header can never override a real authenticated identity.
       A cookie that is present but invalid/expired is an authentication failure (401),
       never a silent downgrade.
    2. **Dev-only** ``X-User-Subject`` header — accepted ONLY in a development/test
       environment (rejected in production). This is the transitional local-dev seam.
    3. **Anonymous dev fallback** — development/test only.
    4. Otherwise **fail closed** (401).

    ``repo`` is injected (``Depends``) so a test that overrides ``get_repository``
    reconfigures identity resolution too — including the cookie session store, which is
    built over the same injected session factory.
    """
    env = _env(request)
    is_dev = env in DEV_ENVS

    # 1) Trusted server-side session cookie.
    token = request.cookies.get(_session_cookie_name(request))
    if token:
        user_id = _resolve_session_user(repo, token)
        if user_id is not None:
            request.state.auth_method = "session"
            return user_id
        # A supplied-but-invalid session is an authentication failure in every env.
        raise HTTPException(status_code=401, detail="Authentication required.")

    # 2) Dev-only transitional header (never honoured in production).
    if x_user_subject and is_dev:
        request.state.auth_method = "dev_header"
        return repo.get_or_create_user(
            subject=x_user_subject,
            provider=(x_user_provider or "api"),
            display_name=x_user_name,
            email=x_user_email,
        )

    # 3) Anonymous developer identity (dev/test only).
    if is_dev:
        request.state.auth_method = "anonymous"
        return repo.get_or_create_user(
            subject=ANONYMOUS_USER.subject,
            provider=ANONYMOUS_USER.provider,
            display_name=ANONYMOUS_USER.display_name,
            email=ANONYMOUS_USER.email,
        )

    # 4) Production with no session → fail closed.
    raise HTTPException(status_code=401, detail="Authentication required.")


def _resolve_session_user(repo, token: str) -> int | None:
    """Resolve a session cookie to a user id, isolating any resolution failure.

    Only the token's hash is ever used against the store, so a raw session token is
    never logged or compared in plaintext. Any error resolves to ``None`` (no grant).
    """
    from src.auth_repository import SessionRepository
    from src.authsec.tokens import hash_token

    try:
        return SessionRepository(repo.session_factory).resolve(hash_token(token))
    except Exception:  # noqa: BLE001 - a resolution error is never an auth grant
        return None


def get_current_principal(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    account_repo=Depends(get_account_repository),
):
    """Resolve the full authenticated :class:`Principal` (role + tier + status).

    Used by role/entitlement-gated routes. Ownership of candidate resources is still
    enforced separately in the data layer — a platform admin is NOT a data superuser.
    """
    from src.application.authorization import Principal
    from src.persistence import ACCOUNT_STATUS_ACTIVE, PLATFORM_ROLE_USER, TIER_BASIC

    auth_method = getattr(request.state, "auth_method", "session")
    try:
        account = account_repo.get_account(user_id)
    except Exception:  # noqa: BLE001 - default to least privilege on lookup failure
        account = None
    if account is None:
        return Principal(
            user_id=user_id,
            platform_role=PLATFORM_ROLE_USER,
            tier=TIER_BASIC,
            status=ACCOUNT_STATUS_ACTIVE,
            auth_method=auth_method,
        )
    return Principal(
        user_id=account.user_id,
        platform_role=account.platform_role,
        tier=account.tier,
        status=account.status,
        email=account.email,
        email_verified=account.email_verified,
        auth_method=auth_method,
    )


def require_platform_admin(principal=Depends(get_current_principal)):
    """Authorize a platform-admin-only operation (server-side; 403 otherwise)."""
    from src.application.authorization import is_platform_admin

    if not is_platform_admin(principal):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return principal


def require_capability(capability: str) -> Callable[..., Any]:
    """Build a dependency that authorizes a capability from the caller's entitlement."""
    from src.application.authorization import has_capability

    def _dep(principal=Depends(get_current_principal)):
        if not has_capability(principal, capability):
            raise HTTPException(
                status_code=403, detail="This feature requires an upgraded plan."
            )
        return principal

    return _dep
