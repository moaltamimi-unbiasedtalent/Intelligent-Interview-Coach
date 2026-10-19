"""Candidate speech routes (W12.4E): capabilities, server-side transcription and server-side synthesis.

* Every route needs an authenticated user. Nothing here makes a provider call unless the governed runtime says server speech is executable (the code authorization constants are False, so by default every
  operation answers ``503 speech_unavailable`` with a ``fallback`` the frontend uses: the governed browser path, or text).
* Audio is transient: read, validated, handed to the provider and discarded. It is never logged, persisted, or placed in an analytics or audit payload; only safe categories are logged.
* A transcript is untrusted input: it is returned for the candidate to review and submit through the normal answer path (same validation and injection scan as typed text). A transcript that trips the
  injection guard is refused exactly as typed text would be.
* Synthesis speaks only text the client says is the approved, candidate-visible response, after server-side sanitisation (no secrets, markdown, links, citations, system markers or error traces).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from src.api.dependencies import get_current_principal, get_speech_runtime
from src.api.rate_limit import enforce, user_key
from src.api.schemas.speech import SpeechCapabilitiesResponse, SynthesisRequest, TranscriptionResponse
from src.constants import SPEECH_MAX_AUDIO_BYTES
from src.observability.sanitizer import safe_metadata
from src.speech_service import SpeechError

router = APIRouter(prefix="/speech", tags=["speech"])
_log = logging.getLogger("ask4mo.speech")

_STATUS = {"unavailable": 503, "not_authorized": 503, "model_unavailable": 503, "busy": 429, "timeout": 504, "provider_error": 502, "unsupported_language": 422, "unsupported_mime": 415,
           "too_large": 413, "too_long": 413, "empty": 422, "corrupt_audio": 422, "empty_transcript": 422, "empty_synthesis": 502, "empty_text": 422, "unsafe_text": 422, "discarded": 500}
# The stable error envelope carries only {code, message, request_id}. The fallback is implied by the endpoint: a failed transcription falls back to governed browser dictation or typing, a failed synthesis
# to governed browser speech or reading on screen; the frontend decides from ``/speech/capabilities`` which of those is allowed.


class SpeechHTTPError(HTTPException):
    """An explicit HTTP error with a stable machine code in the standard envelope (``error_code`` is read by the central handler)."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.error_code = code


def _refuse(kind: str, exc: SpeechError, user_id: int) -> HTTPException:
    _log.info("speech.%s %s", kind, safe_metadata({"outcome": "refused", "category": exc.category, "user_scoped": True}))
    status = _STATUS.get(exc.category, 502)
    code = "speech_unavailable" if exc.category in ("unavailable", "not_authorized", "model_unavailable") else exc.category
    return SpeechHTTPError(status, code, exc.message)


@router.get("/capabilities", response_model=SpeechCapabilitiesResponse, summary="What speech the frontend may use (no secrets, no provider internals)")
def speech_capabilities(principal=Depends(get_current_principal), runtime=Depends(get_speech_runtime)) -> SpeechCapabilitiesResponse:
    return SpeechCapabilitiesResponse(**runtime.candidate_view())


@router.post("/transcriptions", response_model=TranscriptionResponse, summary="Transcribe one recording (transient audio; untrusted transcript)")
async def transcribe(audio: UploadFile = File(...), language: str = Form(..., min_length=2, max_length=8), principal=Depends(get_current_principal), runtime=Depends(get_speech_runtime)) -> TranscriptionResponse:
    enforce("cost_speech_stt_user", user_key(principal.user_id))
    data = await audio.read(SPEECH_MAX_AUDIO_BYTES + 1)        # bounded read: never an unbounded buffer
    try:
        out = runtime.transcribe(data, mime_type=audio.content_type or "", language=language)
    except SpeechError as exc:
        raise _refuse("stt", exc, principal.user_id)
    finally:
        data = b""                                              # drop the reference; the runtime already discarded its copy
    if out.transcript.blocked:
        _log.info("speech.stt %s", safe_metadata({"outcome": "blocked_transcript", "user_scoped": True}))
        raise SpeechHTTPError(422, "transcript_blocked", "That recording could not be used. You can type your answer.")
    _log.info("speech.stt %s", safe_metadata({"outcome": "ok", "language": out.language, "user_scoped": True}))
    return TranscriptionResponse(transcript=out.transcript.text, language=out.language, duration_seconds=out.duration_seconds, provider=out.provider,
                                 flagged=out.transcript.verdict != "allow", blocked=False)


@router.post("/synthesis", summary="Speak one approved, candidate-visible response (transient audio)")
def synthesize(body: SynthesisRequest, principal=Depends(get_current_principal), runtime=Depends(get_speech_runtime)) -> Response:
    enforce("cost_speech_tts_user", user_key(principal.user_id))
    try:
        result = runtime.synthesize(body.text, language=body.language)
    except SpeechError as exc:
        raise _refuse("tts", exc, principal.user_id)
    _log.info("speech.tts %s", safe_metadata({"outcome": "ok", "language": result.language, "user_scoped": True}))
    return Response(content=result.audio, media_type=result.mime_type, headers={"Cache-Control": "no-store", "X-Speech-Provider": result.provider})
