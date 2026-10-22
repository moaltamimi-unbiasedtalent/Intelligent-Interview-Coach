"""Deterministic, explainable prompt-injection scanner.

Normalise the text, match a fixed set of weighted indicators, sum the weights and
map to a verdict: ``allow`` / ``allow_with_warning`` / ``block``. The rules are
transparent and auditable — and deliberately *best effort*: this catches obvious
attacks, not every possible one (see ``docs/security.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.copilot import constants
from src.copilot.security.injection_rules import (
    CHUNK_OVERRIDES,
    EXTRA_EN,
    EXTRA_EN_CHUNK,
    EXTRA_UNICODE,
    EXTRA_UNICODE_CHUNK,
    chunk_pattern,
    decode_base64_segments,
    fold_leet,
    neutralise_negations,
)
from src.copilot.security.normalize import (
    normalize_for_detection,
    normalize_for_unicode_detection,
    normalize_unicode_with_boundaries,
    normalize_with_boundaries,
)
from src.core.security.normalize import fold_confusables

__all__ = ["InjectionScan", "scan_text", "INDICATORS", "UNICODE_INDICATORS", "SURFACE_INPUT", "SURFACE_CHUNK"]

SURFACE_INPUT = "input"  # user-typed text: the original, strict rules (default)
SURFACE_CHUNK = "chunk"  # a retrieved knowledge chunk: boundary-aware, negation-aware rules (01A)

# (label, weight, compiled pattern). High weight (3.0) = a single hit blocks;
# medium (2.0) = a single hit warns, two combine to a block.
_RAW_INDICATORS: list[tuple[str, float, str]] = [
    (
        "ignore_previous_instructions",
        3.0,
        r"\b(ignore|disregard|forget|override)\b.{0,25}\b(previous|prior|above|earlier|all|the)\b.{0,25}\b(instruction|instructions|prompt|prompts|rule|rules|context|message|messages|guidance|guidelines|directive|directives|programming|constraints)\b",
    ),
    (
        "reveal_system_prompt",
        3.0,
        r"\b(reveal|show|print|repeat|display|output|give|tell)\b.{0,25}\b(system|initial|hidden|developer|original)\b.{0,15}\b(prompt|prompts|message|messages|instruction|instructions)\b",
    ),
    (
        "reveal_secret",
        3.0,
        r"\b(reveal|show|print|leak|give|tell|expose|send|what is|whats)\b.{0,25}\b(api key|apikey|secret|secrets|password|passwords|token|tokens|credential|credentials|environment variable|env var)\b",
    ),
    (
        "disable_security",
        3.0,
        r"\b(disable|turn off|bypass|remove|deactivate|switch off|ignore)\b.{0,25}\b(security|safety|guardrail|guardrails|filter|filters|moderation|restriction|restrictions|protection|rules)\b",
    ),
    (
        "execute_commands",
        3.0,
        r"\b(execute|run|eval|exec|invoke)\b.{0,20}\b(command|commands|shell|code|python|script|os system|subprocess|bash|sql)\b",
    ),
    (
        "follow_source_instructions",
        3.0,
        r"\b(follow|obey|execute|comply with|do what|act on)\b.{0,25}\b(instruction|instructions|command|commands|direction|directions)\b.{0,20}\b(in|from|within|inside|below|this|the)\b.{0,20}\b(document|source|sources|context|text|passage|chunk|article|resume|cv|job description|posting)\b",
    ),
    (
        "role_change",
        2.0,
        r"\b(you are now|act as|pretend to be|from now on you are|new role|assume the role of|roleplay as|behave as)\b",
    ),
    (
        "jailbreak_mode",
        2.0,
        r"\b(do anything now|dan mode|jailbreak|developer mode enabled|unfiltered mode)\b",
    ),
    (
        "new_instructions",
        2.0,
        r"\b(new instructions|updated instructions|the real instructions|here are your instructions|system override|admin override)\b",
    ),
    (
        "print_everything_above",
        2.0,
        r"\b(repeat|print|show|output)\b.{0,15}\b(everything above|the text above|your instructions|your prompt|this conversation)\b",
    ),
]

INDICATORS: list[tuple[str, float, re.Pattern]] = [
    (label, weight, re.compile(pattern)) for label, weight, pattern in _RAW_INDICATORS
]

# P10D: the two highest-impact attack classes (override earlier instructions, reveal the hidden prompt) in the other supported product languages
# (de, fr, es, it, pt, nl, ru) plus Arabic. Matched on the accent-folded Unicode form (``normalize_for_unicode_detection``) because the ASCII
# detection form erases non-ASCII letters. Like the English rules this is best effort, not a guarantee: the PRIMARY control stays structural
# (retrieved text is only ever placed in labelled data blocks, never followed as instructions).
_W = r"\w*"
_UNICODE_RAW_INDICATORS: list[tuple[str, float, str]] = [
    ("ignore_previous_instructions", 3.0, r"\b(ignorier\w*|vergiss\w*|missachte\w*|ubergeh\w*|uberschreib\w*)\b.{0,30}\b(vorherig\w*|fruher\w*|obig\w*|alle\w*|samtliche\w*)\b.{0,30}\b(anweisung\w*|instruktion\w*|regeln|befehle\w*|vorgaben)\b"),
    ("ignore_previous_instructions", 3.0, r"\b(ignor\w+|oubli\w+|neglig\w+)\b.{0,30}\b(precedent\w*|anterieur\w*|toutes?|tous)\b.{0,30}\b(instruction\w*|consigne\w*|regle\w*|directive\w*)\b"),
    ("ignore_previous_instructions", 3.0, r"\b(ignor\w+|olvid\w+|omit\w+|desestim\w+)\b.{0,30}\b(anterior\w*|previa\w*|todas?)\b.{0,30}\b(instruccion\w*|reglas|indicacion\w*|directrices)\b"),
    ("ignore_previous_instructions", 3.0, r"\b(ignor\w+|dimentic\w+)\b.{0,30}\b(preceden\w*|tutte|tutti|prime)\b.{0,30}\b(istruzion\w*|regole|direttive)\b"),
    ("ignore_previous_instructions", 3.0, r"\b(ignor\w+|esquec\w+)\b.{0,30}\b(anterior\w*|previa\w*|todas?|todos)\b.{0,30}\b(instruc\w*|regras|diretriz\w*)\b"),
    ("ignore_previous_instructions", 3.0, r"\b(negeer\w*|vergeet\w*|vergeten)\b.{0,30}\b(vorige|eerdere|alle)\b.{0,30}\b(instructies|regels|opdrachten)\b"),
    ("ignore_previous_instructions", 3.0, r"\b(игнорир\w*|забудь\w*|забыть|пренебреги\w*)\b.{0,30}\b(предыдущ\w*|прежн\w*|все|всe|любые)\b.{0,30}\b(инструкци\w*|правила|указани\w*|команд\w*)\b"),
    ("ignore_previous_instructions", 3.0, r"(تجاهل|انس|تجاوز)\w*.{0,30}(التعليمات|الاوامر|القواعد)"),
    ("reveal_system_prompt", 3.0, r"\b(zeig\w*|verrat\w*|gib\w*|nenn\w*|offenbar\w*|wiederhol\w*|ausgeb\w*)\b.{0,30}\b(system\w*|ursprunglich\w*|versteckt\w*|geheim\w*)\b.{0,15}\b(prompt|anweisung\w*|nachricht|instruktion\w*)\b"),
    ("reveal_system_prompt", 3.0, r"\b(zeig\w*|verrat\w*|gib\w*|nenn\w*|offenbar\w*|wiederhol\w*|ausgeb\w*)\b.{0,30}\b(dein\w*|ihr\w*)?\s*systemprompt\b"),
    ("reveal_system_prompt", 3.0, r"\b(revel\w+|montr\w+|affich\w+|donn\w+|repet\w+|devoil\w+)\b.{0,30}\b(prompt|instructions?)\b.{0,20}\b(systeme|initial\w*|cache\w*|origin\w*)\b"),
    ("reveal_system_prompt", 3.0, r"\b(revel\w+|montr\w+|affich\w+|donn\w+|repet\w+|devoil\w+)\b.{0,30}\b(systeme|initial\w*|cache\w*|origin\w*)\b.{0,15}\b(prompt|instructions?)\b"),
    ("reveal_system_prompt", 3.0, r"\b(revela\w*|muestra\w*|imprime\w*|repite\w*|dame|ensena\w*)\b.{0,30}\b(prompt|instrucciones)\b.{0,20}\b(sistema|inicial\w*|oculto\w*|original\w*)\b"),
    ("reveal_system_prompt", 3.0, r"\b(revela\w*|muestra\w*|imprime\w*|repite\w*|dame|ensena\w*)\b.{0,30}\b(sistema|inicial\w*|oculto\w*|original\w*)\b.{0,15}\b(prompt|instrucciones)\b"),
    ("reveal_system_prompt", 3.0, r"\b(rivela\w*|mostra\w*|stampa\w*|ripeti\w*)\b.{0,30}\b(prompt|istruzioni)\b.{0,20}\b(di sistema|sistema|iniziali|nascost\w*)\b"),
    ("reveal_system_prompt", 3.0, r"\b(rivela\w*|mostra\w*|stampa\w*|ripeti\w*)\b.{0,30}\b(sistema|iniziali|nascost\w*)\b.{0,15}\b(prompt|istruzioni)\b"),
    ("reveal_system_prompt", 3.0, r"\b(revele\w*|mostre\w*|imprima\w*|repita\w*)\b.{0,30}\b(prompt|instruc\w*)\b.{0,20}\b(sistema|inicia\w*|oculto\w*|original\w*)\b"),
    ("reveal_system_prompt", 3.0, r"\b(revele\w*|mostre\w*|imprima\w*|repita\w*)\b.{0,30}\b(sistema|inicia\w*|oculto\w*|original\w*)\b.{0,15}\b(prompt|instruc\w*)\b"),
    ("reveal_system_prompt", 3.0, r"\b(onthul\w*|toon\w*|geef\w*|herhaal\w*)\b.{0,30}\b(systeem\w*|oorspronkelijke|verborgen)\b.{0,15}\b(prompt|instructies|bericht)\b"),
    ("reveal_system_prompt", 3.0, r"\b(onthul\w*|toon\w*|geef\w*|herhaal\w*)\b.{0,30}\bsysteemprompt\b"),
    ("reveal_system_prompt", 3.0, r"\b(покаж\w*|раскро\w*|выведи\w*|повтори\w*|назови\w*)\b.{0,30}\b(системн\w*|исходн\w*|скрыт\w*)\b.{0,15}\b(промпт\w*|инструкци\w*|сообщени\w*)\b"),
    ("reveal_system_prompt", 3.0, r"(اكشف|اظهر|اعرض|كرر)\w*.{0,30}(موجه النظام|تعليمات النظام|النظام)"),
]
UNICODE_INDICATORS: list[tuple[str, float, re.Pattern]] = [(label, weight, re.compile(pattern)) for label, weight, pattern in _UNICODE_RAW_INDICATORS]

# Substring indicators checked against the whitespace-removed text, to catch
# heavy obfuscation (e.g. "i g n o r e   a l l   p r e v i o u s ...").
_COLLAPSED_INDICATORS: list[tuple[str, float, tuple[str, ...]]] = [
    ("ignore_previous_collapsed", 3.0, ("ignoreallprevious", "ignorepreviousinstruction", "ignoreallinstruction", "disregardprevious", "disregardallprevious")),
    ("reveal_prompt_collapsed", 3.0, ("revealsystemprompt", "showsystemprompt", "printsystemprompt", "outputsystemprompt", "repeatsystemprompt")),
    ("reveal_secret_collapsed", 3.0, ("revealapikey", "showapikey", "leakapikey", "revealsecret", "revealpassword", "printapikey")),
    ("disable_security_collapsed", 3.0, ("disablesecurity", "disablesafety", "bypasssecurity", "disableguardrails", "turnoffsafety")),
]


@dataclass
class InjectionScan:
    """The result of scanning one piece of text for injection."""

    verdict: str = constants.VERDICT_ALLOW
    score: float = 0.0
    indicators: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.verdict == constants.VERDICT_BLOCK

    @property
    def flagged(self) -> bool:
        return self.verdict != constants.VERDICT_ALLOW


# Retrieved-chunk forms of the rules (01A): each English / Unicode rule becomes a (loose, twin) pair that cannot run across a sentence boundary; three rules are replaced by their
# chunk-specific form (see ``injection_rules.CHUNK_OVERRIDES``). Built once at import.
_CHUNK_INDICATORS = [(label, weight, *chunk_pattern(CHUNK_OVERRIDES.get(label, raw))) for label, weight, raw in _RAW_INDICATORS]
_CHUNK_UNICODE_INDICATORS = [(label, weight, *chunk_pattern(raw)) for label, weight, raw in _UNICODE_RAW_INDICATORS]


def _scan_variant(text: str, *, chunk: bool, add, original: bool) -> None:
    """Run every rule on one text variant (the text itself or its confusable-folded copy) and report hits through ``add(label, weight)``."""
    bounded = normalize_with_boundaries(text)
    if chunk:
        bounded = neutralise_negations(bounded)
        for label, weight, loose, twin in _CHUNK_INDICATORS:
            if loose.search(bounded) or twin.search(bounded):
                add(label, weight)
        collapsed = re.sub(r"[\s|]", "", bounded)
    else:
        normalized = normalize_for_detection(text)
        for label, weight, pattern in INDICATORS:
            if pattern.search(normalized):
                add(label, weight)
        collapsed = normalized.replace(" ", "")
    for label, weight, pattern in (EXTRA_EN_CHUNK if chunk else EXTRA_EN):
        if pattern.search(bounded):
            add(label, weight)

    if original:  # the multilingual rules read the accent-folded Unicode form of the ORIGINAL text (folding look-alikes would corrupt Cyrillic and Arabic words)
        unicode_form = normalize_for_unicode_detection(text)
        ubounded = normalize_unicode_with_boundaries(text)
        if chunk:
            ubounded = neutralise_negations(ubounded)
            for label, weight, loose, twin in _CHUNK_UNICODE_INDICATORS:
                if loose.search(ubounded) or twin.search(ubounded):
                    add(label, weight)
        else:
            for label, weight, pattern in UNICODE_INDICATORS:
                if pattern.search(unicode_form):
                    add(label, weight)
        for label, weight, pattern in (EXTRA_UNICODE_CHUNK if chunk else EXTRA_UNICODE):
            if pattern.search(ubounded):
                add(label, weight)

    # The collapsed needles are also tried on the REVERSED text: a payload written backwards (".snoitcurtsni suoiverp lla erongi") is a known obfuscation.
    reversed_collapsed = collapsed[::-1]
    for label, weight, needles in _COLLAPSED_INDICATORS:
        if any(needle in collapsed or needle in reversed_collapsed for needle in needles):
            add(label, weight)


def scan_text(text: str, *, surface: str = SURFACE_INPUT) -> InjectionScan:
    """Scan ``text`` and return a verdict with matched indicators and score.

    ``surface`` is :data:`SURFACE_INPUT` (default: user-typed or otherwise attacker-controlled instruction text, original strict rules) or :data:`SURFACE_CHUNK` (a retrieved knowledge
    chunk: descriptive prose, so the boundary-aware and negation-aware forms apply). Each label counts once, so an English hit plus its translation or its confusable-folded copy never
    double-counts. The confusable-folded copy (Cyrillic and Greek look-alikes mapped to Latin) is an additional pass: it can add a hit, never remove one.
    """
    if not text or not text.strip():
        return InjectionScan()
    chunk = surface == SURFACE_CHUNK
    matched: list[str] = []
    score = 0.0

    def add(label: str, weight: float) -> None:
        nonlocal score
        if label not in matched:  # each label counts once
            matched.append(label)
            score += weight

    _scan_variant(text, chunk=chunk, add=add, original=True)
    folded = fold_confusables(text)
    if folded != text:
        _scan_variant(folded, chunk=chunk, add=add, original=False)
    leet = fold_leet(text)
    if leet != text and leet != folded:
        _scan_variant(leet, chunk=chunk, add=add, original=False)
    for decoded in decode_base64_segments(text):  # a Base64 payload is decoded once and scanned as text (never executed)
        _scan_variant(decoded, chunk=chunk, add=add, original=True)

    if score >= constants.INJECTION_BLOCK_THRESHOLD:
        verdict = constants.VERDICT_BLOCK
    elif score >= constants.INJECTION_WARN_THRESHOLD:
        verdict = constants.VERDICT_WARN
    else:
        verdict = constants.VERDICT_ALLOW
    return InjectionScan(verdict=verdict, score=score, indicators=matched)
