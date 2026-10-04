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
from src.auth import ANONYMOUS_USER

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
        # Owner-scoped approved-evidence access for the P5 Candidate Evidence specialist.
        # Built over the shared app engine; every read is user-scoped (the specialist
        # only ever receives the trusted run-state user id).
        from src.application.evidence_access_service import EvidenceAccessService
        from src.documents.repository import DocumentRepository, StoryRepository

        session_factory = get_repository(request).session_factory
        evidence_service = EvidenceAccessService(
            documents=DocumentRepository(session_factory),
            stories=StoryRepository(session_factory),
        )
        try:
            from src.privacy.preparation import PreparationRunIndex

            return AgentApplicationService(
                memory_service=get_memory_service(request),
                evidence_service=evidence_service,
                database_url=database_url,
                run_index=PreparationRunIndex(session_factory),
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


def get_governed_retriever(request: Request):
    """Retriever over Admin-governed knowledge (control-plane active set only). Built once; None if it cannot be built."""
    def _build():
        try:
            from src.knowledge_admin.retriever import GovernedKnowledgeRetriever
            from src.knowledge_admin.wiring import build_governed_store

            return GovernedKnowledgeRetriever(build_governed_store(get_copilot_config(request)), get_repository(request).session_factory)
        except Exception:  # noqa: BLE001 - governed knowledge is additive
            return None

    return _shared(request, "governed_retriever", _build)


def get_career_service(request: Request) -> CareerApplicationService:
    return CareerApplicationService(
        get_copilot_config(request),
        store=get_vector_store(request),
        translation_cache=get_translation_cache(request),
        governed_retriever=get_governed_retriever(request),
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


def get_admin_user_repository(repo=Depends(get_repository)):
    from src.admin_repository import AdminUserRepository

    return AdminUserRepository(repo.session_factory)


def get_plan_repository(repo=Depends(get_repository)):
    from src.plans_repository import PlanRepository

    return PlanRepository(repo.session_factory)


def get_entitlement_service(repo=Depends(get_repository)):
    from src.entitlements import EntitlementService

    return EntitlementService(repo.session_factory)


def get_secret_store():
    from src.secret_store import get_secret_store as _get

    return _get()


def get_integration_probes():
    """Probe table (overridable in tests so no real provider is ever contacted)."""
    return None


def get_integration_service(repo=Depends(get_repository), store=Depends(get_secret_store),
                            probes=Depends(get_integration_probes)):
    from src.integrations import IntegrationService

    return IntegrationService(repo.session_factory, store, probes)


def get_job_service(repo=Depends(get_repository)):
    from src.jobs.service import JobService

    return JobService(repo.session_factory)


def get_billing_service(repo=Depends(get_repository)):
    from src.billing.wiring import build_billing_service
    from src.jobs.service import JobService

    return build_billing_service(repo.session_factory, JobService(repo.session_factory))


def get_pause_service(repo=Depends(get_repository)):
    """The DURABLE pause authority for this deployment's environment (P10B-W10.11). Built per request over the shared repository: no process state."""
    from src.application.pause import PauseService

    return PauseService(repo.session_factory)


def get_feature_flag_service(repo=Depends(get_repository)):
    from src.platform_config.flags import FeatureFlagService

    return FeatureFlagService(repo.session_factory)


def get_ai_config_service(repo=Depends(get_repository)):
    from src.ai_admin.resolver import installed
    from src.ai_admin.service import AIConfigService
    from src.jobs.service import JobService

    res = installed()
    # The activation environment is SERVER-authoritative (API_ENV via the resolver); no request field can choose it.
    return AIConfigService(repo.session_factory, jobs=JobService(repo.session_factory), resolver=res, environment=res.environment if res else "from_process")


def get_privacy_request_service(repo=Depends(get_repository)):
    from src.privacy.requests import PrivacyRequestService

    return PrivacyRequestService(repo.session_factory)


def get_legal_service(repo=Depends(get_repository)):
    from src.privacy.legal import LegalService

    return LegalService(repo.session_factory)


def get_knowledge_admin_service(repo=Depends(get_repository)):
    from src.jobs.service import JobService
    from src.knowledge_admin.service import KnowledgeAdminService
    from src.knowledge_admin.wiring import build_knowledge_doc_store

    return KnowledgeAdminService(repo.session_factory, doc_store=build_knowledge_doc_store(),
                                 jobs=JobService(repo.session_factory))


def get_support_repository(repo=Depends(get_repository)):
    from src.support_repository import SupportRepository

    return SupportRepository(repo.session_factory)


def get_audit_repository(repo=Depends(get_repository)):
    from src.auth_repository import AuditRepository

    return AuditRepository(repo.session_factory)


def get_email_sender(request: Request):
    from src.mail import build_email_sender

    return _shared(request, "email_sender", build_email_sender)


# --- Teams / Workspaces & sharing (Capstone P6.5) ----------------------------


def get_workspace_repository(repo=Depends(get_repository)):
    from src.workspace_repository import WorkspaceRepository

    return WorkspaceRepository(repo.session_factory)


def get_workspace_service(
    request: Request,
    workspaces=Depends(get_workspace_repository),
    accounts=Depends(get_account_repository),
    audit=Depends(get_audit_repository),
    email=Depends(get_email_sender),
):
    from src.application.workspace_service import WorkspaceService

    base = getattr(getattr(request.app.state, "settings", None), "app_base_url", None) \
        or "https://app.ask4mo.local"
    return WorkspaceService(workspaces=workspaces, accounts=accounts, audit=audit,
                           email=email, app_base_url=base)


def get_sharing_service(
    request: Request,
    workspaces=Depends(get_workspace_repository),
    audit=Depends(get_audit_repository),
    repo=Depends(get_repository),
):
    # Owner verifiers/loaders for the OPERATIONAL allow-listed shareable resource types.
    # Ownership is ALWAYS checked as the resource OWNER (from the trusted grant), and the
    # loader returns a BOUNDED VIEW projection — a share never bypasses owner scoping and
    # never exposes internal state (usage/prompts/secrets). Interview report + story only;
    # preparation_summary is PLANNED (not in the operational allowlist).
    from src.application.report_export import build_json_export
    from src.application.sharing_service import SharingService
    from src.documents.repository import StoryRepository

    story_repo = StoryRepository(workspaces.session_factory)

    def _story_owns(resource_id: str, owner_user_id: int) -> bool:
        try:
            return story_repo.get(user_id=owner_user_id, story_id=int(resource_id)) is not None
        except (ValueError, TypeError):
            return False

    def _story_load(resource_id: str, owner_user_id: int):
        try:
            return story_repo.get(user_id=owner_user_id, story_id=int(resource_id))
        except (ValueError, TypeError):
            return None

    def _report_owns(resource_id: str, owner_user_id: int) -> bool:
        try:
            return repo.get_interview(owner_user_id, int(resource_id)) is not None
        except (ValueError, TypeError):
            return False

    def _report_load(resource_id: str, owner_user_id: int):
        try:
            detail = repo.get_interview(owner_user_id, int(resource_id))
        except (ValueError, TypeError):
            return None
        if detail is None:
            return None
        # Safe, bounded VIEW projection (no usage/prompt/internal state — same guard the
        # owner's own export uses).
        return build_json_export(detail)

    return SharingService(
        workspaces=workspaces, audit=audit,
        owner_verifiers={"story": _story_owns, "interview_report": _report_owns},
        owner_loaders={"story": _story_load, "interview_report": _report_load},
    )


# --- private candidate documents & evidence (Capstone P4) ---------------------


def get_document_store(request: Request):
    from src.documents.storage import build_document_store

    return _shared(request, "document_store", build_document_store)


def get_ocr_engine(request: Request):
    from src.documents.ocr import build_ocr_engine

    return _shared(request, "ocr_engine", build_ocr_engine)


def get_documents_service(
    repo=Depends(get_repository),
    store=Depends(get_document_store),
    ocr=Depends(get_ocr_engine),
):
    """Owner-scoped documents service (built over injected seams, so tests can override
    the repository, file store or OCR engine independently)."""
    from src.application.documents_service import DocumentsApplicationService
    from src.documents.repository import DocumentRepository, StoryRepository

    sf = repo.session_factory
    return DocumentsApplicationService(
        repo=DocumentRepository(sf),
        stories=StoryRepository(sf),
        store=store,
        ocr=ocr,
    )


def get_stories_service(repo=Depends(get_repository)):
    from src.application.stories_service import StoriesApplicationService
    from src.documents.repository import DocumentRepository, StoryRepository

    sf = repo.session_factory
    return StoriesApplicationService(
        stories=StoryRepository(sf),
        documents=DocumentRepository(sf),
    )


def get_evidence_access_service(repo=Depends(get_repository)):
    """Owner-scoped approved-evidence access (P5) — reused by Practice to compose candidate
    context from APPROVED claims/verified stories only (P10B Wave 4)."""
    from src.application.evidence_access_service import EvidenceAccessService
    from src.documents.repository import DocumentRepository, StoryRepository

    sf = repo.session_factory
    return EvidenceAccessService(documents=DocumentRepository(sf), stories=StoryRepository(sf))


def resolve_document_text(request: Request, *, user_id: int, document_id: int,
                          max_chars: int = 8000) -> str | None:
    """Owner-scoped plain text of a candidate's selected document (P10B Wave 4).

    A shared helper for Prepare (agent run) and Practice (interview create) so a candidate can
    SELECT a stored JD instead of pasting it, WITHOUT the raw text ever travelling via the client.
    Built lazily (only when a document was selected). Returns None for a foreign/missing/unreadable
    document — never another user's data. The caller screens the result as untrusted DATA."""
    from src.application.documents_service import DocumentsApplicationService
    from src.documents.repository import DocumentRepository, StoryRepository

    sf = get_repository(request).session_factory
    svc = DocumentsApplicationService(
        repo=DocumentRepository(sf), stories=StoryRepository(sf),
        store=get_document_store(request), ocr=get_ocr_engine(request),
    )
    return svc.extracted_text(user_id=user_id, document_id=document_id, max_chars=max_chars)


def get_opportunity_service(repo=Depends(get_repository)):
    """Owner-scoped Opportunity service (P10B Wave 6), built over the injected app repository
    (so tests can override the repository/database)."""
    from src.application.opportunity_service import OpportunityApplicationService
    from src.opportunity_repository import OpportunityRepository

    return OpportunityApplicationService(OpportunityRepository(repo.session_factory))


def get_research_service(request: Request):
    """The governed external research engine (P10B Wave 5, reused from Phase 7F).

    Production builds the real, SSRF-safe providers (env-gated; degrade to UNAVAILABLE without
    credentials, so no paid call is ever forced). When ``COMPANY_RESEARCH_FIXTURE`` is truthy the
    deterministic offline fixture provider is used instead (dev demos with 0 live calls). Tests
    override this dependency to inject a fake provider so no network is touched."""
    import os

    def _build():
        from src.copilot.research.service import ExternalResearchService, default_research_service

        raw = (os.environ.get("COMPANY_RESEARCH_FIXTURE", "") or "").strip().lower()
        if raw in ("1", "true", "yes", "on"):
            from src.copilot.research.fake_provider import FakeCompanyResearchProvider

            return ExternalResearchService([FakeCompanyResearchProvider()], enabled=True)
        return default_research_service()

    return _shared(request, "research_service", _build)


def adzuna_credentials_configured() -> bool:
    """Safe, credential-free hint for honest provider status (never exposes the keys)."""
    try:
        from src.copilot.knowledge.providers import adzuna as _adzuna

        return bool(_adzuna.credentials_configured())
    except Exception:  # noqa: BLE001 - status probing must never break a request
        return False


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
        response_detail=account.response_detail,
        interface_locale=account.interface_locale,
        conversation_language=account.conversation_language,
        display_name=account.display_name,
        coaching_style=getattr(account, "coaching_style", "balanced"),
        career_geography=getattr(account, "career_geography", ""),
        target_role=getattr(account, "target_role", ""),
        onboarding_completed=getattr(account, "onboarding_completed", True),
        onboarding_step=getattr(account, "onboarding_step", 0),
        auth_method=auth_method,
    )


def require_platform_admin(principal=Depends(get_current_principal)):
    """DEPRECATED (W10.1): coarse platform-admin gate kept for compatibility. New admin routes MUST use
    ``require_permission``; a CI invariant fails any admin route without an explicit permission."""
    from src.application.authorization import is_platform_admin

    if not is_platform_admin(principal):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return principal


def require_permission(permission: str) -> Callable[..., Any]:
    """Build a dependency that authorizes ONE admin permission (P10B-W10.1; default deny).

    The caller must be authenticated (``get_current_principal``) and have an ACTIVE account; the role is
    read from the server-side account record and resolved to permissions in code
    (``admin_permissions``). Nothing comes from the browser. A denial is audited best-effort, but access
    is denied whether or not that audit write succeeds (a failed audit never grants access).
    The permission string is validated at import time so a typo cannot silently deny everything.
    The returned dependency carries ``.permission`` so a CI invariant can introspect route metadata.
    """
    from src.application.admin_permissions import PERMISSION_SET, permissions_for_role

    if permission not in PERMISSION_SET:
        raise ValueError(f"Unknown admin permission: {permission!r}")

    def _dep(request: Request, principal=Depends(get_current_principal),
             audit=Depends(get_audit_repository)):
        from src.application.admin_audit import record_denial
        from src.persistence import ACCOUNT_STATUS_ACTIVE

        active = principal.status == ACCOUNT_STATUS_ACTIVE
        if active and permission in permissions_for_role(principal.platform_role):
            return principal
        record_denial(
            audit, actor_user_id=principal.user_id, request_id=get_request_id(request),
            permission=permission, method=request.method, path=request.url.path,
            reason="inactive_account" if not active else "missing_permission",
        )
        raise HTTPException(status_code=403, detail="Administrator access required.")

    _dep.permission = permission  # type: ignore[attr-defined]
    return _dep


def require_entitlement(key: str) -> Callable[..., Any]:
    """Build a dependency that enforces a PLAN ENTITLEMENT (P10B-W10.4): the single product-access gate.

    Authorization (ownership, Admin permission) and technical capability stay separate checks; this answers only
    "does the caller's plan grant this feature?". Resolved server-side from the caller's active subscription (or
    the explicit Basic fallback); never from the browser. The key is validated at definition time.
    """
    from src.entitlements import REGISTRY

    if key not in REGISTRY:
        raise ValueError(f"Unknown entitlement key: {key!r}")

    def _dep(principal=Depends(get_current_principal), service=Depends(get_entitlement_service)):
        if not service.is_enabled(principal.user_id, key):
            raise HTTPException(status_code=403, detail="This feature is not included in your plan.")
        return principal

    _dep.entitlement = key  # type: ignore[attr-defined]
    return _dep
