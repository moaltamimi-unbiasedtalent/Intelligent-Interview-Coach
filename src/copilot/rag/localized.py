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
from src.prompt_assets import render

__all__ = ["agent_text", "AGENT_TEXT", "AGENT_TEXT_KEYS", "resolve_language", "section_headings", "insufficient_message", "fallback_strings",
           "language_directive", "SECTION_HEADINGS", "INSUFFICIENT", "FALLBACK", "compensation_guidance", "unverified_general_notice",
           "COMPENSATION_GUIDANCE", "UNVERIFIED_GENERAL", "UNRETRIEVED_LIMITATION", "unretrieved_limitation"]

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


def resolve_language(code: str | None) -> str:
    """Allow-list a conversation-language code; anything unknown/blank is English (the default)."""
    c = (code or "").strip().lower()
    return c if c in SECTION_HEADINGS else "en"


def section_headings(code: str | None) -> tuple[str, str, str]:
    return SECTION_HEADINGS[resolve_language(code)]


def insufficient_message(code: str | None) -> str:
    return INSUFFICIENT[resolve_language(code)]


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
    # 06C: the directive text is the versioned asset ``rag/response_language`` (byte-identical to the former inline literal); the name comes ONLY from the allow-list.
    return render("rag/response_language", "rag.synthesis", language_name=LANGUAGE_NAMES[lang])


# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# 06C: Mo-voiced deterministic sentences of the AGENT path.
#
# Language ownership (CLAUDE.md): the Mo conversation language owns every sentence Mo "says", including the deterministic text that stands in for the model. The agent
# path (`src/agent/nodes.py`, `human.py`, `grounding.py`) still carries these as English literals. The localized text lives HERE (bounded allow-list, no model call,
# English byte-identical to those literals) so wiring `src/agent/*` is a pure substitution once that package's owner order allows an edit; until then the agent keeps its
# English literals and `tests/test_policy_sentence_inventory_06c.py` pins that the English column here equals them. Engineering translations pending native review (LG-11);
# never presented as reviewed.
AGENT_TEXT: dict[str, dict[str, str]] = {
    "agent_unavailable": {
        "en": "The assistant is temporarily unavailable. Please try again.",
        "de": "Der Assistent ist vorübergehend nicht verfügbar. Bitte versuche es erneut.",
        "fr": "L’assistant est temporairement indisponible. Veuillez réessayer.",
        "es": "El asistente no está disponible temporalmente. Inténtalo de nuevo.",
        "it": "L’assistente non è temporaneamente disponibile. Riprova.",
        "pt": "O assistente está temporariamente indisponível. Tenta novamente.",
        "nl": "De assistent is tijdelijk niet beschikbaar. Probeer het opnieuw.",
        "ru": "Ассистент временно недоступен. Пожалуйста, попробуйте ещё раз.",
    },
    "agent_not_configured": {
        "en": "The assistant isn't configured in this environment.",
        "de": "Der Assistent ist in dieser Umgebung nicht eingerichtet.",
        "fr": "L’assistant n’est pas configuré dans cet environnement.",
        "es": "El asistente no está configurado en este entorno.",
        "it": "L’assistente non è configurato in questo ambiente.",
        "pt": "O assistente não está configurado neste ambiente.",
        "nl": "De assistent is in deze omgeving niet geconfigureerd.",
        "ru": "Ассистент не настроен в этой среде.",
    },
    "agent_step_limit": {
        "en": "I've reached the limit of steps for this request. Here's what I have so far.",
        "de": "Ich habe die Schrittgrenze für diese Anfrage erreicht. Das ist mein bisheriger Stand.",
        "fr": "J’ai atteint la limite d’étapes pour cette demande. Voici ce que j’ai pour l’instant.",
        "es": "He alcanzado el límite de pasos para esta solicitud. Esto es lo que tengo hasta ahora.",
        "it": "Ho raggiunto il limite di passaggi per questa richiesta. Ecco quello che ho finora.",
        "pt": "Atingi o limite de passos para este pedido. Isto é o que tenho até agora.",
        "nl": "Ik heb de staplimiet voor dit verzoek bereikt. Dit is wat ik tot nu toe heb.",
        "ru": "Я достиг предела шагов для этого запроса. Вот что у меня есть на данный момент.",
    },
    "hitl_approve_memory": {
        "en": "Would you like me to remember this for future preparation?",
        "de": "Soll ich mir das für künftige Vorbereitungen merken?",
        "fr": "Souhaitez-vous que je retienne cela pour vos préparations futures ?",
        "es": "¿Quieres que recuerde esto para tus próximas preparaciones?",
        "it": "Vuoi che lo ricordi per le tue prossime preparazioni?",
        "pt": "Queres que me lembre disto para preparações futuras?",
        "nl": "Wil je dat ik dit onthoud voor toekomstige voorbereidingen?",
        "ru": "Хотите, чтобы я запомнил это для будущей подготовки?",
    },
    "hitl_approve_handoff": {
        "en": "Ready to practise the areas we've identified?",
        "de": "Bereit, die erkannten Bereiche zu üben?",
        "fr": "Prêt à vous exercer sur les points que nous avons identifiés ?",
        "es": "¿Listo para practicar las áreas que hemos identificado?",
        "it": "Pronto a esercitarti sulle aree che abbiamo individuato?",
        "pt": "Pronto para praticar as áreas que identificámos?",
        "nl": "Klaar om de gevonden aandachtspunten te oefenen?",
        "ru": "Готовы потренировать выявленные области?",
    },
    "warn_uncited_retrieval": {
        "en": "Retrieved evidence was used, but the final response did not include an inline source reference.",
        "de": "Es wurden abgerufene Belege verwendet, aber die endgültige Antwort enthält keinen Quellenverweis im Text.",
        "fr": "Des preuves récupérées ont été utilisées, mais la réponse finale ne contient pas de référence de source dans le texte.",
        "es": "Se usó evidencia recuperada, pero la respuesta final no incluye una referencia de fuente en el texto.",
        "it": "Sono state usate evidenze recuperate, ma la risposta finale non include un riferimento alla fonte nel testo.",
        "pt": "Foram usadas evidências recuperadas, mas a resposta final não inclui uma referência à fonte no texto.",
        "nl": "Er is opgehaald bewijs gebruikt, maar het uiteindelijke antwoord bevat geen bronverwijzing in de tekst.",
        "ru": "Были использованы найденные подтверждения, но в итоговом ответе нет ссылки на источник в тексте.",
    },
    "warn_statistic_removed": {
        "en": "An external statistic was stated without retrieval; the unsupported figure was removed and an evidence limitation given.",
        "de": "Eine externe Statistik wurde ohne Abruf genannt; die nicht belegte Zahl wurde entfernt und eine Beleggrenze angegeben.",
        "fr": "Une statistique externe a été indiquée sans récupération de sources ; le chiffre non étayé a été retiré et une limite des preuves a été indiquée.",
        "es": "Se indicó una estadística externa sin recuperación de fuentes; se eliminó la cifra sin respaldo y se indicó la limitación de la evidencia.",
        "it": "È stata indicata una statistica esterna senza recupero di fonti; la cifra non supportata è stata rimossa ed è stato indicato il limite delle evidenze.",
        "pt": "Foi indicada uma estatística externa sem recuperação de fontes; o valor sem suporte foi removido e foi indicado o limite das evidências.",
        "nl": "Er werd een externe statistiek genoemd zonder bronnen op te halen; het niet-onderbouwde cijfer is verwijderd en de beperking van het bewijs is vermeld.",
        "ru": "Внешняя статистика была указана без поиска источников; неподтверждённая цифра удалена и указано ограничение подтверждений.",
    },
    "warn_unverified_general": {
        "en": "An external factual question was answered without retrieval; the answer is labelled as not source-backed.",
        "de": "Eine externe Sachfrage wurde ohne Abruf beantwortet; die Antwort ist als nicht quellenbasiert gekennzeichnet.",
        "fr": "Une question factuelle externe a reçu une réponse sans récupération de sources ; la réponse est signalée comme non étayée par des sources.",
        "es": "Se respondió una pregunta factual externa sin recuperación de fuentes; la respuesta se marca como no respaldada por fuentes.",
        "it": "È stata data risposta a una domanda fattuale esterna senza recupero di fonti; la risposta è contrassegnata come non supportata da fonti.",
        "pt": "Foi respondida uma pergunta factual externa sem recuperação de fontes; a resposta está assinalada como não apoiada em fontes.",
        "nl": "Een externe feitelijke vraag is beantwoord zonder bronnen op te halen; het antwoord is gemarkeerd als niet door bronnen onderbouwd.",
        "ru": "На внешний фактический вопрос дан ответ без поиска источников; ответ помечен как не подкреплённый источниками.",
    },
}
AGENT_TEXT_KEYS: tuple[str, ...] = tuple(AGENT_TEXT)

assert all(set(t) == set(SUPPORTED_LOCALE_CODES) for t in AGENT_TEXT.values()), "every agent-path sentence must cover exactly the supported locales"


def agent_text(key: str, code: str | None) -> str:
    """A bounded Mo-voiced agent-path sentence in the conversation language (unknown or blank code: English). An unknown KEY is a programming error, never a silent English fallback."""
    return AGENT_TEXT[key][resolve_language(code)]
