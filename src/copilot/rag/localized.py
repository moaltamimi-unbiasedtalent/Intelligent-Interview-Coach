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
           "language_directive", "SECTION_HEADINGS", "INSUFFICIENT", "FALLBACK", "compensation_guidance", "unverified_general_notice",
           "COMPENSATION_GUIDANCE", "UNVERIFIED_GENERAL", "UNRETRIEVED_LIMITATION", "unretrieved_limitation",
           "IRRELEVANT_SOURCES", "SOURCE_LANGUAGE_NOTICE", "LANGUAGE_ENDONYMS", "irrelevant_sources_note", "abstention_message", "language_endonym",
           "source_language_notice"]

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

# Owner policy C (2026-10-19): when verified compensation evidence is unavailable Mo never offers an unsourced estimate. This sentence replaces such an offer: how to find reliable sources and
# which details help. Engineering translations pending native review.
COMPENSATION_GUIDANCE: dict[str, str] = {
    "en": "I cannot give a verified salary figure here. To find reliable figures, tell me the country, the seniority and the occupation, and I can help you locate trustworthy salary sources and judge how comparable they are.",
    "de": "Ich kann hier keine belegte Gehaltsangabe machen. Um verlässliche Zahlen zu finden, nenne mir das Land, die Berufserfahrung und den Beruf, dann helfe ich dir, vertrauenswürdige Gehaltsquellen zu finden und ihre Vergleichbarkeit zu beurteilen.",
    "fr": "Je ne peux pas donner ici un chiffre de salaire vérifié. Pour trouver des données fiables, indiquez-moi le pays, le niveau d’expérience et le métier, et je vous aiderai à trouver des sources salariales dignes de confiance et à juger leur comparabilité.",
    "es": "No puedo dar aquí una cifra salarial verificada. Para encontrar datos fiables, indícame el país, el nivel de experiencia y la ocupación, y te ayudaré a localizar fuentes salariales de confianza y a valorar si son comparables.",
    "it": "Non posso fornire qui una cifra salariale verificata. Per trovare dati affidabili, indicami il paese, il livello di esperienza e la professione, e ti aiuterò a individuare fonti salariali attendibili e a valutarne la confrontabilità.",
    "pt": "Não posso dar aqui um valor salarial verificado. Para encontrar dados fiáveis, indica-me o país, o nível de experiência e a profissão, e ajudo-te a localizar fontes salariais de confiança e a avaliar se são comparáveis.",
    "nl": "Ik kan hier geen geverifieerd salarisbedrag geven. Om betrouwbare cijfers te vinden, geef me het land, het ervaringsniveau en het beroep, dan help ik je betrouwbare salarisbronnen te vinden en te beoordelen of ze vergelijkbaar zijn.",
    "ru": "Я не могу назвать здесь проверенную сумму зарплаты. Чтобы найти надёжные данные, укажите страну, уровень опыта и профессию, и я помогу найти надёжные источники и оценить их сопоставимость.",
}

# Owner policy B (2026-10-19): a general answer to an external factual question that was given WITHOUT retrieval must not look source-backed.
UNVERIFIED_GENERAL: dict[str, str] = {
    "en": "Note: this is general information and was not verified against the knowledge base, so it carries no sources.",
    "de": "Hinweis: Dies sind allgemeine Informationen, die nicht mit der Wissensbasis überprüft wurden und daher keine Quellen haben.",
    "fr": "Remarque : il s’agit d’informations générales, non vérifiées dans la base de connaissances, donc sans sources.",
    "es": "Nota: esta es información general que no se verificó en la base de conocimiento, por lo que no tiene fuentes.",
    "it": "Nota: queste sono informazioni generali non verificate nella base di conoscenza, quindi senza fonti.",
    "pt": "Nota: esta é informação geral que não foi verificada na base de conhecimento, por isso não tem fontes.",
    "nl": "Let op: dit is algemene informatie die niet is gecontroleerd in de kennisbank en daarom geen bronnen heeft.",
    "ru": "Примечание: это общая информация, она не проверялась по базе знаний и поэтому не имеет источников.",
}

