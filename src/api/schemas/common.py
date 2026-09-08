"""Shared API response schemas: health, capabilities, and the error envelope."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str = Field(examples=["intelligent-interview-coach"])
    version: str


class CapabilitiesResponse(BaseModel):
    """User-safe feature availability — never secrets or provider config."""

    career_intelligence: bool = True
    interview_practice: bool = True
    knowledge_base: bool = True
    evaluation: bool = True
    live_interview_enabled: bool = False
    # Sprint 4 agent capabilities (delivered in Phases 6–8): the frontend feature-
    # detects these rather than inferring them from route existence.
    agentic_rag: bool = True
    agent_memory: bool = True
    human_in_the_loop: bool = True
    # Candidate-facing Agent Coach cutover (Phase 9) — a DEPLOYMENT capability
    # controlled by AGENT_COACH_ENABLED, not a user preference. When false, /prepare
    # stays on the deterministic Career flow.
    agent_coach_enabled: bool = False


class ErrorBody(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Stable error envelope: ``{"error": {code, message, request_id}}``."""

    error: ErrorBody
