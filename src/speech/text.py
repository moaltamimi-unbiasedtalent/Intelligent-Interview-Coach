"""Text boundaries for speech (W12.4E).

* A TRANSCRIPT is untrusted candidate-supplied input. ``sanitize_transcript`` runs the SAME normalisation, limit and injection scan as typed text (``validate_input`` and ``scan_text``) and returns the
  cleaned text with the verdict. It never acts on the content, and a transcript is never a privileged instruction channel: a blocked transcript is refused exactly as typed text would be.
* ``prepare_speech_text`` decides what may be SYNTHESISED: only the approved, candidate-visible response. It removes markdown, links and citation markers, redacts secret-like strings, and REFUSES
  text that contains system-prompt markers or looks like an internal error trace. It cannot make arbitrary text "approved"; it only guarantees that what is spoken carries nothing the candidate
  could not already see and nothing the output guard would redact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.copilot.security.injection import scan_text
from src.copilot.security.output_guard import _LEAK_MARKERS, guard_output
from src.copilot.security.validation import validate_input
from src.speech_service import SpeechError

__all__ = ["SanitizedTranscript", "sanitize_transcript", "prepare_speech_text", "MAX_SYNTHESIS_CHARS"]

MAX_SYNTHESIS_CHARS = 1500
_TRACE = re.compile(r"(Traceback \(most recent call last\)|\bFile \"[^\"]+\", line \d+|\bat [\w.$]+\([\w.]+:\d+\)|sqlalchemy\.|psycopg\.|\bOperationalError\b)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?://|mailto:)[^)]*\)")
_URL = re.compile(r"https?://\S+")
_CITE = re.compile(r"\[\d+\]")
_MD_MARKS = re.compile(r"[`*_#>]+")


@dataclass(frozen=True)
class SanitizedTranscript:
    text: str
    verdict: str            # allow | allow_with_warning | block
    indicators: tuple[str, ...]
    truncated: bool

    @property
    def blocked(self) -> bool:
        return self.verdict == "block"


def sanitize_transcript(text: str) -> SanitizedTranscript:
    v = validate_input(text or "", "query")
    if not v.ok:
        raise SpeechError("No usable speech was detected.", category="empty_transcript")
    scan = scan_text(v.cleaned)
    return SanitizedTranscript(text=v.cleaned, verdict=scan.verdict, indicators=tuple(scan.indicators), truncated=v.truncated)


def prepare_speech_text(text: str) -> str:
    """The text that may be spoken for an approved, candidate-visible response, or a ``SpeechError`` (category only; never the content)."""
    raw = (text or "").strip()
    if not raw:
        raise SpeechError("There is nothing to speak.", category="empty_text")
    lowered = raw.lower()
    if any(m in lowered for m in _LEAK_MARKERS):
        raise SpeechError("That text cannot be spoken.", category="unsafe_text")
    if _TRACE.search(raw):
        raise SpeechError("That text cannot be spoken.", category="unsafe_text")
    guarded = guard_output(raw)                      # redacts secret-like strings
    cleaned = _MD_LINK.sub(r"\1", guarded.safe_answer)
    cleaned = _URL.sub("", cleaned)
    cleaned = _CITE.sub("", cleaned)
    cleaned = _MD_MARKS.sub("", cleaned)
    cleaned = re.sub(r"\[REDACTED\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise SpeechError("There is nothing to speak.", category="empty_text")
    if len(cleaned) > MAX_SYNTHESIS_CHARS:
        raise SpeechError("That text is too long to speak in one request.", category="too_long")
    return cleaned
