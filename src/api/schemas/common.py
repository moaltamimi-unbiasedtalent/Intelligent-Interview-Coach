"""Shared API response schemas: health, capabilities, and the error envelope."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.locales import ACTIVE_CANDIDATE_LOCALES, DEFAULT_ACTIVE_LOCALE


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
    # Realtime voice (Capstone P7.5, C1) — a DEPLOYMENT capability requiring both the
    # REALTIME_VOICE_ENABLED flag AND a configured realtime provider key. When false, the
    # UI stays on P7 turn-based voice (the safe default). Never implies a key is present.
    realtime_voice_enabled: bool = False
    # Company Intelligence (P10B Wave 5) — the directable company-research surface. True when
    # external research is enabled and not operator-paused; it never implies a provider key is
    # present (the company-web path works from a user-supplied website; market data degrades
    # honestly without credentials).
    company_research_enabled: bool = False
    # 06A (REQ-LANG-14): the server-defined, code-only list of locales a Candidate may select or start NEW work in.
    # Backward compatible (additive). Excludes ru (preserved, not offered). NOT a per-language qualification claim.
    active_candidate_locales: list[str] = Field(default_factory=lambda: list(ACTIVE_CANDIDATE_LOCALES))
    default_locale: str = DEFAULT_ACTIVE_LOCALE
    # 06H: the activation decision (codes and mode only; per-gate detail is Admin-only). ``active_candidate_locales`` above is the OFFERED set:
    # in hosted environments it is empty until a locale has a complete approved qualification record; in development and test it is the seven,
    # with the unqualified ones listed in ``unqualified_locales`` so every selector can label them.
    language_activation_mode: str = "labelled"
    qualified_locales: list[str] = Field(default_factory=list)
    unqualified_locales: list[str] = Field(default_factory=list)
    no_language_available: bool = False
    # 04D (DEMO-02): the AI provider MODE of this stack (fixed vocabulary): live (a credential is configured; health is NOT tested), offline (no provider is read or reachable; answers
    # come from test doubles), not_configured, unknown. Candidate and Admin surfaces show it so a keyless or offline stack can never masquerade as live. Never a key, URL or model id.
    ai_provider_mode: Literal["live", "offline", "not_configured", "unknown"] = "unknown"


class ErrorBody(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Stable error envelope: ``{"error": {code, message, request_id}}``."""

    error: ErrorBody
