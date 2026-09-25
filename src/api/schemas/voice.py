"""Realtime voice API schemas (Capstone P7.5).

The client may express only a *language preference*, a *surface* and (optionally) the
Practice session it belongs to. It can NEVER specify the provider, model or voice — those are
server-authoritative (see ``src/voice/realtime.py`` + the P5 model policy). No audio or
transcript is ever carried by these schemas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RealtimeSessionCreateRequest(BaseModel):
    """Request to open a realtime voice session. Bounded + allow-listed on purpose."""

    locale: str = Field(default="en", max_length=12,
                        description="Spoken-language preference (primary subtag used).")
    surface: Literal["practice", "prepare"] = Field(default="practice")
    interview_session_id: str | None = Field(default=None, max_length=200)


class RealtimeSessionResponse(BaseModel):
    """The browser's grant: the EPHEMERAL client secret + bounded, non-secret config.

    ``client_secret`` is the provider's short-lived token, never the server key.
    """

    provider: str
    model: str
    voice: str
    locale: str
    client_secret: str
    expires_at: float
    session_id: str
    base_url: str
    max_session_seconds: int
    idle_timeout_seconds: int


class RealtimeStatusResponse(BaseModel):
    """Safe availability projection (no secret). ``available`` gates the Start-live-voice UI;
    when false the UI stays on P7 turn-based voice."""

    enabled: bool = False
    configured: bool = False
    available: bool = False
    provider: str = "openai_realtime"
    supported_locales: list[str] = Field(default_factory=list)
    max_session_seconds: int = 0
    max_concurrent_per_user: int = 0
    fallback: str = "turn_based_voice"
