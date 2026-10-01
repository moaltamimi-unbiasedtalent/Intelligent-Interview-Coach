"""Canonical Ask4Mo PRODUCT locale allow-list (P10B-W9.6, extended to eight locales in W9.7).

One source of truth for the supported INTERFACE / Mo-conversation language codes. Pydantic request
schemas import ``AppLocale``; ``src.persistence`` re-exports ``SUPPORTED_LOCALE_CODES`` as
``SUPPORTED_LOCALES`` for existing callers. Russian (``ru``, W9.7) was added HERE and in the frontend
catalogue; the two prompt language-name allow-lists (``src/prompts.py``, ``src/agent/policies.py``)
carry the matching display name.

Adding a locale to this list does NOT enable anything else. These are deliberately SEPARATE
capability dimensions (never derive one from another):
  * speech-capability locales      - ``src/voice/realtime.py`` SUPPORTED_REALTIME_LOCALES, frontend
    ``ttsLocales``/``DICTATION_LANGUAGES`` (provider/device support differs; ``ru`` is NOT supported);
  * document/OCR languages         - ``DOCUMENT_LANGUAGE_CODES`` below (Tesseract packs installed; ``ru``
    is NOT installed/validated, so a Russian ``language_hint`` is not accepted);
  * taxonomy / KB content languages - ``src/copilot/knowledge/governance.py`` SUPPORTED_LANGUAGES
    (UI support != KB content coverage; Russian is NOT an official ESCO language and no Russian
    occupation layer exists - future P10C aliases must carry Ask4Mo-curated provenance);
  * labour-market geography         - ``CAREER_GEOGRAPHIES`` (geography is never derived from language;
    Russia is NOT a supported market).
"""

from __future__ import annotations

from typing import Literal

# The 8 supported product (interface + Mo-conversation) locales.
SUPPORTED_LOCALE_CODES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "pt", "nl", "ru")

# Typed allow-list for request schemas (validated; an out-of-list value is rejected 422).
AppLocale = Literal["en", "de", "fr", "es", "it", "pt", "nl", "ru"]

# English display names, used ONLY to build trusted "write in <language>" directives. The model only ever
# sees a name from this allow-list (never the raw code). Single copy: `src/prompts.py` (Practice) and
# `src/agent/policies.py` (Mo/agent) derive their maps from it, so a locale cannot be added to one and
# forgotten in another.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
}

# Document language (OCR) is its own capability, NOT the app locale: it is limited to the languages
# whose Tesseract data packs ship in deploy/Dockerfile.api. Adding an app locale never extends it.
DOCUMENT_LANGUAGE_CODES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "pt", "nl")
DocumentLanguage = Literal["en", "de", "fr", "es", "it", "pt", "nl"]

__all__ = ["SUPPORTED_LOCALE_CODES", "AppLocale", "LANGUAGE_NAMES", "DOCUMENT_LANGUAGE_CODES", "DocumentLanguage"]
