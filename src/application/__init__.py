"""Application layer for Intelligent Interview Coach.

A thin, Streamlit-free boundary between the frontend and the domain/services.
Both the current Streamlit UI and a future FastAPI backend call the same
functions here; nothing in this package imports Streamlit or the UI modules.

See ``docs/sprint4_architecture.md`` for the Phase 1 boundary.
"""

from __future__ import annotations

from src.application import (
    errors,
    evaluation_service,
    factories,
    history_service,
    knowledge_service,
)
from src.application.career_service import CareerApplicationService
from src.application.interview_service import InterviewApplicationService
from src.application.models import CareerChatRequest, ToolCallResult

__all__ = [
    "CareerApplicationService",
    "InterviewApplicationService",
    "CareerChatRequest",
    "ToolCallResult",
    "errors",
    "factories",
    "history_service",
    "knowledge_service",
    "evaluation_service",
]
