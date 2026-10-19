"""Schemas for the governed speech routes (W12.4E). Allow-list models only: no secret, path, command, endpoint or open dictionary is ever accepted or returned."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpeechConfigView(_Strict):
    stt_provider: str
    tts_provider: str
    stt_enabled: bool
    tts_enabled: bool
    languages: list[str]
    browser_stt_allowed: bool
    browser_tts_allowed: bool
    stt_timeout_seconds: int
    tts_timeout_seconds: int
    revision: int
    persisted: bool
    updated_at: str | None = None
    updated_by_user_id: int | None = None
    reason: str = ""


class SpeechConfigChange(_Strict):
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=200)
    stt_provider: str | None = Field(default=None, max_length=24)
    tts_provider: str | None = Field(default=None, max_length=24)
    stt_enabled: bool | None = None
    tts_enabled: bool | None = None
    languages: list[str] | None = Field(default=None, max_length=12)
    browser_stt_allowed: bool | None = None
    browser_tts_allowed: bool | None = None
    stt_timeout_seconds: int | None = Field(default=None, ge=1, le=1000)
    tts_timeout_seconds: int | None = Field(default=None, ge=1, le=1000)


class ProviderReadiness(_Strict):
    provider: str
    configured: bool
    dependency_available: bool
    model_available: bool
    ready_for_offline_execution: bool
    validated_with_fixture: bool
    validated_with_genuine_model: str
    live_authorized: bool
    operational: bool
    deployment: str
    blockers: list[str]
    note: str


class SpeechOverview(_Strict):
    environment: str
    config: SpeechConfigView
    stt: ProviderReadiness
    tts: ProviderReadiness
    language_matrix: dict[str, dict]
    provider_facts: dict[str, dict]
    authorization: dict[str, bool]
    note: str


class SpeechCapabilitiesResponse(_Strict):
    server_stt_languages: list[str]
    server_tts_languages: list[str]
    browser_stt_allowed: bool
    browser_tts_allowed: bool
    product_languages: list[str]
    excluded_languages: list[str]
    audio_persisted: bool
    browser_disclosure: str


class TranscriptionResponse(_Strict):
    transcript: str
    language: str
    duration_seconds: float | None = None
    provider: str
    flagged: bool = False
    blocked: bool = False


class SynthesisRequest(_Strict):
    text: str = Field(min_length=1, max_length=3000)
    language: str = Field(min_length=2, max_length=8)
