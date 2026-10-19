"""Explicit-country detection for the structured retrieval lanes (P10D).

WHY: ``detect_country`` used to recognise only four English-named geographies (DE, UK, US, EU). A question that explicitly named
any OTHER country ("... earn in Canada?", "... in Mexico?") therefore detected nothing, the country guard in the structured lanes
never fired and another nation's official statistics (for example US BLS wages) were returned for it. Likewise a country named in
another supported product language ("en Allemagne", "in Duitsland") was not seen.

RULES (unchanged principles, now applied to more names):
  * Only an EXPLICIT country or region NAME (or a handful of unambiguous demonyms and the legacy source/city signals) establishes a
    geography. A language never implies a country ("was verdient eine Pflegekraft" detects nothing).
  * Detecting a country does NOT mean the product has data for it. A detected country with no same-country record makes the lane
    report insufficient evidence and never substitute another country's statistics (the lanes enforce that).
  * The bare two-letter tokens "US" and "EU" count only in upper case: lower-case "us" and "eu" are ordinary words ("tell us",
    Portuguese "eu", French "eu") and must not select a geography.
  * Names are matched after case, accent and hyphen folding, as whole words only, so "Brasil" and "BRASIL" and "Bresil" agree.

The legacy codes are kept (``UK`` for the United Kingdom, ``EU`` for the supra-national aggregate); every other code is ISO 3166-1
alpha-2. This module adds no data source and makes no claim of coverage for any country it can detect.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["fold", "detect_country_code", "COUNTRY_NAMES", "NAMED_COUNTRY_CODES", "SUPRANATIONAL_TAGS", "GLOBAL_TAGS", "EU_FAMILY_TAGS", "EUROPEAN_COUNTRIES", "tag_matches_country"]

# Order matters: the four legacy geographies keep their historic precedence (DE, UK, US) and the broader EU signal is checked
# LAST, after every national signal ("prefer the most specific national signals before the broader EU signal").
COUNTRY_NAMES: dict[str, tuple[str, ...]] = {
    "DE": ("germany", "german", "deutschland", "berlin", "munich", "munchen", "kldb", "berufenet", "allemagne", "alemania", "germania", "duitsland", "alemanha", "германия"),
    "UK": ("uk", "united kingdom", "britain", "british", "england", "scotland", "wales", "ashe", "civil service", "royaume uni", "reino unido", "regno unito", "verenigd koninkrijk",
           "vereinigtes konigreich", "grossbritannien", "angleterre", "inghilterra", "inglaterra", "engeland", "великобритания"),
    "US": ("u.s.", "usa", "united states", "america", "american", "federal", "etats unis", "estados unidos", "stati uniti", "vereinigte staaten", "verenigde staten", "сша",
           "соединенные штаты"),
    # --- other explicit countries: detected so the lanes can ABSTAIN rather than substitute (no data is implied) ---
    "CA": ("canada", "canadian", "canadien", "canadienne", "canadese", "kanada", "канада", "toronto", "ontario", "quebec", "vancouver"),
    "MX": ("mexico", "mexican", "mexique", "messico", "mexiko", "mexicano", "мексика"),
    "BR": ("brazil", "brazilian", "brasil", "bresil", "brasile", "brasilien", "brazilie", "бразилия", "sao paulo"),
    "CL": ("chile", "chilean", "chileno", "чили"),
    "AR": ("argentina", "argentine", "argentinien", "argentinie", "аргентина"),
    "CO": ("colombia", "colombie", "kolumbien", "colombiano", "колумбия"),
    "PE": ("peru", "perou", "перу"),
    "FR": ("france", "french", "francia", "frankreich", "frankrijk", "франция"),
    "ES": ("spain", "espana", "espagne", "spanien", "spagna", "spanje", "испания"),
    "IT": ("italy", "italia", "italie", "italien", "италия"),
    "NL": ("netherlands", "holland", "nederland", "pays bas", "paises bajos", "niederlande", "olanda", "paesi bassi", "нидерланды"),
    "PT": ("portugal", "португалия"),
    "IE": ("ireland", "irlande", "irlanda", "irland", "ierland"),
    "PL": ("poland", "polska", "pologne", "polonia", "polen"),
    "AT": ("austria", "osterreich", "autriche"),
    "CH": ("switzerland", "schweiz", "suisse", "suiza", "svizzera", "zwitserland", "швейцария"),
    "BE": ("belgium", "belgique", "belgie", "belgien", "belgica", "belgio"),
    "SE": ("sweden", "sverige", "suede", "schweden", "suecia", "svezia", "zweden"),
    "AU": ("australia", "australie", "australien"),
    "NZ": ("new zealand",),
    "IN": ("india", "inde", "indien", "индия"),
    "CN": ("china", "chine", "китай"),
    "JP": ("japan", "japon", "giappone", "япония"),
    "SG": ("singapore",),
    "AE": ("united arab emirates", "uae", "dubai", "emirates"),
    "SA": ("saudi arabia", "saudi", "arabie saoudite", "saudi arabien"),
    "EG": ("egypt", "egypte", "agypten", "egipto", "egitto"),
    "ZA": ("south africa",),
    "NG": ("nigeria",),
    "KE": ("kenya",),
    "RU": ("russia", "russland", "russie", "rusia", "россия"),
    "EU": ("europe", "european", "eurozone", "esco", "cedefop", "eurostat", "europa", "unione europea", "union europeenne", "union europea", "europaische union",
           "europese unie", "uniao europeia", "европа", "европейский союз"),
}
NAMED_COUNTRY_CODES = tuple(COUNTRY_NAMES)

# Geography/country TAGS that are not a single nation. Global or unspecified material is broader context for any country question. The EU family
# (EU aggregates, "Europe") is broader context only for a EUROPEAN country: an EU figure is no more a Brazilian or Canadian statistic than a US one is.
# Evidence tagged to ANOTHER nation is never offered for a country question.
GLOBAL_TAGS = frozenset({"", "GLOBAL", "WORLD", "INTERNATIONAL"})
EU_FAMILY_TAGS = frozenset({"EU", "EU27", "EU28", "EA", "EUROPE", "EUROPEAN UNION"})
SUPRANATIONAL_TAGS = GLOBAL_TAGS | EU_FAMILY_TAGS
EUROPEAN_COUNTRIES = frozenset({"DE", "UK", "GB", "FR", "ES", "IT", "NL", "PT", "IE", "PL", "AT", "CH", "BE", "SE", "EU"})


def tag_matches_country(tag, country: str) -> bool:
    """True when ``tag`` (a country/geography metadata value) is acceptable evidence for ``country``: the same nation (``UK`` and ``GB`` are one), a global or
    unspecified tag, or an EU-family tag when the asked-for country is European."""
    t = str(tag or "").strip().upper()
    c = (country or "").strip().upper()
    if len(t) == 5 and t[2] == "-" and t[:2].isalpha():
        t = t[:2]                                 # a sub-national jurisdiction ("US-CA") belongs to its nation
    if t.startswith(("EUROPEAN UNION", "EURO AREA")):
        t = "EU"                                  # the Eurostat store labels its aggregate rows by name ("European Union - 27 countries (from 2020)")
    if t and t not in GLOBAL_TAGS and t not in EU_FAMILY_TAGS and len(t) > 3:
        named = detect_country_code(str(tag))     # a tag written as a country NAME ("Germany") is the same nation as its code ("DE")
        if named:
            t = named
    if t in GLOBAL_TAGS:
        return True
    if t in EU_FAMILY_TAGS:
        return c in EUROPEAN_COUNTRIES
    return t == c or {t, c} == {"UK", "GB"}


# Case-SENSITIVE two-letter tokens (see the module docstring).
_UPPER_TOKENS = {"US": re.compile(r"(?<![\w.])US(?![\w.])"), "EU": re.compile(r"(?<![\w.])EU(?![\w.])")}


def fold(text: str) -> str:
    """Case-fold, strip accents and treat hyphens, apostrophes and punctuation runs as single spaces (Cyrillic letters are kept)."""
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[\s\-_'’]+", " ", stripped)


def _compile(names: tuple[str, ...]) -> re.Pattern:
    parts = sorted({re.escape(fold(n)).replace(r"\ ", " ") for n in names}, key=len, reverse=True)
    # A name may end with '.' (u.s.): word boundaries are only enforced on word characters.
    return re.compile(r"(?<![\w])(?:" + "|".join(parts) + r")(?![\w])")


_PATTERNS = {code: _compile(names) for code, names in COUNTRY_NAMES.items()}


def detect_country_code(query: str) -> str | None:
    """The first geography (legacy precedence, EU last) EXPLICITLY named in ``query``, or ``None``. Never inferred from language."""
    raw = query or ""
    text = fold(raw)
    for code in COUNTRY_NAMES:
        if code == "EU" and _UPPER_TOKENS["EU"].search(raw):
            return "EU"
        if code == "US" and _UPPER_TOKENS["US"].search(raw):
            return "US"
        if _PATTERNS[code].search(text):
            return code
    return None
