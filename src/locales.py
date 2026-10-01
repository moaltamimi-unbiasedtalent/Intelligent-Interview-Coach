"""Canonical Ask4Mo PRODUCT locale allow-list (P10B-W9.6).

One source of truth for the supported INTERFACE / Mo-conversation / document language codes, so the
8th locale (W9.7 Russian) is a one-line change here plus the frontend catalogue. Pydantic request
schemas import ``AppLocale``; ``src.persistence`` re-exports ``SUPPORTED_LOCALE_CODES`` as
``SUPPORTED_LOCALES`` for existing callers.

Deliberately SEPARATE (do NOT couple) from:
  * speech-capability locales      — ``src/voice/realtime.py`` SUPPORTED_REALTIME_LOCALES, frontend
    ``ttsLocales``/``DICTATION_LANGUAGES`` (provider/device support differs);
  * taxonomy / KB content languages — ``src/copilot/knowledge/governance.py`` SUPPORTED_LANGUAGES
    (UI support != KB content coverage);
  * labour-market geography         — ``CAREER_GEOGRAPHIES`` (geography is never derived from language).
"""

from __future__ import annotations

from typing import Literal

# The 7 supported product locales. W9.7 adds "ru" here (and the frontend catalogue) — nowhere else.
SUPPORTED_LOCALE_CODES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "pt", "nl")

# Typed allow-list for request schemas (validated; an out-of-list value is rejected 422).
AppLocale = Literal["en", "de", "fr", "es", "it", "pt", "nl"]

__all__ = ["SUPPORTED_LOCALE_CODES", "AppLocale"]