# Owner policy B: an external statistic or figure was asked for but nothing was retrieved, so the figure is NOT stated. Offers retrieval; never an estimate.
UNRETRIEVED_LIMITATION: dict[str, str] = {
    "en": "I have not retrieved verified evidence for this question, so I cannot state a specific figure. Tell me the country and the occupation and I can search the knowledge base for it.",
    "de": "Ich habe für diese Frage keine belegten Quellen abgerufen und kann daher keine konkrete Zahl nennen. Nenne mir das Land und den Beruf, dann durchsuche ich die Wissensbasis danach.",
    "fr": "Je n’ai pas récupéré de sources vérifiées pour cette question et ne peux donc pas donner de chiffre précis. Indiquez-moi le pays et le métier et je chercherai dans la base de connaissances.",
    "es": "No he recuperado fuentes verificadas para esta pregunta, así que no puedo indicar una cifra concreta. Dime el país y la ocupación y la busco en la base de conocimiento.",
    "it": "Non ho recuperato fonti verificate per questa domanda, quindi non posso indicare una cifra precisa. Dimmi il paese e la professione e la cerco nella base di conoscenza.",
    "pt": "Não recuperei fontes verificadas para esta pergunta, por isso não posso indicar um valor concreto. Diz-me o país e a profissão e procuro na base de conhecimento.",
    "nl": "Ik heb voor deze vraag geen geverifieerde bronnen opgehaald en kan daarom geen concreet cijfer noemen. Geef me het land en het beroep, dan zoek ik het op in de kennisbank.",
    "ru": "Я не получил проверенных источников по этому вопросу, поэтому не могу назвать конкретную цифру. Укажите страну и профессию, и я поищу в базе знаний.",
}

assert set(SECTION_HEADINGS) == set(INSUFFICIENT) == set(FALLBACK) == set(UNRETRIEVED_LIMITATION) == set(COMPENSATION_GUIDANCE) == set(UNVERIFIED_GENERAL) == set(SUPPORTED_LOCALE_CODES), (
    "localized Career-chat text must cover exactly the supported locales")

# 06D (LG-06): the abstention made specific. The existing INSUFFICIENT sentence stays the OPENING of an abstention (the grounding policy and the output
# checks recognise it by that opening); this sentence is appended when sources WERE found but none cleared the relevance floor, so the candidate is told
# why nothing is cited. Mo-voiced, so it follows the Mo conversation language. Engineering translations, NOT natively reviewed.
IRRELEVANT_SOURCES: dict[str, str] = {
    "en": "The sources I found are not relevant to your question, so I am not citing any of them.",
    "de": "Die gefundenen Quellen sind für deine Frage nicht relevant, daher zitiere ich keine davon.",
    "fr": "Les sources trouvées ne sont pas pertinentes pour votre question ; je n’en cite donc aucune.",
    "es": "Las fuentes que encontré no son relevantes para tu pregunta, así que no cito ninguna.",
    "it": "Le fonti trovate non sono pertinenti alla tua domanda, quindi non ne cito nessuna.",
    "pt": "As fontes que encontrei não são relevantes para a tua pergunta, por isso não cito nenhuma.",
    "nl": "De gevonden bronnen zijn niet relevant voor je vraag, dus ik citeer er geen enkele.",
    "ru": "Найденные источники не относятся к вашему вопросу, поэтому я не ссылаюсь ни на один из них.",
}

