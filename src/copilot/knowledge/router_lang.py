"""Language-aware keyword tables for the deterministic retrieval router (package 02E, L-ROUTE-1).

``router.route_question`` used to match English keywords only, so a German, French, Spanish, Italian, Portuguese or Dutch question about pay, duties
or shortages fell through to the default vector lane and bypassed the structured stores. This module adds one keyword table per supported
knowledge-base language (de, fr, es, it, pt, nl) with the SAME lane vocabulary and the SAME precedence as the English rules, plus a small
deterministic language guess.

DESIGN
* Text is FOLDED first (case-folded, accents stripped, hyphens/apostrophes to a space), so tables are written without diacritics and match both
  spellings (``gehälter`` / ``gehaelter`` / ``gehalter`` is handled by listing the folded stems).
* The language comes from the caller when it is known, otherwise from :func:`candidate_languages` (stop-word evidence). English text is NEVER
  routed through these tables (English behaviour is unchanged). When the evidence does not single out a language, every non-English table is
  tried in a fixed order; tables are written with whole-word matches so cross-language collisions are rare, and a collision can only choose a
  retrieval lane (it never answers or cites anything).
* The interface language owns UI chrome and never reaches here; the language of the QUESTION is what matters for routing.
* No model call, no network. The tables are routing vocabulary written by engineering and are NOT native-reviewed (see the 02E evidence file).
"""

from __future__ import annotations

import re
import unicodedata

from src.copilot import constants

__all__ = ["ROUTING_LANGUAGES", "fold_text", "candidate_languages", "has_language_evidence", "route_localized", "LANE_ORDER"]

ROUTING_LANGUAGES = ("de", "fr", "es", "it", "pt", "nl")


