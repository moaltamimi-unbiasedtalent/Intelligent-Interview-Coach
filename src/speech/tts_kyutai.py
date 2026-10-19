"""Kyutai Pocket TTS adapter (W12.4E): a provider-agnostic ``TextToSpeechService`` interface (the repository had none: speech output was browser-only) and the Kyutai implementation.

Verified capabilities (see ``policy.KYUTAI_CAPABILITY``): about 100M parameters, CPU capable, six verified languages (English, French, German, Portuguese, Italian, Spanish); Dutch is claimed by one
official page and absent from the other, so it is UNVERIFIED and not eligible. Weights are cc-by-4.0 and GATED; per-voice licences were not verified; voice cloning is prohibited without lawful consent
and is never offered: only the built-in voice per language is used, chosen by the server (a client never sends a voice, a path or a model name).

Nothing executes unless ``SERVER_SPEECH_PROVIDERS_AUTHORIZED`` is True (it is False), weights are never downloaded, and genuine model execution is MODEL_EXECUTION_NOT_VERIFIED: the contract is proven with a
deterministic fixture engine whose output is a tone, not speech. Generated audio is transient and never persisted.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import math
import os
import struct
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from src.speech import policy
from src.speech.engines import BoundedRunner, ModelUnavailable
from src.speech.text import prepare_speech_text
from src.speech_service import SpeechError

__all__ = ["SynthesisResult", "TextToSpeechService", "UnavailableTtsService", "TtsEngine", "FixtureTtsEngine", "LocalPocketTtsEngine", "KyutaiPocketTtsService", "MAX_AUDIO_BYTES_OUT"]

_LOG = logging.getLogger(__name__)
MAX_AUDIO_BYTES_OUT = 20 * 1024 * 1024


@dataclass(frozen=True)
class SynthesisResult:
    audio: bytes
    mime_type: str
    sample_rate: int
    language: str
    voice: str
    provider: str
    duration_seconds: float

    def __repr__(self) -> str:                       # never the bytes
        return f"SynthesisResult(bytes={len(self.audio)}, language={self.language}, provider={self.provider})"


class TextToSpeechService(ABC):
    provider_name: str = "tts"

    @property
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def synthesize(self, text: str, *, language: str | None) -> SynthesisResult: ...


class UnavailableTtsService(TextToSpeechService):
    provider_name = "unavailable"

    @property
    def is_available(self) -> bool:
        return False

    def synthesize(self, text: str, *, language: str | None) -> SynthesisResult:
        raise SpeechError("Spoken answers are not available. You can read the answer on screen.", category="unavailable")


class TtsEngine(Protocol):
    deployment: str

    def synthesize(self, text: str, model_name: str, voice: str) -> tuple[bytes, int]:
        """Return ``(wav_bytes, sample_rate)``. May raise ``ModelUnavailable`` / ``EngineError``."""


def _tone_wav(seconds: float, rate: int = 16000) -> bytes:
    frames = b"".join(struct.pack("<h", int(2000 * math.sin(2 * math.pi * 220 * i / rate))) for i in range(int(seconds * rate)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


class FixtureTtsEngine:
    """Deterministic engine for contract tests: a short tone whose length depends on the text length. It is NOT speech and says nothing about voice quality."""

    deployment = "fixture"

    def __init__(self, script: Callable[[str, str, str], tuple[bytes, int]] | None = None) -> None:
        self._script = script
        self.calls = 0
        self.last_request: tuple[str, str, str] | None = None

    def synthesize(self, text: str, model_name: str, voice: str) -> tuple[bytes, int]:
        self.calls += 1
        self.last_request = (text, model_name, voice)
        if self._script:
            return self._script(text, model_name, voice)
        return _tone_wav(min(3.0, 0.05 * max(1, len(text)) / 10)), 16000


class LocalPocketTtsEngine:
    """Self-hosted Kyutai Pocket TTS. MODEL_EXECUTION_NOT_VERIFIED. Requires the ``pocket_tts`` dependency AND an operator-placed model directory (``SPEECH_KYUTAI_MODEL_DIR``); never downloads
    (the weights are gated) and never clones a voice."""

    deployment = "self_hosted"

    def __init__(self, model_dir: str | None = None) -> None:
        self.model_dir = model_dir if model_dir is not None else os.environ.get("SPEECH_KYUTAI_MODEL_DIR", "")

    @staticmethod
    def dependency_available() -> bool:
        return importlib.util.find_spec("pocket_tts") is not None

    def model_available(self) -> bool:
        return bool(self.model_dir) and Path(self.model_dir).is_dir() and any(Path(self.model_dir).iterdir())

    def synthesize(self, text: str, model_name: str, voice: str) -> tuple[bytes, int]:   # pragma: no cover - needs weights
        if policy.VOICE_CLONING_ENABLED or not self.dependency_available() or not self.model_available():
            raise ModelUnavailable("pocket-tts dependency or model directory missing")
        raise ModelUnavailable("the local Pocket TTS runtime binding was not verified against genuine weights in this wave")   # honest: no guessed API is exercised


class KyutaiPocketTtsService(TextToSpeechService):
    provider_name = policy.SELECTED_TTS_PROVIDER

    def __init__(self, engine: TtsEngine, *, timeout_seconds: float = 30.0, runner: BoundedRunner | None = None, enabled_languages: tuple[str, ...] | None = None,
                 authorized: Callable[[], bool] | None = None) -> None:
        self._engine = engine
        self._timeout = timeout_seconds
        self._runner = runner or BoundedRunner(2)
        self._languages = policy.effective_languages(policy.KYUTAI_CAPABILITY, enabled_languages)
        self._authorized = authorized or (lambda: policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED)

    @property
    def is_available(self) -> bool:
        return self._authorized()

    @property
    def languages(self) -> tuple[str, ...]:
        return self._languages

    def synthesize(self, text: str, *, language: str | None) -> SynthesisResult:
        if not self._authorized():
            raise SpeechError("Spoken answers are not available right now. You can read the answer on screen.", category="not_authorized")
        lang = policy.base_language(language)
        if lang is None or lang not in self._languages:                      # eligibility BEFORE any text is processed (Dutch is unverified, Russian is excluded)
            raise SpeechError("Spoken answers are not available in that language.", category="unsupported_language")
        spoken = prepare_speech_text(text)                                   # only the approved candidate-visible text, never a secret, a leak or an error trace
        notes = policy.KYUTAI_CAPABILITY.notes
        model_name, voice = notes["model_names"][lang], notes["builtin_voices"][lang]
        try:
            wav, rate = self._runner.run(lambda: self._engine.synthesize(spoken, model_name, voice), timeout_seconds=self._timeout)
        except SpeechError as exc:
            _LOG.warning("speech synthesis failed: provider=%s category=%s", self.provider_name, exc.category)    # category only: never the text or the audio
            raise
        if not isinstance(wav, (bytes, bytearray)) or not wav:
            raise SpeechError("No audio was produced.", category="empty_synthesis")
        if len(wav) > MAX_AUDIO_BYTES_OUT:
            raise SpeechError("The audio was too large.", category="too_large")
        try:
            with wave.open(io.BytesIO(bytes(wav)), "rb") as w:
                duration = w.getnframes() / float(w.getframerate())
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise SpeechError("No usable audio was produced.", category="empty_synthesis") from exc
        if duration <= 0:
            raise SpeechError("No audio was produced.", category="empty_synthesis")
        return SynthesisResult(audio=bytes(wav), mime_type="audio/wav", sample_rate=int(rate), language=lang, voice=voice, provider=self.provider_name, duration_seconds=round(duration, 3))
