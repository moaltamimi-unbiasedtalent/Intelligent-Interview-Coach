"""Safe provider status for ``GET /admin/providers`` (P10B-W10.1, SEC-W10-06).

Built only from booleans and fixed vocabularies. Environment values are read to answer "is it set?",
never echoed. No network call is made: ``configured`` does not mean healthy, so health is always
"Health not tested" unless future evidence exists.
"""

from __future__ import annotations

import os

from src.api.schemas.admin import (
    OcrLanguageStatus, OcrStatus, ProviderRow, ProvidersResponse, RealtimeStatus, SpeechStatus,
)


def _set(*names: str) -> bool:
    return any(bool(os.environ.get(n, "").strip()) for n in names)


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _row(provider_id: str, label: str, configured: bool, *, enabled: bool | None = None,
         mode: str | None = None) -> ProviderRow:
    return ProviderRow(
        provider_id=provider_id, label=label, configured=configured,
        enabled=configured if enabled is None else enabled,
        status="configured_health_not_tested" if configured else "not_configured", mode=mode,
    )


def build_providers_response(pause_service=None) -> ProvidersResponse:
    from src.application.admin_command_center import rate_limit_mode
    from src.documents.ocr import ocr_runtime_status
    from src.voice.realtime import resolve_realtime_config

    brevo = bool(os.environ.get("EMAIL_PROVIDER", "").strip().lower() == "brevo"
                 and _set("BREVO_API_KEY") and _set("EMAIL_SENDER"))
    rows = [
        _row("email", "Transactional email", brevo, mode="brevo" if brevo else "console"),
        _row("google_oidc", "Google sign-in (OIDC)", _set("GOOGLE_OIDC_CLIENT_ID", "GOOGLE_CLIENT_ID")),
        _row("openrouter", "Language model provider (OpenRouter)", _set("OPENROUTER_API_KEY")),
        _row("adzuna", "Labour-market data (Adzuna)", _set("ADZUNA_APP_ID") and _set("ADZUNA_APP_KEY")),
        _row("langfuse", "External observability (Langfuse)",
             _set("LANGFUSE_PUBLIC_KEY") and _set("LANGFUSE_SECRET_KEY"),
             enabled=_flag("AGENT_EXTERNAL_OBSERVABILITY_ENABLED")),
    ]
    ocr = ocr_runtime_status()
    rt = resolve_realtime_config().safe_dict()
    rl = rate_limit_mode()
    return ProvidersResponse(
        providers=rows,
        speech=SpeechStatus(
            architecture="browser_web_speech", input="browser_web_speech_stt",
            output="browser_speech_synthesis_tts", camera="never_requested",
            audio_persisted_by_ask4mo=False, voice_trait_inference="none", live_quality="UNVALIDATED",
            realtime=RealtimeStatus(
                enabled=bool(rt.get("enabled")), configured=bool(rt.get("configured")),
                available=bool(rt.get("available")),
                max_session_seconds=int(rt.get("max_session_seconds", 0)),
                max_concurrent_per_user=int(rt.get("max_concurrent_per_user", 0)),
                live_validation="NOT_RUN"),
        ),
        ocr=OcrStatus(
            engine=str(ocr.get("engine", "unknown")), available=bool(ocr.get("available")),
            pdf_ocr_available=bool(ocr.get("pdf_ocr_available")),
            poppler_available=bool(ocr.get("poppler_available")),
            languages={k: OcrLanguageStatus(configured=bool(v.get("configured")),
                                            runtime_available=bool(v.get("runtime_available")))
                       for k, v in (ocr.get("languages") or {}).items()},
            live_quality=str(ocr.get("live_quality", "UNVALIDATED"))),
        pause={k: v["paused"] for k, v in pause_service.snapshot().items()} if pause_service is not None else {}, pause_durable=pause_service is not None,
        rate_limit_mode=rl["mode"], rate_limit_distributed=bool(rl["distributed"]),
        note=("Booleans and fixed labels only. Provider configuration is managed outside this console "
              "(deployment environment). Configured does not mean healthy; no provider is contacted here."),
    )
