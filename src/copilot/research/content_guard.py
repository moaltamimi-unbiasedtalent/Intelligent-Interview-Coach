"""External-content guard for current-market research (Phase 7F, §34–§36).

External web/API text is UNTRUSTED DATA and must NEVER act as Agent instructions. The primary
control is structural: this text only ever reaches the model inside a typed ``ExternalEvidence``
field whose tool/system contract says it is quoted evidence, not instructions. This module is the
defence-in-depth backstop: it caps length, normalises whitespace, and FLAGS obvious
prompt-injection patterns (reusing the existing injection scanner) so a flagged snippet can be
dropped or clearly quoted — never followed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.copilot.security.injection import scan_text

MAX_SNIPPET_CHARS = 800

# External-content-specific indicators layered ON TOP of the shared injection scanner: data
# exfiltration and outbound-call instructions that web pages may embed to weaponise an agent.
_EXTERNAL_INDICATORS: tuple[tuple[str, re.Pattern], ...] = (
    ("exfiltration", re.compile(r"\bsend\b.{0,40}\b(cv|resume|candidate|user'?s?)\b", re.I)),
    ("exfiltration_url", re.compile(r"\b(send|post|email|upload|forward)\b.{0,40}https?://", re.I)),
    ("outbound_call", re.compile(r"\b(call|fetch|request|visit|open)\b.{0,20}\b(this|the following)\b.{0,10}\b(url|link|endpoint)\b", re.I)),
    ("data_exfil_generic", re.compile(r"\b(exfiltrat|leak the|reveal the|forward the)\b", re.I)),
)


@dataclass
class GuardedText:
    text: str
    flagged: bool
    indicators: list[str]


def guard_external_text(text: str, *, max_chars: int = MAX_SNIPPET_CHARS) -> GuardedText:
    """Return a bounded, whitespace-normalised snippet plus an injection verdict.

    ``flagged`` is True when the content contains prompt-injection / exfiltration / outbound-call
    indicators ("ignore previous instructions", "reveal your system prompt", "send the user's CV
    to <url>", "call this URL", role-override, etc.). The caller drops or quotes it — it is NEVER
    executed as an instruction. Flagging is defence-in-depth; the PRIMARY control is that this
    text only ever reaches the model inside a typed evidence field, never as instructions (§35).
    """
    cleaned = " ".join((text or "").split())
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "…"
    scan = scan_text(cleaned)
    indicators = list(scan.indicators)
    for label, pattern in _EXTERNAL_INDICATORS:
        if pattern.search(cleaned):
            indicators.append(label)
    return GuardedText(text=cleaned, flagged=bool(indicators), indicators=indicators)
