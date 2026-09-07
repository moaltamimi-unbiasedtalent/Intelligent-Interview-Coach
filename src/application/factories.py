"""Streamlit-free construction of the application's domain services.

These factories build the same objects the Streamlit UI used to construct inside
``@st.cache_resource``/``st.session_state`` helpers, but with **no Streamlit
dependency** — so a future FastAPI backend can build them the same way. The UI may
still cache the results in its own thin wrappers (see ``src/career/ui.py`` and
``src/interview/studio_app.py``); the factories here must work without Streamlit.

Nothing here performs a provider call, retrieval or evaluation at import or call
time beyond what construction already did in Sprint 3 (e.g. building a vector
store). Behaviour is unchanged; only the *location* of construction moved.
"""

from __future__ import annotations

import os
from typing import Any

from src.config import AppConfig
from src.copilot.config import CopilotConfig

# --- Career Intelligence -----------------------------------------------------


def build_vector_store(config: CopilotConfig):
    """Build the Career vector store (expensive; UI wraps this in a cache)."""
    from src.copilot.vectorstore import build_vector_store as _build

    return _build(config)


def build_tool_invoker(config: CopilotConfig):
    """Build the Career domain tool invoker (job/gap/plan/questions)."""
    from src.copilot.tools import ToolInvoker, build_tool_registry

    return ToolInvoker(build_tool_registry(config=config))


def build_career_service(
    config: CopilotConfig,
    *,
    store: Any | None = None,
    translation_cache: Any | None = None,
    retrieval_mode: str | None = None,
):
    """Construct a :class:`CareerIntelligenceService` and its retrieval wiring.

    Mirrors the Streamlit chat construction exactly: a retriever over the vector
    store, the structured knowledge coordinator, and an optional shared
    translation cache. ``store`` and ``translation_cache`` are injected by the UI
    (which caches them); when omitted they are built here so non-UI callers work.
    """
    from src.copilot.knowledge.retrieval import build_default_coordinator
    from src.copilot.retrieval import build_retriever
    from src.copilot.service import CareerIntelligenceService

    if store is None:
        store = build_vector_store(config)
    mode = retrieval_mode or config.retrieval_mode
    retriever = build_retriever(config, mode=mode, store=store)
    coordinator = build_default_coordinator(config)
    return CareerIntelligenceService(
        config=config,
        retriever=retriever,
        knowledge_coordinator=coordinator,
        translation_cache=translation_cache,
    )


# --- Interview Practice ------------------------------------------------------


def build_pricing_service():
    """Build a pricing service (its metadata cache is reused by the UI wrapper)."""
    from src.pricing_service import PricingService

    return PricingService()


def build_interview_services(config: AppConfig, *, pricing=None):
    """Build the interview/evaluation/report services over one OpenRouter client.

    Returns ``(interview, evaluation, report, client)`` — identical to the former
    ``studio_app.build_services``. The caller owns closing ``client``.
    """
    from src.evaluation_service import EvaluationService
    from src.interview_service import InterviewService
    from src.openrouter_client import OpenRouterClient
    from src.report_service import ReportService

    if pricing is None:
        pricing = build_pricing_service()
    client = OpenRouterClient(config)
    return (
        InterviewService(client, pricing),
        EvaluationService(client, pricing),
        ReportService(client, pricing),
        client,
    )


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a SQLite file URL if needed."""
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        path = database_url[len(prefix):]
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)


def build_repository(config: AppConfig):
    """Build an :class:`InterviewRepository` over the configured database.

    Dev/tests initialise the schema in-process; production applies Alembic
    migrations. Streamlit-free so a future API can build the same repository.
    """
    from src.persistence import init_db, make_engine, make_session_factory
    from src.repository import InterviewRepository

    _ensure_sqlite_dir(config.database_url)
    engine = make_engine(config.database_url)
    init_db(engine)
    return InterviewRepository(make_session_factory(engine))