# 06D (LG-06): a source written in another language than the conversation. Mo never presents what such a source says as if it said it in the candidate's
# language: the notice states the source language and that what is reported is a translation, and quotes the original wording UNCHANGED ({quote} is a
# verbatim excerpt of the retrieved passage, never a translation). {source_language} is the source language's own name (endonym, see LANGUAGE_ENDONYMS).
SOURCE_LANGUAGE_NOTICE: dict[str, str] = {
    "en": "Source {marker} is written in {source_language}, so what is said here from it is a translation, not the source's own wording. Original wording: \"{quote}\"",
    "de": "Quelle {marker} ist auf {source_language} verfasst; was hier daraus wiedergegeben wird, ist eine Übersetzung und nicht der Wortlaut der Quelle. Originalwortlaut: \"{quote}\"",
    "fr": "La source {marker} est rédigée en {source_language} ; ce qui en est rapporté ici est une traduction et non la formulation de la source. Formulation d’origine : \"{quote}\"",
    "es": "La fuente {marker} está redactada en {source_language}; lo que se indica aquí a partir de ella es una traducción y no la formulación de la propia fuente. Texto original: \"{quote}\"",
    "it": "La fonte {marker} è scritta in {source_language}; ciò che qui ne viene riportato è una traduzione e non la formulazione della fonte. Testo originale: \"{quote}\"",
    "pt": "A fonte {marker} está redigida em {source_language}; o que aqui se refere a partir dela é uma tradução e não a formulação da própria fonte. Texto original: \"{quote}\"",
    "nl": "Bron {marker} is geschreven in {source_language}; wat hier daaruit wordt weergegeven is een vertaling en niet de eigen formulering van de bron. Oorspronkelijke tekst: \"{quote}\"",
    "ru": "Источник {marker} написан на языке {source_language}; то, что здесь из него передано, является переводом, а не формулировкой самого источника. Оригинальный текст: \"{quote}\"",
}

# Language names in their own language (endonyms): unambiguous inside a sentence of any other language.
LANGUAGE_ENDONYMS: dict[str, str] = {
    "en": "English", "de": "Deutsch", "fr": "français", "es": "español", "it": "italiano", "pt": "português", "nl": "Nederlands", "ru": "русский",
}

assert set(IRRELEVANT_SOURCES) == set(SOURCE_LANGUAGE_NOTICE) == set(LANGUAGE_ENDONYMS) == set(SUPPORTED_LOCALE_CODES), (
    "06D localized text must cover exactly the supported locales")


def resolve_language(code: str | None) -> str:
    """Allow-list a conversation-language code; anything unknown/blank is English (the default)."""
    c = (code or "").strip().lower()
    return c if c in SECTION_HEADINGS else "en"


def section_headings(code: str | None) -> tuple[str, str, str]:
    return SECTION_HEADINGS[resolve_language(code)]


def insufficient_message(code: str | None) -> str:
    return INSUFFICIENT[resolve_language(code)]


def irrelevant_sources_note(code: str | None) -> str:
    return IRRELEVANT_SOURCES[resolve_language(code)]


def abstention_message(code: str | None, *, sources_found: bool = False) -> str:
    """The abstention sentence in the Mo conversation language. It always OPENS with the standard insufficient-evidence sentence; when sources were
    retrieved but all fell at or below the relevance floor the specific note follows (no citation is offered either way)."""
    base = insufficient_message(code)
    return f"{base} {irrelevant_sources_note(code)}" if sources_found else base


def language_endonym(code: str | None) -> str | None:
    """The language's own name, or ``None`` for a code outside the supported set (an unknown language is never named)."""
    c = (code or "").strip().lower().split("-")[0]
    return LANGUAGE_ENDONYMS.get(c)


def source_language_notice(code: str | None, *, marker: str, source_language: str, quote: str) -> str:
    """The translation notice in the Mo conversation language. ``quote`` must be the source's own words, passed through unchanged."""
    return SOURCE_LANGUAGE_NOTICE[resolve_language(code)].format(marker=marker, source_language=language_endonym(source_language) or source_language, quote=quote)


def compensation_guidance(code: str | None) -> str:
    return COMPENSATION_GUIDANCE[resolve_language(code)]


def unretrieved_limitation(code: str | None) -> str:
    return UNRETRIEVED_LIMITATION[resolve_language(code)]


def unverified_general_notice(code: str | None) -> str:
    return UNVERIFIED_GENERAL[resolve_language(code)]


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
