"""Deterministic occupation-label normalization (GKB-3; PROPOSED DESIGN, version ``n1``). The original text is NEVER replaced; two derived keys are computed from it.

``normalized_text`` (the exact key): Unicode NFKC, case folding, punctuation and hyphens and slashes to a single space, whitespace collapsed. Diacritics are KEPT, so ``año``/``ano``,
``Schaffer``/``Schäffer`` and Russian ``й``/``и`` stay distinct. Preserved because they distinguish occupations: ``+``, ``#``, ``&`` and a ``.`` that begins or continues a token
(``C++ developer``, ``C# developer``, ``.NET developer``, ``Node.js``).
``folded_text`` (the tolerant key): ``normalized_text`` with combining marks removed for LATIN script only. Cyrillic, Greek and other scripts are never folded (folding ``й`` would
merge different words). A folded match can only support a resolution when exactly one occupation holds it; a collision is reported as ambiguity by the resolver.

Deliberately NOT done: German ä→ae style transliteration, compound splitting (``Softwareentwickler`` is not ``Software Entwickler``), gender-form expansion (``Pfleger/in``),
abbreviation expansion (``QA`` stays ``qa``), stemming, translation. Case folding is locale-independent (so ``ß`` folds to ``ss`` and Greek final sigma to ``σ``; Turkish dotted/dotless
i is not specially handled and is documented as a limitation). Nothing here changes an existing system's matching."""

from __future__ import annotations

import re
import unicodedata

__all__ = ["NORMALIZATION_VERSION", "normalize_label", "fold_label", "detect_script", "normalize_language_tag", "UNKNOWN_LANGUAGE"]

NORMALIZATION_VERSION = "n1"
UNKNOWN_LANGUAGE = "und"
_KEEP = set("+#&")
_LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
_SCRIPT_PREFIXES = (("LATIN", "Latn"), ("CYRILLIC", "Cyrl"), ("GREEK", "Grek"), ("ARABIC", "Arab"), ("HEBREW", "Hebr"), ("CJK", "Hani"), ("HIRAGANA", "Hira"),
                    ("KATAKANA", "Kana"), ("HANGUL", "Hang"), ("DEVANAGARI", "Deva"), ("THAI", "Thai"))


def normalize_language_tag(tag: str | None) -> str:
    """A language identifier (BCP-47 style, lowercase primary subtag) or ``und`` when absent. Independent of the UI locale list: any well-formed tag is representable."""
    if tag is None or not str(tag).strip():
        return UNKNOWN_LANGUAGE
    t = str(tag).strip().replace("_", "-")
    parts = t.split("-")
    t = "-".join([parts[0].lower()] + parts[1:])
    if t != UNKNOWN_LANGUAGE and not _LANG_RE.match(t):
        raise ValueError("malformed language identifier")
    return t


def normalize_label(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").casefold()
    out: list[str] = []
    n = len(s)
    for i, ch in enumerate(s):
        if ch.isalnum() or unicodedata.category(ch).startswith("M") or ch in _KEEP:
            out.append(ch)
        elif ch == "." and i + 1 < n and s[i + 1].isalnum():
            out.append(ch)                                                   # ".net", "node.js"
        else:
            out.append(" ")                                                  # whitespace, hyphens, slashes, other punctuation
    return " ".join("".join(out).split())


def detect_script(text: str) -> str | None:
    """The dominant ISO 15924 script of the letters, ``Zzzz`` when scripts are mixed with no clear majority, None when there are no letters."""
    counts: dict[str, int] = {}
    for ch in text or "":
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        code = next((c for prefix, c in _SCRIPT_PREFIXES if name.startswith(prefix)), "Zzzz")
        counts[code] = counts.get(code, 0) + 1
    if not counts:
        return None
    total = sum(counts.values())
    top, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    return top if n * 100 >= total * 80 else "Zzzz"


def fold_label(normalized: str) -> str:
    """Remove combining marks from tokens whose letters are all Latin; every other token (Cyrillic, Greek, mixed, symbols only) is returned unchanged."""
    return " ".join(_strip_marks(tok) if _is_latin(tok) else tok for tok in normalized.split(" "))


def _strip_marks(token: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", token) if not unicodedata.category(c).startswith("M"))


def _is_latin(token: str) -> bool:
    letters = [c for c in token if c.isalpha()]
    return bool(letters) and all(unicodedata.name(c, "").startswith("LATIN") for c in letters)
