"""Candidate-facing grounding policy for Mo's final answers (owner-approved 2026-10-19: policies A, B, C).

ONE deterministic layer, shared by the Career-chat ``answer()`` path and the LangGraph agent path. It extends the existing response-validation layer
(``guard_output`` / ``guard_agent_answer``); it adds no citation system, no retrieval, no model call and no per-language engine. Language only selects which
bounded, localized sentence is shown (``src.copilot.rag.localized``); detection lexicons are language-agnostic unions over the seven supported
knowledge-base languages, so a model that mixes languages is still covered.

What it enforces (smallest practical rewriting; everything else is left exactly as the model wrote it):
  A. Citations. A citation attached to an abstention must point at real retrieved evidence that is relevant to the question or explains the limit of the
     evidence. A marker for evidence about a DIFFERENT geography (compensation) or with no overlap with the question is removed from an abstention or a
     compensation answer, and a coverage limit is never presented as positive evidence for a claim. Valid marker syntax is never taken as claim support.
  C. No unsourced compensation estimates. When no in-scope compensation evidence exists, sentences that offer or give an estimate/range are removed and one
     localized safe-guidance sentence (how to find reliable sources, clarify country, seniority and occupation) is added. Refusals are never removed.
  General. A money figure that appears in no evidence, tool result or user text is removed with its sentence (fabricated number).
  B. (agent only, observation + labelling) A general answer to an external factual question given without retrieval is labelled as not source-backed.
Anything that cannot be classified reliably is reported as ``UNCERTAIN_REQUIRES_REVIEW``; no quality verdict is invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.copilot.rag import localized

__all__ = ["EvidenceView", "PolicyResult", "enforce", "classify_response", "money_figures", "unsupported_money_figures", "offers_unsourced_estimate",
           "is_compensation_query", "is_external_fact_query", "states_insufficient", "CLASSES"]

EVIDENCE_BACKED_ANSWER = "EVIDENCE_BACKED_ANSWER"
ABSTENTION_WITHOUT_CITATIONS = "ABSTENTION_WITHOUT_CITATIONS"
ABSTENTION_WITH_CONTEXTUAL_CITATIONS = "ABSTENTION_WITH_CONTEXTUAL_CITATIONS"
CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
UNSUPPORTED_FACTUAL_RESPONSE = "UNSUPPORTED_FACTUAL_RESPONSE"
UNCERTAIN_REQUIRES_REVIEW = "UNCERTAIN_REQUIRES_REVIEW"
CLASSES = (EVIDENCE_BACKED_ANSWER, ABSTENTION_WITHOUT_CITATIONS, ABSTENTION_WITH_CONTEXTUAL_CITATIONS, CLARIFICATION_REQUESTED, UNSUPPORTED_FACTUAL_RESPONSE, UNCERTAIN_REQUIRES_REVIEW)

_MARKER_RE = re.compile(r"\[(\d+)\]")
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# ---------------------------------------------------------------------------------------------------------------------------------------- lexicons
_COMPENSATION_STEMS = (
    "salary", "salaries", "pay ", "wage", "earn", "compensation", "remuneration", "income",                       # en
    "gehalt", "lohn", "verdien", "vergütung", "verguetung", "einkommen",                                           # de (verdient/verdienen)
    "salaire", "rémunération", "remuneration", "gagne", "revenu",                                                   # fr
    "salario", "sueldo", "remuneración", "gana", "ingreso",                                                         # es
    "stipendio", "retribuzione", "guadagn", "salario", "paga",                                                      # it
    "salário", "remuneração", "ganha", "vencimento", "ordenado",                                                    # pt
    "salaris", "loon", "verdient", "inkomen", "beloning",                                                           # nl
)
_ESTIMATE_STEMS = (
    "estimat", "ballpark", "rough figure", "rough range", "realistic range", "typical range", "salary range", "pay range", "guess",                         # en
    "schätz", "schaetz", "einschätzung", "gehaltsspanne", "gehaltsrahmen", "spanne",                                                                          # de
    "estim", "fourchette", "approximati",                                                                                                                     # fr / es / pt (estim-)
    "rango", "rangos", "orientativ",                                                                                                                          # es
    "stima", "forchetta", "intervallo", "intervalo",                                                                                                          # it / pt
    "faixa", "faixas",                                                                                                                                        # pt
    "schat", "bandbreedte", "marge", "indicatie",                                                                                                             # nl
)
_NEGATORS = {"not", "no", "cannot", "can't", "cant", "unable", "never", "nicht", "kein", "keine", "keinen", "nie", "pas", "ne", "non", "não", "nao", "niet", "geen", "nunca", "impossible",
             "n't"}
_INSUFFICIENT_PREFIXES = None
_EXTERNAL_FACT_STEMS = (
    "statistic", "official", "labour market", "labor market", "unemployment", "regulat", "licen", "legal requirement", "by law", "law ", "government", "census", "published figure",
    "how many ", "what percentage", "what percent", "growth rate", "market size", "demand for",
    "statistik", "offiziell", "arbeitslos", "gesetz", "vorschrift", "behörde", "behoerde",
    "statistique", "officiel", "chômage", "chomage", "réglementation", "reglementation", "loi ", "législation",
    "estadístic", "estadistic", "oficial", "desempleo", "normativa", "reglament", "ley ",
    "statistic", "ufficial", "disoccupazione", "normativ", "legge",
    "estatístic", "estatistic", "desemprego", "regulament", "lei ",
    "statistiek", "officieel", "werkloosheid", "regelgeving", "wetgeving", "wet ",
) + _COMPENSATION_STEMS
_MONEY_CURRENCY = r"(?:[$€£¥]|\b(?:usd|cad|eur|gbp|chf|aud)\b|dollars?|dólares|euros?|pounds?)"


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def is_compensation_query(text: str) -> bool:
    t = " " + _flat(text) + " "
    return any(s in t for s in _COMPENSATION_STEMS)


def is_external_fact_query(text: str) -> bool:
    t = " " + _flat(text) + " "
    return any(s in t for s in _EXTERNAL_FACT_STEMS)


def _insufficient_prefixes() -> list[str]:
    global _INSUFFICIENT_PREFIXES
    if _INSUFFICIENT_PREFIXES is None:
        _INSUFFICIENT_PREFIXES = [" ".join(re.sub(r"\W+", " ", v).strip().lower().split()[:6]) for v in localized.INSUFFICIENT.values()]
    return _INSUFFICIENT_PREFIXES


def states_insufficient(text: str, *, opening_only: bool = False) -> bool:
    """The answer states (in any supported language, even paraphrased after the first six words) that the knowledge base lacks enough evidence."""
    flat = re.sub(r"\W+", " ", (text or "")[:400] if opening_only else (text or "")).strip().lower()
    return any(p in flat for p in _insufficient_prefixes())


# ---------------------------------------------------------------------------------------------------------------------------------------- figures
def _to_number(token: str) -> int | None:
    t = token.strip()
    k = re.match(r"^(\d+(?:[.,]\d+)?)\s?[kK]$", t)
    if k:
        try:
            return int(round(float(k.group(1).replace(",", ".")) * 1000))
        except ValueError:
            return None
    digits = re.sub(r"[^\d]", "", t)
    return int(digits) if digits else None


def money_figures(text: str) -> list[str]:
    """Money figures in a text: a currency marker next to a number, a thousands-separated number, or a number with k. A bare year 1900-2100 is not a figure."""
    t = text or ""
    found: list[str] = []
    for m in re.finditer(rf"{_MONEY_CURRENCY}\s?\d[\d.,   ]*\d|\d[\d.,   ]*\d\s?{_MONEY_CURRENCY}|{_MONEY_CURRENCY}\s?\d|\d\s?{_MONEY_CURRENCY}", t, re.IGNORECASE):
        found.append(m.group(0))
    for m in re.finditer(r"\b\d{1,3}(?:[.,   ]\d{3})+\b", t):
        found.append(m.group(0))
    for m in re.finditer(r"\b\d+(?:[.,]\d+)?\s?[kK]\b", t):
        found.append(m.group(0))
    for m in re.finditer(r"\b(\d{4,})\b", t):
        n = int(m.group(1))
        if len(m.group(1)) == 4 and 1900 <= n <= 2100:
            continue
        found.append(m.group(0))
    return found


def _numbers_in(text: str) -> set[int]:
    out: set[int] = set()
    for m in re.finditer(r"\d[\d.,   ]*\d|\d", text or ""):
        n = _to_number(m.group(0))
        if n is not None:
            out.add(n)
    for m in re.finditer(r"\b\d+(?:[.,]\d+)?\s?[kK]\b", text or ""):
        n = _to_number(m.group(0))
        if n is not None:
            out.add(n)
    return out


_PERCENT_RE = re.compile(r"\d+(?:[.,]\d+)?\s?%")
_COUNTRY_NAMES = {
    "US": ("us", "usa", "u.s.", "united states", "vereinigte staaten", "états-unis", "etats-unis", "estados unidos", "stati uniti", "verenigde staten"),
    "CA": ("canada", "kanada", "canadá", "canadese"),
    "GB": ("uk", "united kingdom", "vereinigtes königreich", "royaume-uni", "reino unido", "regno unito", "verenigd koninkrijk"),
    "DE": ("germany", "deutschland", "allemagne", "alemania", "germania", "alemanha", "duitsland"),
    "FR": ("france", "frankreich", "francia", "frankrijk"),
    "ES": ("spain", "spanien", "espagne", "españa", "spagna", "espanha", "spanje"),
    "IT": ("italy", "italien", "italie", "italia", "itália", "italië"),
    "PT": ("portugal",),
    "NL": ("netherlands", "niederlande", "pays-bas", "países bajos", "paesi bassi", "países baixos", "nederland"),
}
_LIMIT_WORDS = {"only", "nur", "seulement", "uniquement", "solo", "solamente", "apenas", "somente", "alleen", "enkel", "different", "andere", "autre", "otro", "altro", "outro", "ander", "other"}


def _decimals_in(text: str) -> set:
    from decimal import Decimal, InvalidOperation

    out = set()
    for m in re.finditer(r"\d+(?:[.,]\d+)?", text or ""):
        try:
            out.add(Decimal(m.group(0).replace(",", ".")))
        except InvalidOperation:
            continue
    return out


def percent_figures(text: str) -> list[str]:
    return [m.group(0) for m in _PERCENT_RE.finditer(text or "")]


def statistic_figures(text: str) -> list[str]:
    """Figures that read as an external statistic: money, percentages, decimals and non-year numbers of three or more digits (list numbering and years are not figures)."""
    found = list(money_figures(text)) + percent_figures(text)
    found += [m.group(0) for m in re.finditer(r"(?<![\w.])\d+[.,]\d+(?![\w])", text or "")]
    found += [m.group(0) for m in re.finditer(r"\b\d{3,}\b", text or "") if not (len(m.group(0)) == 4 and 1900 <= int(m.group(0)) <= 2100)]
    return found


def _mentions_country(sentence: str, code: str | None) -> bool:
    flat = " " + _flat(sentence) + " "
    names = _COUNTRY_NAMES.get((code or "").upper(), ((code or "").lower(),) if code else ())
    return any(f" {n}" in flat for n in names if n)


def is_context_limitation(sentence: str, foreign_countries: set[str]) -> bool:
    """A sentence that names the evidence's own (other) country AND states a limit ("only for the US", "does not establish Canadian pay"). Such a sentence may quote that foreign figure as context; it never states it as the requested country's pay."""
    tokens = set(_WORD_RE.findall(sentence.lower().replace("’", "'")))
    limited = bool(tokens & _NEGATORS) or bool(tokens & _LIMIT_WORDS) or "n't" in sentence.lower()
    return limited and any(_mentions_country(sentence, c) for c in foreign_countries)


def unsupported_percent_figures(answer: str, allowed_text: str) -> list[str]:
    from decimal import Decimal, InvalidOperation

    allowed = _decimals_in(allowed_text)
    bad = []
    for fig in percent_figures(answer):
        try:
            v = Decimal(re.sub(r"[^\d.,]", "", fig).replace(",", "."))
        except InvalidOperation:
            continue
        if v not in allowed:
            bad.append(fig)
    return bad


def unsupported_money_figures(answer: str, allowed_text: str) -> list[str]:
    """Money figures in the answer whose numeric value appears in NO allowed text (evidence, tool results, the candidate's own words)."""
    allowed = _numbers_in(allowed_text)
    bad = []
    for fig in money_figures(answer):
        n = _to_number(re.sub(rf"{_MONEY_CURRENCY}", "", fig, flags=re.IGNORECASE).strip())
        if n is not None and n not in allowed:
            bad.append(fig)
    return bad


# ---------------------------------------------------------------------------------------------------------------------------------------- sentences
def offers_unsourced_estimate(sentence: str) -> bool:
    """A sentence that offers or gives an estimate/range. A refusal (a negator BEFORE the estimate word, e.g. "I can't estimate") is not an offer; a trailing "non sourcée" is not a negator."""
    tokens = _WORD_RE.findall(sentence.lower().replace("’", "'"))
    flat = " " + _flat(sentence) + " "
    positions = [i for i, tok in enumerate(tokens) if any(tok.startswith(s.strip()) for s in _ESTIMATE_STEMS if " " not in s)]
    phrase_hit = any(s in flat for s in _ESTIMATE_STEMS if " " in s)
    if not positions and not phrase_hit:
        return False
    first = positions[0] if positions else len(tokens)
    before = tokens[max(0, first - 8):first]
    if "n't" in sentence.lower() or any(t in _NEGATORS for t in before):
        return False
    return True


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _units(answer: str):
    """Yield (line_index, sentence) pairs, keeping line structure so edits are local."""
    for li, line in enumerate((answer or "").split("\n")):
        parts = _SENT_SPLIT.split(line) if line.strip() else [line]
        for p in parts:
            yield li, p


# ---------------------------------------------------------------------------------------------------------------------------------------- evidence view
@dataclass
class EvidenceView:
    """Minimal, content-bounded view of one retrieved evidence item (marker n refers to the n-th evidence item)."""

    marker: str                     # "[1]"
    text: str = ""
    evidence_type: str = ""
    country: str | None = None


def _content_tokens(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if len(w) >= 4 and w not in _GENERIC}


_GENERIC = set("what does earn earns salary pays that this with from have your about which would could there their into than then them they were been very more most some such only also over under when where while whom whose ".split()) | \
    set("quel quelle quels combien gagne dans pour avec sans sont leur cette ces plus moins entre sous cual cuanto gana para como esta este estos pero quanto qual quanto wieviel verdient eine einen einem einer oder wenn wird werden aber auch nach wat doet een voor naar over wordt zijn".split())


@dataclass
class PolicyResult:
    answer: str
    response_class: str
    findings: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    removed_sentences: int = 0
    removed_markers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------------------------------------------------- classification
def classify_response(answer: str, evidence: list[EvidenceView], *, query: str = "", resolved_country: str | None = None) -> tuple[str, list[str]]:
    """The six approved response classes. Never infers success from citation syntax alone."""
    text = answer or ""
    markers = {int(m) for m in _MARKER_RE.findall(text)}
    valid = {int(e.marker.strip("[]")) for e in evidence if e.marker.strip("[]").isdigit()}
    bad = sorted(m for m in markers if m not in valid)
    flags: list[str] = []
    if bad:
        flags.append(f"citation marker without evidence: {bad}")
    if money_figures(text):
        flags.append("money figure present")
    short_question = len(text) <= 500 and "?" in text
    abst = states_insufficient(text, opening_only=True)
    if bad or (money_figures(text) and not _figures_supported(text, evidence, resolved_country)):
        return UNSUPPORTED_FACTUAL_RESPONSE, flags
    if abst:
        return (ABSTENTION_WITH_CONTEXTUAL_CITATIONS if markers else ABSTENTION_WITHOUT_CITATIONS), flags
    if markers and evidence:
        return EVIDENCE_BACKED_ANSWER, flags
    if not evidence and short_question:
        return CLARIFICATION_REQUESTED, flags
    if evidence and not markers and len(text) > 200:
        flags.append("evidence was available but the answer carries no citation")
        return UNSUPPORTED_FACTUAL_RESPONSE, flags
    return UNCERTAIN_REQUIRES_REVIEW, flags


def _figures_supported(answer: str, evidence: list[EvidenceView], resolved_country: str | None = None) -> bool:
    return not unsupported_money_figures(answer, " ".join(e.text for e in evidence if not _out_of_scope(e, resolved_country)))


def _out_of_scope(e: EvidenceView, resolved_country: str | None) -> bool:
    """Compensation evidence about a different country than the one requested may not authorise a figure for the requested one."""
    return bool(e.evidence_type == "compensation" and resolved_country and e.country and e.country != resolved_country)


# ---------------------------------------------------------------------------------------------------------------------------------------- enforcement
def enforce(answer: str, *, evidence: list[EvidenceView] | None = None, query: str = "", resolved_country: str | None = None, language: str | None = None,
            allowed_text: str = "") -> PolicyResult:
    """Apply policies A and C and the fabricated-figure rule to a final answer. Deterministic; no model call; local edits only."""
    evidence = list(evidence or [])
    text = answer or ""
    findings: list[str] = []
    removed_markers: list[str] = []
    removed = 0
    comp_ctx = is_compensation_query(query)
    in_scope_comp = [e for e in evidence if e.evidence_type == "compensation" and not _out_of_scope(e, resolved_country)]
    foreign = [e for e in evidence if _out_of_scope(e, resolved_country)]
    foreign_countries = {e.country for e in foreign if e.country}
    # ONLY eligible, in-scope evidence (plus tool results and the candidate's own words) may authorise a figure. Another country's compensation evidence never does.
    corpus = " ".join([allowed_text, query] + [e.text for e in evidence if not _out_of_scope(e, resolved_country)])
    foreign_numbers = _numbers_in(" ".join(e.text for e in foreign))

    # A. citations that must not stay: compensation evidence about another geography, and (on an abstention) evidence unrelated to the question.
    drop: set[str] = {e.marker for e in foreign}
    if states_insufficient(text, opening_only=True) or (comp_ctx and not in_scope_comp):
        q = _content_tokens(query)
        for e in evidence:
            if e.text and q and not (q & _content_tokens(e.text)) and e.marker in set(f"[{m}]" for m in _MARKER_RE.findall(text)):   # unknown text (agent metadata view) is never dropped as unrelated
                drop.add(e.marker)
    drop = {m for m in drop if m in text}
    if drop:
        for m in sorted(drop):
            text = text.replace(m, "")
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        removed_markers = sorted(drop)
        findings.append(f"Removed citation(s) {removed_markers}: evidence about another geography or unrelated to the question must not be cited as support.")

    # C + fabricated figures: remove offending sentences only. A citation marker never authorises an estimate offer or a figure.
    bad_figs = set(unsupported_money_figures(text, corpus)) | set(unsupported_percent_figures(text, corpus))
    lines = text.split("\n")
    out_lines: dict[int, list[str]] = {}
    offer_removed = fig_removed = 0
    for li, sent in _units(text):
        is_offer = comp_ctx and not in_scope_comp and offers_unsourced_estimate(sent)
        sent_bad = [f for f in bad_figs if f in sent]
        # A foreign figure may be quoted only as an explicit limitation about its own country ("the available US evidence does not establish Canadian pay").
        if sent_bad and foreign_numbers and is_context_limitation(sent, foreign_countries):
            sent_bad = [f for f in sent_bad if (_to_number(re.sub(rf"{_MONEY_CURRENCY}", "", f, flags=re.IGNORECASE).strip()) not in foreign_numbers)]
        if is_offer or sent_bad:
            offer_removed += int(is_offer)
            fig_removed += int(bool(sent_bad) and not is_offer)
            removed += 1
            continue
        out_lines.setdefault(li, []).append(sent)
    if offer_removed or fig_removed:
        rebuilt = []
        for li in range(len(lines)):
            kept = out_lines.get(li)
            if kept is None:                 # every sentence on that line was removed
                continue
            rebuilt.append(" ".join(kept) if len(kept) > 1 or kept[0].strip() else kept[0])
        text = "\n".join(rebuilt)
        text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
        if comp_ctx and not in_scope_comp and not states_insufficient(text):
            text = (localized.insufficient_message(language) + ("\n\n" + text if text.strip() else "")).strip()      # the evidence gap is always stated
        elif not text.strip():
            text = localized.insufficient_message(language)
        if offer_removed:
            findings.append("Removed an offer of an unsourced compensation estimate (no verified compensation evidence for this scope).")
            if localized.compensation_guidance(language) not in text:
                text = text.rstrip() + "\n\n" + localized.compensation_guidance(language)
        elif comp_ctx and not in_scope_comp and localized.compensation_guidance(language) not in text:
            text = text.rstrip() + "\n\n" + localized.compensation_guidance(language)
        if fig_removed:
            findings.append("Removed a figure that no eligible in-scope evidence, tool result or user text supports.")

    cls, flags = classify_response(text, evidence, query=query, resolved_country=resolved_country)
    return PolicyResult(answer=text, response_class=cls, findings=findings, flags=flags, removed_sentences=removed, removed_markers=removed_markers)
