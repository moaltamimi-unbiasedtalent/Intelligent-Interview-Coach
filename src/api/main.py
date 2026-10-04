"""FastAPI application for Intelligent Interview Coach.

A thin, typed HTTP layer over the Streamlit-free application services
(``src/application``). It orchestrates HTTP concerns only — no Career/Interview/
RAG/persistence/RAGAS/security logic is duplicated here. The Streamlit UI keeps
working independently; both call the same application layer.

Run locally:
    uvicorn src.api.main:app --reload

Base path: /api/v1  (plus /api/health for infra liveness).
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import API_PREFIX, ApiSettings
from src.api.exception_handlers import register_exception_handlers
from src.api.middleware import (
    CatchAllErrorMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from src.api.routes import (
    admin,
    admin_ai,
    admin_billing,
    admin_integrations,
    admin_jobs,
    admin_knowledge,
    admin_legal,
    admin_privacy,
    admin_plans,
    admin_support,
    agent,
    auth,
    career,
    company,
    documents,
    evaluation,
    feedback,
    health,
    history,
    interview,
    knowledge,
    memory,
    opportunity,
    privacy,
    progress,
    support,
    reviewer,
    voice,
    workspaces,
)
from src.api.session_store import InMemorySessionStore

logger = logging.getLogger("api")

TAGS_METADATA = [
    {"name": "health", "description": "Liveness, readiness and safe capabilities."},
    {"name": "career", "description": "Grounded career guidance and domain tools."},
    {"name": "interviews", "description": "Interview practice sessions and reports."},
    {"name": "history", "description": "The caller's saved interviews (user-scoped)."},
    {"name": "knowledge", "description": "Read-only knowledge-base status."},
    {"name": "evaluation", "description": "Read-only evaluation status (no paid runs)."},
    {"name": "agent", "description": "Experimental LangGraph preparation agent (Sprint 4 preview)."},
    {"name": "memory", "description": "User-scoped long-term preparation memory (Sprint 4 Phase 7)."},
    {"name": "auth", "description": "Accounts, authentication, sessions and account lifecycle (Capstone P1/E1)."},
    {"name": "documents", "description": "Private candidate documents, evidence, story bank and report export (Capstone P4)."},
    {"name": "reviewer", "description": "PLATFORM_ADMIN-gated knowledge/retention/Prompt Lab diagnostics (Capstone P6)."},
    {"name": "workspaces", "description": "Teams/workspaces, membership, invitations and explicit sharing (Capstone P6.5)."},
    {"name": "admin", "description": "PLATFORM_ADMIN operations: account/workspace/entitlement/privacy metadata (Capstone P6.5)."},
]

DESCRIPTION = (
    "Typed HTTP API over the Intelligent Interview Coach application layer. "
    "Deterministic RAG today; agent orchestration (LangGraph) and a Next.js "
    "frontend are planned for later Sprint 4 phases."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # App-lifetime state. Expensive resources (vector store, repository, …) are
    # built lazily on first use and cached here under a lock — nothing that makes
    # a provider/DB call runs at import or startup.
    # RLock (reentrant) is required: a resource factory may itself resolve another
    # shared resource (e.g. get_agent_service's factory calls get_app_config), which
    # re-enters ``_shared`` on the SAME thread — a plain Lock would self-deadlock.
    app.state.resources = {}
    app.state.resources_lock = threading.RLock()
    app.state.session_store = InMemorySessionStore()
    logger.info("API started (env=%s)", app.state.settings.env)
    yield
    app.state.resources.clear()


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    app = FastAPI(
        title="Ask4Mo — Intelligent Interview Coach API",
        version=settings.version,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Fail fast in production when a mandatory dependency is missing (§31). Dev/test/staging
    # never raise here; production refuses to boot "healthy" without critical config.
    from src.api.env_validation import enforce_runtime_config

    app.state.env_report = enforce_runtime_config()

    # Error/resilience middleware stack (P10B-W9.1). ORDER IS LOAD-BEARING.
    # ``add_middleware`` PREPENDS, so the LAST one added is the OUTERMOST. Starlette also wraps
    # every user middleware inside its own ServerErrorMiddleware, so an unhandled 500 raised in
    # a route would otherwise be turned into a response OUTSIDE this stack and bypass CORS —
    # the browser then sees a header-less cross-origin response and reports a misleading
    # "couldn't connect" network failure for what is really a server bug (PF-01/PF-02).
    #
    # We therefore add (inner -> outer): CatchAllError -> RequestId -> SecurityHeaders -> CORS.
    # Effective nesting becomes CORS(outer) -> SecurityHeaders -> RequestId -> CatchAllError ->
    # routes. CatchAllErrorMiddleware converts unhandled exceptions to the safe envelope from
    # INSIDE the stack, so every response — success, expected error, or catastrophic 500 —
    # flows back out through RequestId (X-Request-Id) and CORS (Access-Control-Allow-Origin).
    app.add_middleware(CatchAllErrorMiddleware, env=settings.env)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, env=settings.env)
    # CORS — exact allow-list only, never wildcard-with-credentials. In staging/production
    # enforce_runtime_config() (above) has already failed fast when FRONTEND_ORIGINS is unset,
    # so the allow-list is always present there; development falls back to safe localhost
    # origins (see ApiSettings.from_env). Added LAST so it is the OUTERMOST layer and stamps
    # CORS headers on every response, including the catch-all 500.
    if settings.frontend_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.frontend_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-Id"],
        )
    register_exception_handlers(app)

    # Infra liveness alias (unversioned) + versioned API surface.
    app.include_router(health.router, prefix="/api")
    for module in (health, career, interview, history, knowledge, evaluation, agent, memory, feedback, progress, auth, reviewer, voice, workspaces, admin, admin_ai, admin_billing, admin_integrations, admin_jobs, admin_knowledge, admin_legal, admin_privacy, admin_plans, admin_support, company, opportunity, privacy, support):
        app.include_router(module.router, prefix=API_PREFIX)
    # Workspaces registers a second router for explicit sharing under the same prefix.
    app.include_router(workspaces.shares_router, prefix=API_PREFIX)
    # Documents phase (P4) registers three routers under the same prefix.
    app.include_router(documents.router, prefix=API_PREFIX)
    app.include_router(documents.stories_router, prefix=API_PREFIX)
    app.include_router(documents.export_router, prefix=API_PREFIX)
    return app


app = create_app()
