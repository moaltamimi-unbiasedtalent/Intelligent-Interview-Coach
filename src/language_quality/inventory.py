"""Inventory of every localized Mo-voiced policy / safety / fallback sentence, and the mechanical review that finds gaps (06C, D-LANG, REQ-LANG-03).

Scope. The Mo conversation language owns every sentence Mo "says", including the deterministic text that stands in for the model (CLAUDE.md, language ownership). This module lists those
sentences per supported locale, checks each for a missing locale, an empty text, a placeholder mismatch against English, an unchanged-English copy and English-only function or content
words, and records the sentences that are STILL English-only in the code (``OPEN_ENGLISH_ONLY``) so the gap is visible and tested instead of silent.

What this is NOT. A heuristic cannot judge a translation. Every non-English sentence remains an ENGINEERING translation until a named native reviewer approves it (LG-11, OD-LANG-03);
nothing here marks a sentence reviewed. The model-facing directive and policy instructions are English by design (the model reads English; the candidate-facing prose follows the
language directive) and are inventoried separately as ``MODEL_FACING``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.copilot.rag import localized
from src.locales import ACTIVE_CANDIDATE_LOCALES, SUPPORTED_LOCALE_CODES

__all__ = ["PolicySentence", "OpenEnglishOnly", "OPEN_ENGLISH_ONLY", "inventory", "problems", "render_markdown", "english_markers", "placeholders", "open_items_still_present", "MODEL_FACING"]

ROOT = Path(__file__).resolve().parents[2]
NON_ENGLISH = tuple(c for c in SUPPORTED_LOCALE_CODES if c != "en")

# Candidate-facing categories (what the candidate reads).
GROUNDING, SAFETY, FALLBACK, HEADING, AGENT_FALLBACK, HITL, WARNING = "grounding_policy", "safety_policy", "fallback", "response_heading", "agent_fallback", "human_review", "agent_warning"

# Function words that are English and not a word of the target language. A token that is ALSO a normal word in a locale is exempt there (for example the Dutch or German "was", the
# Romance "a", "me", "in", "base", "sources" are real words and are not leaks).
_EN_FUNCTION = {"the", "and", "not", "this", "that", "with", "your", "you", "please", "have", "been", "from", "for", "are", "will", "would", "could", "should", "here", "what", "there",
                "which", "these", "those", "because", "before", "after", "was", "were", "its", "it's", "can't", "isn't", "don't", "i've"}
_EN_FUNCTION_VALID_IN: dict[str, set[str]] = {"de": {"was", "will"}, "nl": {"was", "will"}, "pt": set(), "fr": set(), "es": set(), "it": set()}
# English content words with no meaning-identical spelling in the supported locales.
_EN_CONTENT = {"knowledge", "unavailable", "retrieved", "evidence", "estimate", "limited", "summary", "assistant", "temporarily", "configured", "environment", "request", "reached",
               "limit", "steps", "remember", "future", "preparation", "practise", "identified", "statistic", "removed", "figure", "answer", "answered", "labelled", "question"}
_EN_CONTENT_VALID_IN: dict[str, set[str]] = {"fr": {"question", "limit", "statistic"}, "de": {"limit", "status"}, "nl": {"limit", "status"}, "it": set(), "es": set(), "pt": set()}
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


@dataclass(frozen=True)
class PolicySentence:
    """One candidate-facing localized sentence across the supported locales."""

    key: str
    category: str
    texts: dict[str, str]
    wired: bool          # True when running code reads this table today; False when the agent path still carries its own English literal
    source: str          # where the English and the localized table live


@dataclass(frozen=True)
class OpenEnglishOnly:
    """A candidate-visible sentence the code still emits in English only (a language-ownership gap that this package could not close by itself)."""

    key: str
    english: str
    file: str
    why_open: str


OPEN_ENGLISH_ONLY: tuple[OpenEnglishOnly, ...] = (
    OpenEnglishOnly("agent_safe_model_error", "The assistant is temporarily unavailable. Please try again.", "src/agent/nodes.py",
                    "src/agent/* belongs to 01D then 01C, 04C, 07B; localized text exists as localized.AGENT_TEXT['agent_unavailable']; wiring is a one-line substitution of state['response_language']"),
    OpenEnglishOnly("agent_safe_config_error", "The assistant isn't configured in this environment.", "src/agent/nodes.py", "same ownership; localized.AGENT_TEXT['agent_not_configured']"),
    OpenEnglishOnly("agent_step_limit", "I've reached the limit of steps for this request. Here's what I have so far.", "src/agent/nodes.py", "same ownership; localized.AGENT_TEXT['agent_step_limit']"),
    OpenEnglishOnly("hitl_approve_memory", "Would you like me to remember this for future preparation?", "src/agent/human.py", "same ownership; localized.AGENT_TEXT['hitl_approve_memory'] (the card shows action.message verbatim)"),
    OpenEnglishOnly("hitl_approve_handoff", "Ready to practise the areas we've identified?", "src/agent/human.py", "same ownership; localized.AGENT_TEXT['hitl_approve_handoff']"),
    OpenEnglishOnly("warn_uncited_retrieval", "Retrieved evidence was used, but the final response did not include an inline", "src/agent/grounding.py", "same ownership; localized.AGENT_TEXT['warn_uncited_retrieval']"),
    OpenEnglishOnly("warn_statistic_removed", "An external statistic was stated without retrieval; the unsupported figure was removed and an evidence limitation given.", "src/agent/grounding.py",
                    "same ownership; localized.AGENT_TEXT['warn_statistic_removed']"),
    OpenEnglishOnly("warn_unverified_general", "An external factual question was answered without retrieval; the answer is labelled as not source-backed.", "src/agent/grounding.py",
                    "same ownership; localized.AGENT_TEXT['warn_unverified_general']"),
    OpenEnglishOnly("policy_finding_citations", "Removed citation(s) ", "src/copilot/security/grounding_policy.py",
                    "src/copilot/security/* is ordered 01D, 01C, 04C, 07B; the three PolicyResult.findings are English and are shown as run warnings; no localized table exists yet"),
    OpenEnglishOnly("policy_finding_estimate", "Removed an offer of an unsourced compensation estimate (no verified compensation evidence for this scope).", "src/copilot/security/grounding_policy.py", "same ownership"),
    OpenEnglishOnly("policy_finding_figure", "Removed a figure that no eligible in-scope evidence, tool result or user text supports.", "src/copilot/security/grounding_policy.py", "same ownership"),
    OpenEnglishOnly("next_step_label", "Start interview practice", "src/agent/presentation.py",
                    "src/agent/*; the frontend (frontend/components/agent/AgentAnswer.tsx) renders next_step.label verbatim, so the fix is a catalogue key keyed on next_step.kind (06A catalogue ownership)"),
)

# Model-facing instruction assets: English by design, versioned, never shown to the candidate.
MODEL_FACING: tuple[str, ...] = ("interview/language_directive", "agent/response_language", "rag/response_language", "coaching/directives", "coaching/wrapper", "interview/guardrails", "agent/system",
                                 "rag/synthesis_system")


def _terminal(text: str) -> str:
    """The sentence-final mark (``.``, ``?``, ``!``, ``:`` or ``)``), so a question stays a question and a heading stays a heading in every language."""
    last = text.rstrip()[-1:]
    return last if last in ".?!:)" else ""


def placeholders(text: str) -> tuple[str, ...]:
    return tuple(sorted(_PLACEHOLDER.findall(text)))


def english_markers(text: str, locale: str) -> list[str]:
    """English-only function or content words present in a non-English sentence (a heuristic signal for a human, never a verdict)."""
    if locale == "en":
        return []
    skip = _EN_FUNCTION_VALID_IN.get(locale, set()) | _EN_CONTENT_VALID_IN.get(locale, set())
    hits = {w for w in (m.lower().replace("’", "'") for m in _WORD.findall(text)) if (w in _EN_FUNCTION or w in _EN_CONTENT) and w not in skip}
    return sorted(hits)


_OPEN_FOR = {"agent_unavailable": "agent_safe_model_error", "agent_not_configured": "agent_safe_config_error", "agent_step_limit": "agent_step_limit", "hitl_approve_memory": "hitl_approve_memory",
             "hitl_approve_handoff": "hitl_approve_handoff", "warn_uncited_retrieval": "warn_uncited_retrieval", "warn_statistic_removed": "warn_statistic_removed",
             "warn_unverified_general": "warn_unverified_general"}


def _agent_wired(key: str) -> bool:
    """True when the agent module no longer carries the English literal for ``key`` (it has been wired to the localized table)."""
    item = next(o for o in OPEN_ENGLISH_ONLY if o.key == _OPEN_FOR[key])
    return item.english not in (ROOT / item.file).read_text(encoding="utf-8")


def inventory() -> list[PolicySentence]:
    """Every localized candidate-facing sentence, in a stable order."""
    src = "src/copilot/rag/localized.py"
    out: list[PolicySentence] = []
    for i, key in enumerate(("heading_evidence", "heading_tool_results", "heading_recommendation")):
        out.append(PolicySentence(key, HEADING, {c: localized.SECTION_HEADINGS[c][i] for c in SUPPORTED_LOCALE_CODES}, True, src))
    out.append(PolicySentence("insufficient_evidence", GROUNDING, dict(localized.INSUFFICIENT), True, src))
    out.append(PolicySentence("compensation_guidance", GROUNDING, dict(localized.COMPENSATION_GUIDANCE), True, src))
    out.append(PolicySentence("unretrieved_limitation", GROUNDING, dict(localized.UNRETRIEVED_LIMITATION), True, src))
    out.append(PolicySentence("unverified_general_notice", GROUNDING, dict(localized.UNVERIFIED_GENERAL), True, src))
    out.append(PolicySentence("fallback_model_unavailable", FALLBACK, {c: localized.FALLBACK[c]["unavailable"] for c in SUPPORTED_LOCALE_CODES}, True, src))
    out.append(PolicySentence("fallback_retrieved_passages", FALLBACK, {c: localized.FALLBACK[c]["retrieved"] for c in SUPPORTED_LOCALE_CODES}, True, src))
    category = {"agent_unavailable": AGENT_FALLBACK, "agent_not_configured": AGENT_FALLBACK, "agent_step_limit": AGENT_FALLBACK, "hitl_approve_memory": HITL, "hitl_approve_handoff": HITL}
    for key in localized.AGENT_TEXT_KEYS:
        out.append(PolicySentence(key, category.get(key, WARNING), dict(localized.AGENT_TEXT[key]), _agent_wired(key), src))
    return out


def problems(inv: list[PolicySentence] | None = None) -> list[str]:
    """Mechanical findings. Empty means: no missing locale, no empty text, no placeholder drift, no unchanged-English copy, no English-only word, Russian is Cyrillic."""
    found: list[str] = []
    for s in inv if inv is not None else inventory():
        if set(s.texts) != set(SUPPORTED_LOCALE_CODES):
            found.append(f"{s.key}: locales {sorted(set(SUPPORTED_LOCALE_CODES) ^ set(s.texts))} missing or extra")
            continue
        en = s.texts["en"]
        for code in SUPPORTED_LOCALE_CODES:
            text = s.texts[code]
            if not text.strip():
                found.append(f"{s.key}/{code}: empty")
                continue
            if placeholders(text) != placeholders(en):
                found.append(f"{s.key}/{code}: placeholders {placeholders(text)} != English {placeholders(en)}")
            if code == "en":
                continue
            if text.strip() == en.strip():
                found.append(f"{s.key}/{code}: identical to English")
            leaks = english_markers(text, code)
            if leaks:
                found.append(f"{s.key}/{code}: English-only words {leaks}")
            if _terminal(text) != _terminal(en):
                found.append(f"{s.key}/{code}: ends with {_terminal(text)!r} but English ends with {_terminal(en)!r}")
            if code == "ru" and not _CYRILLIC.search(text):
                found.append(f"{s.key}/ru: no Cyrillic text")
            if code != "ru" and _CYRILLIC.search(text):
                found.append(f"{s.key}/{code}: unexpected Cyrillic text")
    return found


def open_items_still_present() -> list[str]:
    """Open English-only items whose English text is no longer in its file (fixed): the register must then be edited, never left to go stale."""
    gone: list[str] = []
    for item in OPEN_ENGLISH_ONLY:
        path = ROOT / item.file
        if not path.exists() or item.english not in path.read_text(encoding="utf-8"):
            gone.append(item.key)
    return gone


def render_markdown() -> str:
    """The generated inventory document (committed; a test fails if it drifts from the code)."""
    inv = inventory()
    lines = [
        "# 06C policy sentence inventory (generated)",
        "",
        "Generated by `scripts/eval_language_ai_behaviour.py --write` from `src/language_quality/inventory.py`. Do not edit by hand; a test fails if this file drifts from the code.",
        "",
        "Every non-English sentence below is an ENGINEERING translation. None is native-reviewed (LG-11, OD-LANG-03). The mechanical review below is a heuristic that finds a missing, empty,"
        " unchanged-English or English-word-bearing sentence; it cannot judge correctness or tone.",
        "",
        f"- Locales covered: {', '.join(SUPPORTED_LOCALE_CODES)} (Russian is preserved; the active candidate locales are {', '.join(ACTIVE_CANDIDATE_LOCALES)}).",
        f"- Sentences inventoried: {len(inv)} keys x {len(SUPPORTED_LOCALE_CODES)} locales = {len(inv) * len(SUPPORTED_LOCALE_CODES)} texts.",
        f"- Mechanical findings: {len(problems(inv))}.",
        f"- Wired into running code: {sum(1 for s in inv if s.wired)} of {len(inv)} keys; the agent-path keys stay un-wired while `src/agent/*` is owned by an earlier package.",
        "",
        "## Candidate-facing sentences",
        "",
        "| key | category | wired | locales present |",
        "|---|---|---|---|",
    ]
    for s in inv:
        lines.append(f"| `{s.key}` | {s.category} | {'yes' if s.wired else 'NO (agent literal still English)'} | {len(s.texts)} |")
    lines += ["", "## Still English-only in code (OPEN)", "", "| key | file | why it is open |", "|---|---|---|"]
    for o in OPEN_ENGLISH_ONLY:
        lines.append(f"| `{o.key}` | `{o.file}` | {o.why_open} |")
    lines += ["", "## Model-facing instruction assets (English by design, versioned)", ""]
    lines += [f"- `{f}`" for f in MODEL_FACING]
    lines += ["", "## Texts", ""]
    for s in inv:
        lines += [f"### `{s.key}` ({s.category})", ""]
        for code in SUPPORTED_LOCALE_CODES:
            text = s.texts[code].replace("\n", " ").replace("|", "\\|")
            lines.append(f"- {code}: {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