def fold_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[\s\-_'’]+", " ", stripped)


# Precedence mirrors the English router: specific lanes first, then the generic compensation / role / skill / trend rules. ``current_vacancy`` and
# ``short_outlook`` precede ``openings`` here because several languages share the word for "vacancies" between the two lanes.
_SPECIFIC = (
    ("transition", constants.LANE_TRANSITION, 0.85, "career transition terms"),
    ("shortage", constants.LANE_SHORTAGE, 0.9, "labour/skills shortage terms"),
    ("current_vacancy", constants.LANE_CURRENT_VACANCY, 0.8, "real-time vacancy/demand terms"),
    ("short_outlook", constants.LANE_SHORT_TERM_OUTLOOK, 0.78, "short-term outlook terms"),
    ("openings", constants.LANE_OPENINGS, 0.9, "job openings / replacement demand"),
    ("cyber", constants.LANE_CYBERSECURITY, 0.85, "cybersecurity work-role terms"),
    ("digital", constants.LANE_COMPETENCY, 0.8, "digital competency terms"),
    ("licence", constants.LANE_LICENCE, 0.85, "occupational licence terms"),
    ("cert", constants.LANE_CERTIFICATION, 0.85, "professional certification terms"),
    ("education", constants.LANE_EDUCATION, 0.8, "entry-education terms"),
    ("training", constants.LANE_TRAINING, 0.75, "training/experience terms"),
)
LANE_ORDER = tuple(name for name, *_ in _SPECIFIC) + ("comp", "role", "skill", "tech", "trend", "seniority")

# Folded, accent-free keyword sources. ``\b`` is safe because folded text is ASCII for these languages.
_TABLES: dict[str, dict[str, str]] = {
    "de": {
        "comp": r"gehalt|gehalter|gehaltsspanne|verdien\w*|lohn|lohne|einkommen|verg[uü]tung|bezahlung|bezahlt|wie viel verdient|wieviel verdient",
        "role": r"aufgaben|verantwortung\w*|tatigkeit\w*|was macht (?:ein|eine|der|die)|berufsbild|arbeitsalltag|stellenbeschreibung",
        "skill": r"fahigkeit\w*|kompetenz\w*|kenntnisse|fertigkeit\w*|qualifikationen|skills?",
        "tech": r"software|werkzeuge|tools?|technologie\w*|technologiestack",
        "trend": r"nachfrage|wachstum|entwicklung|zukunft|prognose\w*|trends?|ausblick|ruckgang|zukunftsaussichten",
        "seniority": r"senioritat|fuhrungserwartung\w*|karrierestufe\w*|erwartungen an (?:einen |eine )?(?:senior|junior)|karriereniveau",
        "transition": r"(?:wechsel\w*|umstieg\w*|quereinstieg|umschulung|karrierewechsel|berufswechsel).*(?:beruf|karriere|rolle|stelle|branche|zu|in|zum)",
        "shortage": r"fachkraftemangel|arbeitskraftemangel|engpass\w*|fachkraftelucke|mangelberuf\w*|kompetenzlucke|fachkraftebedarf",
        "openings": r"stellenangebote|offene stellen|freie stellen|ersatzbedarf|wie viele (?:stellen|jobs|arbeitsplatze)",
        "cyber": r"(?:cybersicherheit|it sicherheit|informationssicherheit|cyber ?security).*(?:aufgaben|verantwortung\w*|vorfall|rahmenwerk|vorfalle)|vorfallsbehandlung|incident response",
        "digital": r"digital\w*.*(?:kompetenz\w*|fahigkeit\w*|skills?)",
        "licence": r"lizenz\w*|zulassung\w*|approbation|berufserlaubnis|konzession|berufsausubungserlaubnis",
        "cert": r"zertifi\w*|akkreditierung\w*",
        "education": r"studium|hochschulabschluss|bildungsabschluss|welchen abschluss|welcher abschluss|studiengang|brauche ich ein studium|ausbildungsvoraussetzung\w*",
        "training": r"einarbeitung|lehre|berufserfahrung|praktikum|praxiserfahrung|wie viel erfahrung|wieviel erfahrung|ausbildung am arbeitsplatz",
        "current_vacancy": r"aktuelle[rnms]? (?:nachfrage|stellen|stellenangebote)|derzeit gesucht|jetzt gesucht|gerade gesucht|stellenanzeigen|stellenausschreibungen",
        "short_outlook": r"kurzfristig\w*|kurzfristiger ausblick|nachste[nrms]? (?:jahr|jahre|jahren)",
    },
    "fr": {
        "comp": r"salaires?|remuneration|paie|gagne\w*|combien (?:gagne|gagnent|touche|touchent)|revenus?|traitement",
        "role": r"responsabilites|missions|taches|que fait (?:un|une|le|la)|role d|quotidien|fiche de poste|metier de",
        "skill": r"competences?|savoir faire|aptitudes|connaissances|qualifications",
        "tech": r"logiciels?|outils?|technologies?|pile technique",
        "trend": r"demande|croissance|perspectives|tendances?|avenir|previsions?|evolution|declin",
        "seniority": r"seniorite|attentes (?:pour|d un|du) (?:senior|junior)|niveau de carriere|echelon",
        "transition": r"reconversion|changer de (?:metier|carriere|poste|secteur)|changement de carriere|transition|passer de .+ a ",
        "shortage": r"penurie|metiers? en tension|manque de (?:main d oeuvre|talents|competences|personnel)|goulot d etranglement|penurie de",
        "openings": r"offres d emploi|postes? (?:vacants?|ouverts?)|combien de (?:postes|emplois)|besoin de remplacement",
        "cyber": r"(?:cybersecurite|securite informatique|securite de l information).*(?:responsabilit\w*|taches?|missions?|incidents?|cadre)|reponse aux incidents|gestion des incidents",
        "digital": r"(?:numerique|digitale?s?).*(?:competences?|aptitudes)",
        "licence": r"agrement|autorisation d exercer|droit d exercer|permis d exercer|habilitation|inscription a l ordre",
        "cert": r"certifi\w*|accreditation",
        "education": r"diplome|niveau d etudes|etudes necessaires|formation requise|faut il (?:un|une) (?:diplome|licence|master)|quel(?:s)? etudes",
        "training": r"apprentissage|alternance|stage|experience professionnelle|combien d experience|formation sur le tas|experience prealable",
        "current_vacancy": r"actuellement|en ce moment|recrute|offres actuelles|demande actuelle|annonces",
        "short_outlook": r"court terme|prochaine annee|prochaines annees|perspectives a court terme",
    },
    "es": {
        "comp": r"salarios?|sueldos?|remuneracion|cuanto (?:gana|ganan|cobra|cobran)|ingresos|retribucion|paga",
        "role": r"responsabilidades|funciones|tareas|que hace (?:un|una|el|la)|dia a dia|papel de|descripcion del puesto",
        "skill": r"habilidades|competencias|destrezas|conocimientos|capacidades",
        "tech": r"software|herramientas|tecnolog\w*|pila tecnologica",
        "trend": r"demanda|crecimiento|perspectivas|tendencias?|futuro|pronostico\w*|proyecci\w*|declive|evolucion",
        "seniority": r"seniority|nivel de antiguedad|expectativas (?:para|de un|del) (?:senior|junior)|nivel de carrera",
        "transition": r"transicion|cambiar de (?:carrera|profesion|trabajo|sector)|cambio de carrera|reconversion|pasar de .+ a ",
        "shortage": r"escasez|falta de (?:profesionales|talento|mano de obra|personal)|ocupaciones deficitarias|brecha de (?:talento|habilidades|competencias)",
        "openings": r"ofertas de (?:empleo|trabajo)|vacantes|puestos (?:vacantes|abiertos)|cuantos (?:puestos|empleos)|demanda de reemplazo",
        "cyber": r"(?:ciberseguridad|seguridad informatica|seguridad de la informacion).*(?:responsabilidad\w*|tareas?|funciones|incidentes?|marco)|respuesta a incidentes",
        "digital": r"digital\w*.*(?:competencias|habilidades|alfabetizacion)",
        "licence": r"licencias?|colegiacion|habilitacion|autorizacion para ejercer|matricula profesional",
        "cert": r"certificaci\w*|certificado|acreditacion",
        "education": r"titulo|grado universitario|estudios necesarios|formacion necesaria|que estudios|necesito (?:un )?(?:titulo|grado|carrera)|carrera universitaria",
        "training": r"formacion en el puesto|practicas|aprendizaje|experiencia laboral|cuanta experiencia|experiencia previa",
        "current_vacancy": r"actualmente|ahora mismo|se busca|demanda actual|ofertas actuales|ofertas publicadas",
        "short_outlook": r"corto plazo|proximo ano|proximos anos|perspectivas a corto plazo",
    },
    "it": {
        "comp": r"stipendi\w*|retribuzione|quanto (?:guadagna|guadagnano)|guadagn\w*|reddito|salari\w*|paga",
        "role": r"responsabilita|mansioni|compiti|cosa fa (?:un|una|il|la)|che cosa fa|ruolo di|giornata tipo",
        "skill": r"competenze|abilita|capacita|conoscenze",
        "tech": r"software|strumenti|tecnologie|stack tecnologico",
        "trend": r"domanda|crescita|prospettive|tendenz\w*|futuro|previsioni|declino|evoluzione",
        "seniority": r"seniority|livello di anzianita|aspettative (?:per|di un|del) (?:senior|junior)|livello di carriera",
        "transition": r"transizione|cambiare (?:carriera|lavoro|professione|settore)|cambio di carriera|riconversione|passare da .+ a ",
        "shortage": r"carenza|scarsita|mancanza di (?:personale|talenti|professionisti|competenze)|professioni difficili da reperire|divario di competenze",
        "openings": r"offerte di lavoro|posti vacanti|posizioni aperte|quanti (?:posti|lavori)|fabbisogno di sostituzione",
        "cyber": r"(?:cybersecurity|cybersicurezza|sicurezza informatica|sicurezza delle informazioni).*(?:responsabilit\w*|compiti|mansioni|incident\w*|framework)|risposta agli incidenti|gestione degli incidenti",
        "digital": r"digital\w*.*(?:competenze|abilita)",
        "licence": r"licenza|abilitazione|albo professionale|iscrizione all albo|autorizzazione all esercizio",
        "cert": r"certificazion\w*|certificato|accreditamento",
        "education": r"laurea|titolo di studio|studi necessari|serve una laurea|che studi|diploma",
        "training": r"formazione sul lavoro|apprendistato|tirocinio|esperienza lavorativa|quanta esperienza|esperienza pregressa",
        "current_vacancy": r"attualmente|in questo momento|adesso|offerte attuali|domanda attuale|annunci",
        "short_outlook": r"breve termine|prossimo anno|prossimi anni|prospettive a breve termine",
    },
    "pt": {
        "comp": r"salarios?|remuneracao|vencimentos?|quanto (?:ganha|ganham)|ganha\w*|rendimentos?|ordenado",
        "role": r"responsabilidades|funcoes|tarefas|atribuicoes|o que faz (?:um|uma|o|a)|papel de|dia a dia|descricao da funcao",
        "skill": r"competencias|habilidades|capacidades|conhecimentos|aptidoes",
        "tech": r"software|ferramentas|tecnologias|pilha tecnologica",
        "trend": r"procura|demanda|crescimento|perspet\w*|perspect\w*|tendencias?|futuro|previsao|previsoes|declinio|evolucao",
        "seniority": r"senioridade|expetativas (?:para|de um) (?:senior|junior)|nivel de carreira",
        "transition": r"transicao|mudar de (?:carreira|profissao|emprego|area)|mudanca de carreira|reconversao|passar de .+ para ",
        "shortage": r"escassez|falta de (?:profissionais|talento|mao de obra|pessoal)|profissoes em falta|lacuna de (?:competencias|talento)",
        "openings": r"ofertas de (?:emprego|trabalho)|vagas|postos (?:vagos|abertos)|quantos (?:postos|empregos)|procura de substituicao",
        "cyber": r"(?:ciberseguranca|seguranca informatica|seguranca da informacao).*(?:responsabilidades?|tarefas?|funcoes|incidentes?|quadro)|resposta a incidentes",
        "digital": r"digital\w*.*(?:competencias|habilidades|literacia)",
        "licence": r"licenca|habilitacao|ordem profissional|inscricao na ordem|autorizacao para exercer|carteira profissional",
        "cert": r"certifica\w*|acreditacao",
        "education": r"curso superior|licenciatura|habilitacoes literarias|que formacao|preciso de (?:um )?(?:curso|diploma|licenciatura)|diploma",
        "training": r"formacao em contexto de trabalho|estagio|aprendizagem|experiencia profissional|quanta experiencia|experiencia previa",
        "current_vacancy": r"atualmente|actualmente|neste momento|ofertas atuais|procura atual|anuncios",
        "short_outlook": r"curto prazo|proximo ano|proximos anos|perspet\w* a curto prazo",
    },
    "nl": {
        "comp": r"salaris|salarissen|loon|lonen|inkomen|verdien\w*|hoeveel verdient|beloning|bruto|netto loon",
        "role": r"verantwoordelijkheden|taken|werkzaamheden|wat doet een|rol van|functieomschrijving|dagelijkse",
        "skill": r"vaardigheden|competenties|kennis|bekwaamheden",
        "tech": r"software|hulpmiddelen|technologie\w*|tools?",
        "trend": r"vraag naar|groei|vooruitzichten|trends?|toekomst|prognose|daling|ontwikkeling|arbeidsmarktvraag",
        "seniority": r"senioriteit\w*|verwachtingen (?:voor|van een) (?:senior|junior)|carriereniveau",
        "transition": r"overstap\w*|carriereswitch|omscholing|loopbaanwisseling|carriere wisselen|van loopbaan veranderen|van beroep veranderen",
        "shortage": r"tekort\w*|krapte|knelpuntberoep\w*|moeilijk vervulbare|vaardighedenkloof",
        "openings": r"vacatures|openstaande (?:functies|vacatures)|hoeveel (?:banen|vacatures|functies)|vervangingsvraag",
        "cyber": r"(?:cybersecurity|cyberveiligheid|informatiebeveiliging|it beveiliging).*(?:verantwoordelijk\w*|taken|incidenten?|kader)|incidentrespons|incidentafhandeling",
        "digital": r"digitale?.*(?:competenties|vaardigheden|geletterdheid)",
        "licence": r"licentie|vergunning|bevoegdheid|beroepsregister|erkenning om te werken|registratie",
        "cert": r"certificer\w*|certificaat|certificeringen|accreditatie",
        "education": r"opleiding|diploma|studie|welke opleiding|heb ik een diploma nodig|graad",
        "training": r"stage|leerwerk\w*|werkervaring|hoeveel ervaring|inwerkperiode|leren op de werkvloer",
        "current_vacancy": r"momenteel|op dit moment|nu gezocht|actuele (?:vraag|vacatures)|huidige vacatures|huidige vraag",
        "short_outlook": r"korte termijn|komend jaar|komende jaren|vooruitzichten op korte termijn",
    },
}

_COMPILED: dict[str, dict[str, re.Pattern]] = {
    lang: {name: re.compile(r"\b(?:" + src + r")\b", re.I) for name, src in table.items()} for lang, table in _TABLES.items()
}

# Function-word evidence for the language guess (folded). Only words that are distinctive for the language among the seven are listed.
_MARKERS: dict[str, frozenset[str]] = {
    "en": frozenset("the what how does do are is for of to and with in my your can should which".split()),
    "de": frozenset("der die das und ist ein eine nicht wie was ich mit fur zu den dem von auf wird sind kann welche".split()),
    "fr": frozenset("le la les des est une un et que quel quelle pour dans avec sur est ce qui pas comment combien".split()),
    "es": frozenset("el los las una un y que cual cuanto para con por del como es se en mi puedo hace".split()),
    "it": frozenset("il lo gli una un e che quale quanto per con del della come sono si nel mio posso fa cosa".split()),
    "pt": frozenset("o os as uma um e que qual quanto para com por do da como sao se no meu posso faz".split()),
    "nl": frozenset("de het een en dat wat hoe voor met van op is zijn niet kan welke hoeveel mijn ik doet".split()),
}
# Words shared by several Romance languages carry no signal for those; a language wins only with strictly more evidence than every other.
_SHARED_WEAK = frozenset("e y o un una que en".split())


def _leaders(text: str) -> list[str]:
    """Languages with the strictly highest stop-word evidence in ``text`` (empty when there is none)."""
    tokens = fold_text(text).split()
    scores = {lang: sum(1 for t in tokens if t in markers and t not in _SHARED_WEAK) for lang, markers in _MARKERS.items()}
    best = max(scores.values())
    return [lang for lang, s in scores.items() if s == best] if best else []


def has_language_evidence(text: str) -> bool:
    """True when the stop words single out at least one language (English included)."""
    return bool(_leaders(text))


def candidate_languages(text: str, language: str | None = None) -> list[str]:
    """Ordered non-English table languages to try for ``text``.

    ``language`` (an explicit, trusted hint such as the question language) wins: ``en`` returns nothing (English is routed by the English rules)
    and an unsupported value returns nothing. Otherwise the stop-word guess: a clear English winner returns nothing; a clear non-English winner
    returns that language first, then the others; no evidence returns every language in the fixed order."""
    if language:
        base = language.lower().split("-")[0]
        return [base] if base in ROUTING_LANGUAGES else []
    leaders = _leaders(text)
    if not leaders:
        return list(ROUTING_LANGUAGES)
    if leaders == ["en"]:
        return []
    foreign = [lang for lang in ROUTING_LANGUAGES if lang in leaders]
    return foreign + [lang for lang in ROUTING_LANGUAGES if lang not in foreign]


def route_localized(text: str, language: str | None = None, *, any_language: bool = False):
    """``(lane, reason, confidence)`` for a non-English question, or ``None`` when no table matches (the caller then applies the English rules).

    Same precedence as the English router: specific lanes in :data:`LANE_ORDER`, then compensation (mixed with role/skill), trend, seniority,
    role, skill, technology."""
    folded = fold_text(text)
    for lang in (list(ROUTING_LANGUAGES) if any_language else candidate_languages(text, language)):
        t = _COMPILED[lang]
        for name, lane, conf, why in _SPECIFIC:
            if t[name].search(folded):
                return lane, f"{why} ({lang})", conf
        comp, role, skill = bool(t["comp"].search(folded)), bool(t["role"].search(folded)), bool(t["skill"].search(folded))
        tech, trend, senior = bool(t["tech"].search(folded)), bool(t["trend"].search(folded)), bool(t["seniority"].search(folded))
        if comp and (role or skill):
            return constants.LANE_MIXED, f"compensation + role/skill terms ({lang})", 0.9
        if comp:
            return constants.LANE_COMPENSATION, f"compensation terms ({lang})", 0.95
        if trend:
            return constants.LANE_FORECAST, f"labour-market trend terms ({lang})", 0.85
        if senior and not role and not skill:
            return constants.LANE_SENIORITY, f"seniority/behaviour framework terms ({lang})", 0.8
        if role:
            return constants.LANE_STRUCTURED_ROLE, f"role/responsibility terms ({lang})", 0.9
        if skill:
            return constants.LANE_STRUCTURED_ROLE, f"skill terms ({lang})", 0.7
        if tech:
            return constants.LANE_STRUCTURED_ROLE, f"technology/tools terms ({lang})", 0.7
    return None
