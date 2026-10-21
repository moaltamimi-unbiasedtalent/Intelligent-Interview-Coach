"""Text normalisation used before injection analysis.

Attackers hide instructions with zero-width characters, control characters and
odd spacing. Normalisation removes that obfuscation so the scanner sees the plain
intent. Two functions:

* :func:`normalize_for_storage` — a light clean kept for display/use (preserves
  case and punctuation).
* :func:`normalize_for_detection` — an aggressive lower-cased form for matching
  (strips zero-width chars, collapses spacing, drops most punctuation).
"""

from __future__ import annotations

import re
import unicodedata

from src.core.security.normalize import ZERO_WIDTH as _ZERO_WIDTH
from src.core.security.normalize import count_control_chars, strip_control

__all__ = ["normalize_for_storage", "normalize_for_detection", "normalize_for_unicode_detection", "normalize_with_boundaries", "normalize_unicode_with_boundaries", "count_control_chars"]

# Low-level primitives (zero-width table, control stripping, control-char count)
# are shared from src.core.security; the domain-specific normalisation below is
# kept here because the Career injection scanner depends on its exact behaviour.
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")


def normalize_for_storage(text: str) -> str:
    """Light clean: strip zero-width + control chars, keep case/punctuation."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.translate(_ZERO_WIDTH)
    text = strip_control(text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text.strip()


def normalize_for_detection(text: str) -> str:
    """Aggressive form for matching: NFKC, lower-case, de-obfuscate, de-punctuate."""
    text = normalize_for_storage(text).lower()
    # Collapse simple separator obfuscation like "i-g-n-o-r-e" or "i.g.n.o.r.e".
    text = re.sub(r"(?<=\b\w)[\s._\-]+(?=\w\b)", "", text)
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_unicode_detection(text: str) -> str:
    """P10D: the detection form for NON-ASCII scripts. ``normalize_for_detection`` turns every character outside ``[a-z0-9]`` into a space, which
    erased accented Latin letters, Cyrillic and Arabic entirely, so no non-English pattern could ever match. This variant keeps every Unicode letter
    and digit, case-folds, and removes combining marks (so "précédentes" matches "precedentes"); punctuation still becomes a space."""
    text = normalize_for_storage(text).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"(?<=\b\w)[\s._\-]+(?=\w\b)", "", text)
    text = re.sub(r"[^\w\s]|_", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# 01A: boundary-preserving detection forms. The two forms above replace every punctuation mark with a space, so a ".{0,25}" gap in a rule could silently run across a
# sentence boundary ("Ignore jargon; focus on the reader. Experience with prompt engineering" matched "ignore ... the ... prompt"). These variants turn sentence terminators and
# line breaks into a " | " marker (a literal "|" in the input is first replaced by a space, so an attacker cannot forge a boundary), letting the retrieved-chunk rules refuse to match across
# sentences while still matching when the marker sits between ADJACENT words.
_BOUNDARY_RE = re.compile(r"[.!?;\n…。]+")


def _with_boundaries(text: str) -> str:
    return _BOUNDARY_RE.sub(" | ", text.replace("|", " "))


def normalize_with_boundaries(text: str) -> str:
    """ASCII detection form (like :func:`normalize_for_detection`) that keeps sentence boundaries as ``" | "``."""
    text = normalize_for_storage(text).lower()
    text = re.sub(r"(?<=\b\w)[\s._\-]+(?=\w\b)", "", text)
    text = _with_boundaries(text)
    text = re.sub(r"[^a-z0-9\s|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_unicode_with_boundaries(text: str) -> str:
    """Unicode detection form (like :func:`normalize_for_unicode_detection`) that keeps sentence boundaries as ``" | "``."""
    text = normalize_for_storage(text).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"(?<=\b\w)[\s._\-]+(?=\w\b)", "", text)
    text = _with_boundaries(text)
    text = re.sub(r"[^\w\s|]|_", " ", text)
    return re.sub(r"\s+", " ", text).strip()
