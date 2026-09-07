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
from src.api.middleware import RequestIdMiddleware
from src.api.routes import career, evaluation, health, history, interview, knowledge
from src.api.session_store import InMemorySessionStore

logger = logging.getLogger("api")

TAGS_METADATA = [
    {"name": "health", "description": "Liveness, readiness and safe capabilities."},
    {"name": "career", "description": "Grounded career guidance and domain tools."},
    {"name": "interviews", "description": "Interview practice sessions and reports."},
    {"name": "history", "description": "The caller's saved interviews (user-scoped)."},
    {"name": "knowledge", "description": "Read-only knowledge-base status."},
    {"name": "evaluation", "description": "Read-only evaluation status (no paid runs)."},
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
    app.state.resources = {}
    app.state.resources_lock = threading.Lock()
    app.state.session_store = InMemorySessionStore()
    logger.info("API started (env=%s)", app.state.settings.env)
    yield
    app.state.resources.clear()


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    app = FastAPI(
        title="Intelligent Interview Coach API",
        version=settings.version,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    app.state.settings = settings

    # CORS for the future Next.js frontend. Never wildcard-with-credentials.
    if settings.frontend_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.frontend_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-Id"],
        )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    # Infra liveness alias (unversioned) + versioned API surface.
    app.include_router(health.router, prefix="/api")
    for module in (health, career, interview, history, knowledge, evaluation):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
