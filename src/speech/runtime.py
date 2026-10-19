"""The governed speech runtime (W12.4E): composes the Admin configuration, the code authorization constants, the provider adapters, readiness and the candidate-facing capability view.

A provider executes only when ALL of these hold: the code constant authorizes server speech, the administrator enabled it, the language is eligible (product boundary AND provider capability AND admin
selection), and the engine can run (dependency and model present; never downloaded). Anything else is a controlled, candidate-safe refusal that leaves the text workflow and the (separately governed) browser
fallback intact.
"""

from __future__ import annotations

import io
import struct
import wave
from dataclasses import dataclass

from src.speech import policy
from src.speech.engines import BoundedRunner
from src.speech.governance import SpeechConfig, SpeechGovernanceService, default_config
from src.speech.stt_whisper import FixtureWhisperEngine, LocalWhisperEngine, WhisperEngine, WhisperTranscriptionService
from src.speech.text import SanitizedTranscript, sanitize_transcript
from src.speech.tts_kyutai import FixtureTtsEngine, KyutaiPocketTtsService, LocalPocketTtsEngine, SynthesisResult, TtsEngine
from src.speech_service import SpeechError

__all__ = ["SpeechRuntime", "TranscriptionOutcome", "provider_readiness", "fixture_wav"]


def fixture_wav(seconds: float = 0.2, rate: int = 16000) -> bytes:
    """A tiny SYNTHETIC silent WAV for contract checks. It is not candidate audio and contains no speech."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))
    return buf.getvalue()


@dataclass(frozen=True)
class TranscriptionOutcome:
    transcript: SanitizedTranscript
    language: str
    duration_seconds: float | None
    provider: str


def _engine_ready(engine) -> tuple[bool, bool]:
    """(dependency_available, model_available) for an engine. A fixture engine reports both True (it needs neither) but is never 'operational'."""
    if engine is None:
        return False, False
    if getattr(engine, "deployment", "") == "fixture":
        return True, True
    dep = getattr(engine, "dependency_available", lambda: False)()
    model = getattr(engine, "model_available", lambda: False)()
    return bool(dep), bool(model)


def provider_readiness(kind: str, config: SpeechConfig, engine) -> dict:
    """Separate readiness states (never one global 'ready'). ``kind`` is ``stt`` or ``tts``."""
    selected = config.stt_provider if kind == "stt" else config.tts_provider
    enabled = config.stt_enabled if kind == "stt" else config.tts_enabled
    dep, model = _engine_ready(engine)
    authorized = bool(policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED)
    genuine = policy.GENUINE_MODEL_VALIDATION.get(selected, "NOT_VERIFIED")
    fixture_ok = _fixture_contract_ok(kind)
    deployment = getattr(engine, "deployment", "none")
    ready_offline = dep and model
    operational = bool(enabled and authorized and ready_offline and deployment not in ("fixture", "none") and genuine == "VERIFIED")
    blockers = []
    if not enabled:
        blockers.append("disabled by configuration")
    if not authorized:
        blockers.append("server speech is not authorized (code constant)")
    if not dep:
        blockers.append("runtime dependency not installed")
    if not model:
        blockers.append("model weights not placed by an operator (never downloaded automatically)")
    if genuine != "VERIFIED":
        blockers.append(f"genuine model execution: {genuine}")
    return {"provider": selected, "configured": bool(selected) and bool(enabled), "dependency_available": dep, "model_available": model, "ready_for_offline_execution": ready_offline,
            "validated_with_fixture": fixture_ok, "validated_with_genuine_model": genuine, "live_authorized": authorized, "operational": operational, "deployment": deployment,
            "blockers": blockers, "note": "Configured is not operational; a fixture-passing adapter is not live-qualified."}


_FIXTURE_CACHE: dict[str, bool] = {}


def _fixture_contract_ok(kind: str) -> bool:
    """Run the adapter against a deterministic fixture engine (authorization overridden for this check only; no model, no network, no candidate data)."""
    if kind in _FIXTURE_CACHE:
        return _FIXTURE_CACHE[kind]
    try:
        if kind == "stt":
            svc = WhisperTranscriptionService(FixtureWhisperEngine(), authorized=lambda: True)
            ok = bool(svc.transcribe(fixture_wav(), mime_type="audio/wav", language="en").transcript)
        else:
            svc2 = KyutaiPocketTtsService(FixtureTtsEngine(), authorized=lambda: True)
            ok = svc2.synthesize("Hello there.", language="en").duration_seconds > 0
    except Exception:  # noqa: BLE001
        ok = False
    _FIXTURE_CACHE[kind] = ok
    return ok


class SpeechRuntime:
    def __init__(self, governance: SpeechGovernanceService | None = None, *, stt_engine: WhisperEngine | None = None, tts_engine: TtsEngine | None = None,
                 config_override: SpeechConfig | None = None) -> None:
        self._governance = governance
        self._config_override = config_override
        self.stt_engine = stt_engine if stt_engine is not None else LocalWhisperEngine()
        self.tts_engine = tts_engine if tts_engine is not None else LocalPocketTtsEngine()
        self._runner = BoundedRunner(2)

    def config(self) -> SpeechConfig:
        if self._config_override is not None:
            return self._config_override
        if self._governance is None:
            return default_config()
        return self._governance.get_or_fail_closed()

    # -- gating ---------------------------------------------------------------------------------------------------------------------------------------------------------------
    def _stt(self, cfg: SpeechConfig) -> WhisperTranscriptionService:
        return WhisperTranscriptionService(self.stt_engine, timeout_seconds=cfg.stt_timeout_seconds, runner=self._runner, enabled_languages=cfg.languages)

    def _tts(self, cfg: SpeechConfig) -> KyutaiPocketTtsService:
        return KyutaiPocketTtsService(self.tts_engine, timeout_seconds=cfg.tts_timeout_seconds, runner=self._runner, enabled_languages=cfg.languages)

    def stt_available(self, cfg: SpeechConfig | None = None) -> bool:
        cfg = cfg or self.config()
        return bool(cfg.stt_enabled and policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED)

    def tts_available(self, cfg: SpeechConfig | None = None) -> bool:
        cfg = cfg or self.config()
        return bool(cfg.tts_enabled and policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED)

    # -- operations -----------------------------------------------------------------------------------------------------------------------------------------------------
    def transcribe(self, audio: bytes, *, mime_type: str, language: str | None) -> TranscriptionOutcome:
        cfg = self.config()
        if not self.stt_available(cfg):
            raise SpeechError("Voice answers are not available right now. You can type your answer.", category="unavailable")
        result = self._stt(cfg).transcribe(audio, mime_type=mime_type, language=language)
        # A transcript is untrusted candidate input: same validation and injection scan as typed text. It is returned for the candidate to review and submit; it never acts on anything.
        return TranscriptionOutcome(transcript=sanitize_transcript(result.transcript), language=result.detected_language or "", duration_seconds=result.duration_seconds, provider=result.provider)

    def synthesize(self, text: str, *, language: str | None) -> SynthesisResult:
        cfg = self.config()
        if not self.tts_available(cfg):
            raise SpeechError("Spoken answers are not available right now. You can read the answer on screen.", category="unavailable")
        return self._tts(cfg).synthesize(text, language=language)

    # -- views ----------------------------------------------------------------------------------------------------------------------------------------------------------
    def readiness(self) -> dict:
        cfg = self.config()
        return {"stt": provider_readiness("stt", cfg, self.stt_engine), "tts": provider_readiness("tts", cfg, self.tts_engine)}

    def candidate_view(self) -> dict:
        """What the frontend may rely on (no secrets, no provider internals). Server speech is offered per language only when it is executable now; the browser fallback is a separate, governed permission."""
        cfg = self.config()
        stt_langs = policy.effective_languages(policy.WHISPER_CAPABILITY, cfg.languages) if self.stt_available(cfg) else ()
        tts_langs = policy.effective_languages(policy.KYUTAI_CAPABILITY, cfg.languages) if self.tts_available(cfg) else ()
        return {"server_stt_languages": list(stt_langs), "server_tts_languages": list(tts_langs), "browser_stt_allowed": cfg.browser_stt_allowed, "browser_tts_allowed": cfg.browser_tts_allowed,
                "product_languages": list(policy.PRODUCT_SPEECH_LANGUAGES), "excluded_languages": list(policy.EXCLUDED_SPEECH_LANGUAGES), "audio_persisted": False,
                "browser_disclosure": "Browser dictation may be processed by your browser's speech service. Ask4Mo does not store your audio."}

    def capability_matrix(self) -> dict:
        """Per product language: product-authorized, each provider's verified capability, the admin selection and the effective result."""
        cfg = self.config()
        rows = {}
        for code in policy.PRODUCT_SPEECH_LANGUAGES:
            rows[code] = {"product_authorized": True, "stt_provider_supports": code in policy.WHISPER_CAPABILITY.languages, "tts_provider_supports": code in policy.KYUTAI_CAPABILITY.languages,
                          "tts_provider_unverified": code in policy.KYUTAI_CAPABILITY.unverified_languages, "admin_selected": code in cfg.languages,
                          "effective_stt": code in policy.effective_languages(policy.WHISPER_CAPABILITY, cfg.languages), "effective_tts": code in policy.effective_languages(policy.KYUTAI_CAPABILITY, cfg.languages)}
        rows["ru"] = {"product_authorized": False, "stt_provider_supports": "ru" in policy.WHISPER_CAPABILITY.languages, "tts_provider_supports": False, "tts_provider_unverified": False,
                      "admin_selected": False, "effective_stt": False, "effective_tts": False, "note": "Russian is an interface language only; it is excluded from speech by product policy even though Whisper itself supports it."}
        return rows
