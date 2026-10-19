"""Transient audio lifecycle for the governed speech providers (W12.4E).

Candidate audio is TRANSIENT: held in memory for one request, optionally written to a private temporary file ONLY when an engine truly needs a path, and always discarded in a ``finally``.
It is never logged, never persisted, never put in an analytics event or an audit payload, and never written to object storage. ``LIVE_TEMP_FILES`` is an observable counter so a test (and an
operator diagnostic) can prove nothing is left behind.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from src import constants
from src.speech_service import SpeechError, validate_audio

__all__ = ["TransientAudio", "secure_tempfile", "sniff_container", "validate_and_sniff", "LIVE_TEMP_FILES", "live_temp_file_count"]

_lock = threading.Lock()
LIVE_TEMP_FILES: set[str] = set()


def live_temp_file_count() -> int:
    with _lock:
        return len(LIVE_TEMP_FILES)


@dataclass
class TransientAudio:
    """One request's audio. ``discard()`` overwrites the buffer (best effort) and drops the reference. Never printed: ``repr`` carries only the size."""

    data: bytearray
    mime_type: str
    duration_seconds: float | None = None
    discarded: bool = field(default=False, init=False)

    def __repr__(self) -> str:                       # never the bytes
        return f"TransientAudio(bytes={len(self.data)}, discarded={self.discarded})"

    def view(self) -> bytes:
        if self.discarded:
            raise SpeechError("The audio is no longer available.", category="discarded")
        return bytes(self.data)

    def discard(self) -> None:
        if not self.discarded:
            for i in range(len(self.data)):
                self.data[i] = 0
            self.data.clear()
            self.discarded = True


@contextmanager
def secure_tempfile(data: bytes, suffix: str = ".bin"):
    """Write ``data`` to a private (0700 directory, 0600 file) temporary file for an engine that needs a path; overwrite and remove it in ``finally``, even when the engine raises."""
    d = Path(tempfile.mkdtemp(prefix="ask4mo_speech_"))
    os.chmod(d, 0o700)
    path = d / f"audio{suffix}"
    with _lock:
        LIVE_TEMP_FILES.add(str(path))
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        yield path
    finally:
        try:
            if path.exists():
                size = path.stat().st_size
                with open(path, "r+b") as fh:
                    fh.write(b"\x00" * size)
                path.unlink()
        except OSError:
            pass
        shutil.rmtree(d, ignore_errors=True)
        with _lock:
            LIVE_TEMP_FILES.discard(str(path))


def sniff_container(data: bytes) -> str | None:
    """The container implied by the leading bytes, or ``None``. Used to reject a payload whose declared MIME type does not match its content (corrupt or disguised audio)."""
    head = bytes(data[:16])
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if head[:4] == b"OggS":
        return "ogg"
    if head[4:8] == b"ftyp":
        return "mp4"
    if head[:3] == b"ID3" or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


_MIME_TO_CONTAINER = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3"}


def validate_and_sniff(data: bytes, mime_type: str, *, max_bytes: int = constants.SPEECH_MAX_AUDIO_BYTES, max_seconds: int = constants.SPEECH_MAX_AUDIO_SECONDS) -> float | None:
    """The existing size, MIME and duration validation (``validate_audio``) PLUS a content check: the leading bytes must match the declared container. Raises ``SpeechError`` (a category, never audio)."""
    duration = validate_audio(data, mime_type, max_bytes=max_bytes, max_seconds=max_seconds)
    declared = _MIME_TO_CONTAINER.get((mime_type or "").split(";")[0].strip().lower())
    found = sniff_container(data)
    if declared and found != declared:
        raise SpeechError("The audio file is damaged or is not the format it claims to be.", category="corrupt_audio")
    return duration
