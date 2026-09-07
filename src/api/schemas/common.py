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
    # Planned Sprint 4 work — advertised as not-yet-available so a frontend can
    # feature-detect without assuming it exists.
    agentic_rag: bool = False
    agent_memory: bool = False
    human_in_the_loop: bool = False


class ErrorBody(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Stable error envelope: ``{"error": {code, message, request_id}}``."""

    error: ErrorBody
