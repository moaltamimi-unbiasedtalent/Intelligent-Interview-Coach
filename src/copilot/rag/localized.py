"""Conversation-language text for the deterministic Career-chat path (P10B-W9.7A).

Language ownership (do not conflate):
  * INTERFACE language owns Ask4Mo UI chrome (headings, buttons, labels) - frontend catalogue.
  * Mo CONVERSATION language owns everything Mo "says": the model's prose AND the deterministic text
    that stands in for it. That includes the three response-template section headings this prompt asks
    the model to write ("Evidence (from sources):" / "Tool results (calculated):" / "Recommendation:")
    and the deterministic fallback summary used when the model is unavailable.

Everything here is a bounded allow-list keyed by the supported locale codes. An unknown/blank code resolves
to English (the existing default), so the default path is byte-for-byte unchanged. No model call, no raw
client string ever reaches a prompt (the language NAME comes from `src.locales.LANGUAGE_NAMES`).
"""

from __future__ import annotations

from src.locales import LANGUAGE_NAMES, SUPPORTED_LOCALE_CODES

__all__ = ["resolve_language", "section_headings", "insufficient_message", "fallback_strings",
           "language_directive", "SECTION_HEADINGS", "INSUFFICIENT", "FALLBACK"]

# (evidence heading, tool-results heading, recommendation heading)
SECTION_HEADINGS: dict[str, tuple[str, str, str]] = {
    "en": ("Evidence (from sources):", "Tool results (calculated):", "Recommendation:"),
    "de": ("Belege (aus Quellen):", "Werkzeugergebnisse (berechnet):", "Empfehlung:"),
    "fr": ("Preuves (issues des sources):", "Résultats des outils (calculés):", "Recommandation:"),
    "es": ("Evidencia (de las fuentes):", "Resultados de herramientas (calculados):", "Recomendación:"),
    "it": ("Evidenze (dalle fonti):", "Risultati degli strumenti (calcolati):", "Raccomandazione:"),
    "pt": ("Evidências (das fontes):", "Resultados das ferramentas (calculados):", "Recomendação:"),
    "nl": ("Bewijs (uit bronnen):", "Toolresultaten (berekend):", "Aanbeveling:"),
    "ru": ("Подтверждения (из источников):", "Результаты инструментов (рассчитано):", "Рекомендация:"),
}

# The sentence the model is told to use when evidence is insufficient (and the deterministic fallback).
INSUFFICIENT: dict[str, str] = {
    "en": "The knowledge base does not contain enough evidence to answer that.",
    "de": "Die Wissensbasis enthält nicht genügend Belege, um das zu beantworten.",
    "fr": "La base de connaissances ne contient pas assez de preuves pour y répondre.",
    "es": "La base de conocimiento no contiene evidencia suficiente para responder a eso.",
    "it": "La base di conoscenza non contiene prove sufficienti per rispondere.",
    "pt": "A base de conhecimento não contém evidências suficientes para responder a isso.",
    "nl": "De kennisbank bevat onvoldoende bewijs om dat te beantwoorden.",
    "ru": "В базе знаний недостаточно подтверждений, чтобы на это ответить.",
}

# Deterministic fallback summary pieces (used when the model is unavailable). {n} = passage count.
FALLBACK: dict[str, dict[str, str]] = {
    "en": {"unavailable": "The assistant model is currently unavailable, so this is a limited summary.",
           "retrieved": "Retrieved {n} narrative passage(s) — see sources."},
    "de": {"unavailable": "Das Assistenzmodell ist derzeit nicht verfügbar, daher ist dies eine eingeschränkte Zusammenfassung.",
           "retrieved": "{n} Textpassage(n) abgerufen, siehe Quellen."},
    "fr": {"unavailable": "Le modèle de l’assistant est actuellement indisponible; voici donc un résumé limité.",
           "retrieved": "{n} passage(s) narratif(s) récupéré(s), voir les sources."},
    "es": {"unavailable": "El modelo del asistente no está disponible en este momento, así que este es un resumen limitado.",
           "retrieved": "Se recuperaron {n} pasaje(s) narrativo(s); consulta las fuentes."},
    "it": {"unavailable": "Il modello dell’assistente non è al momento disponibile, quindi questo è un riepilogo limitato.",
           "retrieved": "Recuperati {n} passaggio/i narrativo/i; vedi le fonti."},
    "pt": {"unavailable": "O modelo do assistente está atualmente indisponível, por isso este é um resumo limitado.",
           "retrieved": "Foram recuperados {n} excerto(s) narrativo(s); consulte as fontes."},
    "nl": {"unavailable": "Het assistentmodel is momenteel niet beschikbaar, dit is daarom een beperkte samenvatting.",
           "retrieved": "{n} verhalende passage(s) opgehaald, zie de bronnen."},
    "ru": {"unavailable": "Модель ассистента сейчас недоступна, поэтому это сокращённая сводка.",
           "retrieved": "Найдено фрагментов текста: {n}, см. источники."},
}

assert set(SECTION_HEADINGS) == set(INSUFFICIENT) == set(FALLBACK) == set(SUPPORTED_LOCALE_CODES), (
    "localized Career-chat text must cover exactly the supported locales")


def resolve_language(code: str | None) -> str:
    """Allow-list a conversation-language code; anything unknown/blank is English (the default)."""
    c = (code or "").strip().lower()
    return c if c in SECTION_HEADINGS else "en"


def section_headings(code: str | None) -> tuple[str, str, str]:
    return SECTION_HEADINGS[resolve_language(code)]


def insufficient_message(code: str | None) -> str:
    return INSUFFICIENT[resolve_language(code)]


def fallback_strings(code: str | None) -> dict[str, str]:
    return FALLBACK[resolve_language(code)]


def language_directive(code: str | None) -> str | None:
    """Trusted, allow-list-only 'respond in <language>' instruction, or None for English/unknown.

    Prose-only: it never changes grounding, citation, tool or geography rules."""
    lang = resolve_language(code)
    if lang == "en":
        return None
    name = LANGUAGE_NAMES[lang]
    return (
        f"RESPONSE LANGUAGE\nThe candidate has chosen to converse in {name}. Write your whole answer "
        f"in {name}, using EXACTLY the section headings given in the rules above. This affects only the "
        "language of your prose: keep the same grounding, citation ([n]) and tool-result rules, do not "
        "translate source titles, citations, numbers or the candidate's own text, and do not change the "
        "labour market or geography of any career information because of the language."
    )
