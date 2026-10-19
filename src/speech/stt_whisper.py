"""OpenAI Whisper speech-to-text adapter (W12.4E). Implements the existing ``SpeechTranscriptionService`` interface.

Two deployment models sit behind ONE contract, selected by the engine you give it:
  * ``LocalWhisperEngine`` (self-hosted open weights; audio never leaves our infrastructure). It needs a dependency and a model directory that an operator placed; it NEVER downloads weights.
  * ``OpenAIWhisperApiEngine`` (hosted ``whisper-1``; audio goes to a third party). It needs its own authorization (``WHISPER_API_TRANSPORT_AUTHORIZED``) and a credential from the SecretStore.

Nothing executes unless ``SERVER_SPEECH_PROVIDERS_AUTHORIZED`` is True (it is False). Genuine model execution on real audio is NOT VERIFIED; the contract is proven with deterministic fixture engines.
Privacy: audio is validated, handed to the engine and discarded; it is never logged or persisted, and only categories are logged.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Callable, Protocol

from src.speech import policy
from src.speech.audio import TransientAudio, secure_tempfile, validate_and_sniff
from src.speech.engines import BoundedRunner, EngineError, ModelUnavailable, ProviderNotAuthorized
from src.speech_service import SpeechError, SpeechTranscriptionService, TranscriptionResult

__all__ = ["WhisperEngine", "FixtureWhisperEngine", "LocalWhisperEngine", "OpenAIWhisperApiEngine", "WhisperTranscriptionService", "WHISPER_API_URL", "WHISPER_API_MODEL"]

_LOG = logging.getLogger(__name__)
WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"      # a constant owned by the adapter: no user-controlled destination
WHISPER_API_MODEL = "whisper-1"


class WhisperEngine(Protocol):
    deployment: str

    def transcribe(self, audio: bytes, mime_type: str, language: str) -> dict:
        """Return ``{"text": str, "language": str | None, "confidence": float | None}``. May raise ``ModelUnavailable`` / ``EngineError``."""


class FixtureWhisperEngine:
    """Deterministic engine for contract tests. ``script(audio, language) -> dict`` decides the output; it is NOT a speech model and its output is never speech quality."""

    deployment = "fixture"

    def __init__(self, script: Callable[[bytes, str], dict] | None = None) -> None:
        self._script = script or (lambda audio, language: {"text": f"fixture transcript ({language})", "language": language, "confidence": None})
        self.calls = 0

    def transcribe(self, audio: bytes, mime_type: str, language: str) -> dict:
        self.calls += 1
        return self._script(audio, language)


class LocalWhisperEngine:
    """Self-hosted open-weights Whisper. NOT VERIFIED on real audio. Requires ``faster_whisper`` or ``whisper`` AND an operator-placed model directory (``SPEECH_WHISPER_MODEL_DIR``); never downloads."""

    deployment = "self_hosted"

    def __init__(self, model_dir: str | None = None, model_name: str = "small") -> None:
        self.model_dir = model_dir if model_dir is not None else os.environ.get("SPEECH_WHISPER_MODEL_DIR", "")
        self.model_name = model_name
        self._model = None

    @staticmethod
    def dependency_available() -> bool:
        return importlib.util.find_spec("faster_whisper") is not None or importlib.util.find_spec("whisper") is not None

    def model_available(self) -> bool:
        return bool(self.model_dir) and Path(self.model_dir).is_dir() and any(Path(self.model_dir).iterdir())

    def _load(self):
        if self._model is not None:
            return self._model
        if not self.dependency_available() or not self.model_available():
            raise ModelUnavailable("whisper dependency or model directory missing")
        if importlib.util.find_spec("faster_whisper") is not None:
            from faster_whisper import WhisperModel          # pragma: no cover - needs weights

            self._model = ("faster", WhisperModel(self.model_dir, local_files_only=True))   # pragma: no cover
        else:
            raise ModelUnavailable("only the faster-whisper loader is supported for an operator-placed directory")   # never ``whisper.load_model`` (it downloads)
        return self._model

    def transcribe(self, audio: bytes, mime_type: str, language: str) -> dict:   # pragma: no cover - needs weights
        kind, model = self._load()
        with secure_tempfile(audio, ".audio") as path:
            segments, info = model.transcribe(str(path), language=language, vad_filter=False)
            text = " ".join(s.text.strip() for s in segments).strip()
        return {"text": text, "language": getattr(info, "language", language), "confidence": getattr(info, "language_probability", None)}


class OpenAIWhisperApiEngine:
    """Hosted ``whisper-1`` transport. Candidate audio goes to a THIRD PARTY, so it needs ``WHISPER_API_TRANSPORT_AUTHORIZED`` and a SecretStore credential. A client is injected so tests make no call."""

    deployment = "hosted_api"

    def __init__(self, client=None, api_key_reader: Callable[[], str | None] | None = None) -> None:
        self._client = client
        self._key = api_key_reader

    def transcribe(self, audio: bytes, mime_type: str, language: str) -> dict:
        if not policy.WHISPER_API_TRANSPORT_AUTHORIZED:
            raise ProviderNotAuthorized("hosted transcription transport is not authorized")
        key = self._key() if self._key else None
        if not key:
            raise ModelUnavailable("no credential")
        if self._client is None:
            import httpx

            self._client = httpx.Client(timeout=30.0)
        resp = self._client.post(WHISPER_API_URL, headers={"Authorization": f"Bearer {key}"},
                                 files={"file": ("audio", audio, mime_type)}, data={"model": WHISPER_API_MODEL, "language": language, "response_format": "json"})
        if resp.status_code >= 400:
            raise EngineError(f"status {resp.status_code}")
        body = resp.json()
        return {"text": body.get("text", ""), "language": language, "confidence": None}


class WhisperTranscriptionService(SpeechTranscriptionService):
    provider_name = policy.SELECTED_STT_PROVIDER

    def __init__(self, engine: WhisperEngine, *, timeout_seconds: float = 30.0, runner: BoundedRunner | None = None, enabled_languages: tuple[str, ...] | None = None,
                 authorized: Callable[[], bool] | None = None) -> None:
        self._engine = engine
        self._timeout = timeout_seconds
        self._runner = runner or BoundedRunner(2)
        self._languages = policy.effective_languages(policy.WHISPER_CAPABILITY, enabled_languages)
        self._authorized = authorized or (lambda: policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED)

    @property
    def is_available(self) -> bool:
        return self._authorized()

    @property
    def languages(self) -> tuple[str, ...]:
        return self._languages

    def transcribe(self, data: bytes, *, mime_type: str, language: str | None = None) -> TranscriptionResult:
        if not self._authorized():
            raise SpeechError("Voice answers are not available right now. You can type your answer.", category="not_authorized")
        lang = policy.base_language(language)
        if lang is None or lang not in self._languages:                      # explicit, eligible language BEFORE any audio is touched ("auto" is not accepted)
            raise SpeechError("Speech is not available in that language. You can type your answer.", category="unsupported_language")
        duration = validate_and_sniff(data, mime_type)
        audio = TransientAudio(bytearray(data), mime_type, duration)
        try:
            out = self._runner.run(lambda: self._engine.transcribe(audio.view(), mime_type, lang), timeout_seconds=self._timeout)
        except SpeechError as exc:
            _LOG.warning("speech transcription failed: provider=%s category=%s", self.provider_name, exc.category)   # category only: never audio or transcript
            raise
        finally:
            audio.discard()
        text = (out or {}).get("text") if isinstance(out, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise SpeechError("No speech was detected. Please record again or type your answer.", category="empty_transcript")
        confidence = out.get("confidence")
        quality = {"average_confidence": round(float(confidence), 4)} if isinstance(confidence, (int, float)) and confidence > 0 else None
        return TranscriptionResult(transcript=text.strip(), detected_language=lang, duration_seconds=round(duration, 2) if duration else None, quality=quality, provider=self.provider_name)
