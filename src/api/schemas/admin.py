"""Allowlist response schemas for the admin surface (P10B-W10.1, SEC-W10-06).

Every field is explicit. There is no open-ended mapping pass-through, so a new environment variable or
config value can never leak into the response by accident; ``extra="forbid"`` guards construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


HEALTH_NOT_TESTED = "Health not tested"
ProviderState = Literal["not_configured", "configured_health_not_tested", "internal"]


class ProviderRow(_Strict):
    provider_id: str
    label: str
    configured: bool
    enabled: bool
    externally_managed: bool = True   # configured through deployment env, not by this console
    writable: bool = False            # the console cannot change provider configuration (AD-04)
    status: ProviderState
    health: str = HEALTH_NOT_TESTED   # configured is NOT healthy; no live call is made here
    live_validation: str = "UNVALIDATED"
    mode: str | None = None           # fixed vocabulary only (e.g. console/brevo)


class OcrLanguageStatus(_Strict):
    configured: bool
    runtime_available: bool


class OcrStatus(_Strict):
    engine: str
    available: bool
    pdf_ocr_available: bool
    poppler_available: bool
    languages: dict[str, OcrLanguageStatus]
    live_quality: str


class RealtimeStatus(_Strict):
    enabled: bool
    configured: bool
    available: bool
    max_session_seconds: int
    max_concurrent_per_user: int
    live_validation: str
    audio_visible_to_admin: bool = False
    transcript_visible_to_admin: bool = False


class SpeechStatus(_Strict):
    architecture: str
    input: str
    output: str
    camera: str
    audio_persisted_by_ask4mo: bool
    voice_trait_inference: str
    live_quality: str
    realtime: RealtimeStatus


class ProvidersResponse(_Strict):
    providers: list[ProviderRow]
    speech: SpeechStatus
    ocr: OcrStatus
    pause: dict[str, bool]
    pause_durable: bool = False
    rate_limit_mode: str
    rate_limit_distributed: bool
    note: str
