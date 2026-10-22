"""Generic text-normalisation primitives shared across modules.

These are the low-level building blocks (the zero-width table, the control-char
regex, and simple strippers). Higher-level, domain-specific normalisation is
built on top of these in each module's own security package.
"""

from __future__ import annotations

import re

__all__ = [
    "ZERO_WIDTH",
    "control_char_regex",
    "count_control_chars",
    "strip_zero_width",
    "strip_control",
    "fold_confusables",
]

# Zero-width / bidi / BOM code points commonly used to obfuscate text.
ZERO_WIDTH: dict[int, None] = dict.fromkeys(
    [
        0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF,
        0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    ],
    None,
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def control_char_regex() -> re.Pattern:
    """The compiled control-character pattern (shared)."""
    return _CONTROL_RE


def count_control_chars(text: str) -> int:
    """Number of disallowed control/zero-width characters in ``text``."""
    zero_width = sum(1 for ch in text if ord(ch) in ZERO_WIDTH)
    return len(_CONTROL_RE.findall(text)) + zero_width


def strip_zero_width(text: str) -> str:
    return (text or "").translate(ZERO_WIDTH)


def strip_control(text: str) -> str:
    return _CONTROL_RE.sub("", text or "")


# 01A: visually confusable Cyrillic and Greek letters mapped to the Latin letter they imitate. An attacker can write "ignore" with a Cyrillic "i" and "o"; the ASCII
# detection forms drop non-ASCII letters, so the phrase vanished instead of matching. Folding is applied to a COPY used only for detection (never to stored text) and only
# as an ADDITIONAL pass, so it can add a match but never remove one.
_CONFUSABLES: dict[int, str] = {
    # Cyrillic lower case
    0x0430: "a", 0x0435: "e", 0x043E: "o", 0x0440: "p", 0x0441: "c", 0x0443: "y", 0x0445: "x", 0x0456: "i", 0x0458: "j", 0x04CF: "l",
    0x0455: "s", 0x0501: "d", 0x051B: "q", 0x051D: "w", 0x04BB: "h",
    # Cyrillic upper case
    0x0410: "a", 0x0412: "b", 0x0415: "e", 0x041A: "k", 0x041C: "m", 0x041D: "h", 0x041E: "o", 0x0420: "p", 0x0421: "c", 0x0422: "t",
    0x0423: "y", 0x0425: "x", 0x0406: "i", 0x0408: "j", 0x0405: "s",
    # Greek lower and upper case
    0x03BF: "o", 0x03B1: "a", 0x03B5: "e", 0x03B9: "i", 0x03BA: "k", 0x03BD: "v", 0x03C1: "p", 0x03C4: "t", 0x03C5: "u", 0x03C7: "x",
    0x0391: "a", 0x0392: "b", 0x0395: "e", 0x0396: "z", 0x0397: "h", 0x0399: "i", 0x039A: "k", 0x039C: "m", 0x039D: "n", 0x039F: "o",
    0x03A1: "p", 0x03A4: "t", 0x03A5: "y", 0x03A7: "x",
}
_CONFUSABLE_TABLE = {code: letter for code, letter in _CONFUSABLES.items()}


def fold_confusables(text: str) -> str:
    """Return ``text`` with Cyrillic and Greek look-alike letters replaced by their Latin imitation (detection copy only). Call it BEFORE lower-casing: the capital
    forms (for example Cyrillic "К", "Т", "Н") are the true look-alikes and have no lookalike once lower-cased."""
    return (text or "").translate(_CONFUSABLE_TABLE)
